"""Central, process-scoped cost reservations and credential-free usage events.

Estimates are never confirmed bills. A finite monetary cap fails closed for
unknown prices. Successful JSON results can be cached; failures are not cached,
but repeat attempts within a run are blocked to prevent accidental paid retries.
"""
import copy
import hashlib
import json
import math
import os
import threading
import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Public documentation checked 2026-11-09; money depends on account/plan.
# https://docs.openregister.de/pricing
# https://docs.tavily.com/documentation/api-credits
CREDITS = {('OpenRegister', 'company_search'): 1,
           ('OpenRegister', 'company_details'): 10,
           ('OpenRegister', 'financials'): 10,
           ('Tavily', 'search_basic'): 1}


class UsageBlocked(RuntimeError):
    pass


class BudgetExceeded(UsageBlocked):
    pass


class ApprovalRequired(UsageBlocked):
    pass


class DuplicateRequestBlocked(UsageBlocked):
    pass


def _money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Budget and price values must be finite and non-negative')
    return result


class JsonCache:
    def __init__(self, directory=None, clock=time.time):
        self.directory = Path(directory) if directory else None
        self.clock = clock
        self.memory = {}

    def get(self, key, ttl):
        entry = self.memory.get(key)
        if entry is None and self.directory:
            path = self.directory / (key + '.json')
            try:
                entry = json.loads(path.read_text())
            except (OSError, ValueError):
                return None
        if not isinstance(entry, dict):
            return None
        saved = entry.get('saved_at')
        if not isinstance(saved, (int, float)) or not math.isfinite(saved) or not 0 <= self.clock() - saved < ttl:
            return None
        if 'value' not in entry:
            return None
        return copy.deepcopy(entry['value'])

    def put(self, key, value):
        # JSON roundtrip rejects nonserializable data before writing.
        entry = json.loads(json.dumps({'saved_at': self.clock(), 'value': value}, allow_nan=False))
        self.memory[key] = entry
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / (key + '.json')
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(entry), encoding='utf-8')
            os.chmod(temporary, 0o600)
            temporary.replace(path)


class UsageTracker:
    def __init__(self, *, max_openregister_credits=50, max_tavily_searches=5,
                 max_session_spend=None, currency='EUR', prices=None,
                 approved=False, development=False, cache_dir=None,
                 cache_ttl=86400, ledger_path=None, clock=time.time):
        for limit in (max_openregister_credits, max_tavily_searches):
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise ValueError('Request limits must be non-negative integers')
        if not math.isfinite(cache_ttl) or cache_ttl <= 0:
            raise ValueError('Cache TTL must be positive and finite')
        self.max_openregister_credits = max_openregister_credits
        self.max_tavily_searches = max_tavily_searches
        self.max_session_spend = _money(max_session_spend) if max_session_spend is not None else None
        self.currency = currency
        self.prices = {k: _money(v) for k, v in (prices or {}).items()}
        self.approved = approved
        self.development = development
        self.cache = JsonCache(cache_dir, clock)
        self.cache_ttl = cache_ttl
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.events = []
        self.spend = Decimal(0)
        self.run_credits = 0
        self.run_searches = 0
        self.attempted = set()
        self.results = {}
        self.lock = threading.RLock()
        self.run_id = 1
        self.session_id = uuid.uuid4().hex

    @staticmethod
    def key(provider, operation, identity):
        payload = json.dumps([1, provider, operation, identity], sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _event(self, provider, operation, outcome, *, credits=0, cost=Decimal(0), cache_hit=False, mode='live'):
        event = {'provider': provider, 'operation': operation,
                 'timestamp': datetime.now(timezone.utc).isoformat(), 'run_id': self.run_id, 'session_id': self.session_id,
                 'outcome': outcome, 'success': True if outcome in ('success', 'cache_hit', 'mocked') else False if outcome == 'failure' else None,
                 'cache_hit': cache_hit, 'estimated_credits': credits,
                 'estimated_cost': str(cost) if cost is not None else None,
                 'cost_display': f'{cost} {self.currency} (estimate)' if cost is not None else 'Cost unknown',
                 'currency': self.currency, 'billing_confirmed': False, 'mode': mode}
        self.events.append(event)
        if self.ledger_path:
            # Fail before making a request if audit storage cannot be written.
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open('a', encoding='utf-8') as stream:
                os.chmod(self.ledger_path, 0o600)
                stream.write(json.dumps(event) + '\n')
        return event

    def cache_hit(self, provider, operation, value):
        with self.lock:
            self._event(provider, operation, 'cache_hit', cache_hit=True)
        return copy.deepcopy(value)

    def new_run(self):
        """Reset per-run limits, retaining session spending and all events."""
        with self.lock:
            self.run_id += 1
            self.run_credits = self.run_searches = 0
            self.attempted.clear()
            self.results.clear()

    def execute(self, provider, operation, identity, call, *, cache=False, approved=False,
                mock=None, success=lambda value: True):
        # One lock covers check/reservation/execution: concurrent duplicate callers
        # cannot both issue a paid request in this process.
        with self.lock:
            key = self.key(provider, operation, identity)
            if self.development:
                if mock is None:
                    self._event(provider, operation, 'blocked_no_mock', mode='development')
                    raise UsageBlocked('Development mode has no fixture for this operation; network blocked')
                value = copy.deepcopy(mock() if callable(mock) else mock)
                self._event(provider, operation, 'mocked', mode='development')
                return value
            if cache:
                value = self.cache.get(key, self.cache_ttl)
                if value is not None:
                    return self.cache_hit(provider, operation, value)
            if key in self.results and not cache:
                return self.cache_hit(provider, operation, self.results[key])
            if key in self.attempted:
                self._event(provider, operation, 'blocked_duplicate')
                raise DuplicateRequestBlocked('Duplicate failed/uncertain request blocked for this run; start an explicit new run to retry')
            credits = CREDITS.get((provider, operation), 0 if provider == 'Companies House' else None)
            cost = Decimal(0) if provider == 'Companies House' else self.prices.get((provider, operation))
            if not (self.approved or approved) and provider != 'Companies House':
                self._event(provider, operation, 'blocked_approval')
                raise ApprovalRequired('Explicit API approval required before a potentially chargeable request')
            reason = None
            if provider in ('OpenRegister', 'Tavily') and credits is None:
                reason = 'Credit estimate unknown for this operation; request blocked'
            elif provider == 'OpenRegister' and self.run_credits + credits > self.max_openregister_credits:
                reason = 'OpenRegister credit limit would be exceeded'
            if provider == 'Tavily' and self.run_searches + 1 > self.max_tavily_searches:
                reason = 'Tavily search limit would be exceeded'
            if self.max_session_spend is not None:
                if cost is None:
                    reason = 'Cost unknown: a finite spending limit requires a reliable per-operation upper-bound estimate'
                elif self.spend + cost > self.max_session_spend:
                    reason = 'Session spending limit would be exceeded'
            if reason:
                self._event(provider, operation, 'blocked_budget')
                raise BudgetExceeded(reason)
            self._event(provider, operation, 'reserved', credits=credits, cost=cost)
            self.attempted.add(key)
            self.run_credits += credits if provider == 'OpenRegister' else 0
            self.run_searches += int(provider == 'Tavily')
            if cost is not None:
                self.spend += cost
            try:
                value = call()
                passed = success(value)
            except Exception:
                self._event(provider, operation, 'failure', credits=0, cost=Decimal(0))
                raise
            self._event(provider, operation, 'success' if passed else 'failure')
            # The reservation event owns consumption; completion events add none.
            if passed:
                self.results[key] = copy.deepcopy(value)
                if cache:
                    try:
                        self.cache.put(key, value)
                    except (OSError, ValueError, TypeError):
                        self._event(provider, operation, 'cache_write_failure')
            return value

    def summary(self):
        unknown = sum(e['outcome'] == 'reserved' and e['estimated_cost'] is None for e in self.events)
        return {'session_id': self.session_id, 'run_openregister_credits_estimated': self.run_credits,
                'run_tavily_searches': self.run_searches,
                'session_spending_estimated': None if unknown else str(self.spend),
                'known_cost_subtotal_estimated': str(self.spend), 'currency': self.currency,
                'cost_display': 'Cost unknown' if unknown else f'{self.spend} {self.currency} (estimate)',
                'unknown_cost_reservations': unknown,
                'billing_confirmed': False}


_runtime = None
_request_runtime = ContextVar('legalflow_usage_tracker', default=None)


def get_tracker():
    global _runtime
    contextual = _request_runtime.get()
    if contextual is not None:
        return contextual
    if _runtime is None:
        _runtime = UsageTracker(cache_dir='data/api_cache', ledger_path='data/api_usage.jsonl')
    return _runtime


@contextmanager
def use_tracker(tracker):
    token = _request_runtime.set(tracker)
    try:
        yield tracker
    finally:
        _request_runtime.reset(token)


class RegistryRecord:
    """JSON-backed register response preserving the adapter's model_dump contract."""
    def __init__(self, data, retrieved_at=None):
        self.data = data
        self.retrieved_at = retrieved_at

    def model_dump(self, **kwargs):
        return copy.deepcopy(self.data)

    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(name) from None
