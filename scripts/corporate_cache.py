"""Shared registry evidence format. Provenance is written only by adapter callbacks.

A provider response is not a verified legal finding. Old cache entries are never
upgraded by guessing where they came from. Reading does not change evidence dates.
"""
from datetime import datetime, timezone
from typing import Literal
from pydantic import model_validator
from scripts.service_schemas import Schema


class RegistryProvenance(Schema):
    provider: Literal['OpenRegister', 'Companies House']
    origin: Literal['live_provider_response', 'synthetic_fixture']
    synthetic: bool


class CorporateCacheRecord(Schema):
    schema_version: Literal[1]
    provider: Literal['OpenRegister', 'Companies House']
    jurisdiction: Literal['Germany', 'UK']
    registry_identifier: str
    retrieved_at: str | None
    provenance: RegistryProvenance
    verification_status: Literal['provider_reported_unverified', 'synthetic_unverified']
    payload: dict

    @model_validator(mode='after')
    def consistent_provenance(self):
        if not self.registry_identifier or self.provenance.provider != self.provider:
            raise ValueError('Missing or inconsistent registry provenance')
        if (self.provider == 'OpenRegister') != (self.jurisdiction == 'Germany'):
            raise ValueError('Provider jurisdiction mismatch')
        synthetic = self.provenance.origin == 'synthetic_fixture'
        if synthetic != self.provenance.synthetic or self.verification_status != ('synthetic_unverified' if synthetic else 'provider_reported_unverified'):
            raise ValueError('Inconsistent evidence classification')
        if self.retrieved_at is not None:
            when = datetime.fromisoformat(self.retrieved_at.replace('Z', '+00:00'))
            if when.tzinfo is None:
                raise ValueError('Retrieval timestamp requires timezone')
        elif not synthetic:
            raise ValueError('Provider retrieval timestamp missing')
        return self

    def require_identity(self, provider, jurisdiction, identifier, *, live_only=False):
        if (self.provider, self.jurisdiction, self.registry_identifier) != (provider, jurisdiction, identifier):
            raise ValueError('Cached registry context mismatch')
        if live_only and self.provenance.origin != 'live_provider_response':
            raise ValueError('Synthetic evidence is not a live registry cache')
        return self


def captured_record(provider, identifier, payload, *, synthetic=False):
    """Called after successful provider transport, or in an explicit fixture callback."""
    return CorporateCacheRecord(schema_version=1, provider=provider, jurisdiction='Germany' if provider == 'OpenRegister' else 'UK',
        registry_identifier=identifier, retrieved_at=None if synthetic else datetime.now(timezone.utc).isoformat(),
        provenance=RegistryProvenance(provider=provider, origin='synthetic_fixture' if synthetic else 'live_provider_response', synthetic=synthetic),
        verification_status='synthetic_unverified' if synthetic else 'provider_reported_unverified', payload=payload).model_dump(mode='json')


class RegistrySnapshot(dict):
    """Keep adapter dict/model_dump compatibility; metadata is not payload data."""
    def __init__(self, payload, *, retrieved_at=None, cache_accessed_at=None, cache_hit=False,
                 evidence_status='legacy_unverified', evidence_origin='unknown'):
        super().__init__(payload)
        self.retrieved_at = retrieved_at
        self.cache_accessed_at = cache_accessed_at
        self.cache_hit = cache_hit
        self.evidence_status = evidence_status
        self.evidence_origin = evidence_origin
        self.cache_age_seconds = None
        self.freshness = 'unknown'
        if retrieved_at:
            try:
                when = datetime.fromisoformat(retrieved_at.replace('Z', '+00:00'))
                self.cache_age_seconds = (datetime.fromisoformat(cache_accessed_at) - when).total_seconds()
                self.freshness = ('invalid_future_timestamp' if self.cache_age_seconds < 0 else 'stale' if self.cache_age_seconds > 30*86400 else
                                  'recent_cache_not_current_verification' if cache_hit else 'provider_record_not_independent_verification')
            except (ValueError, TypeError):
                self.cache_age_seconds = None

    def model_dump(self, **kwargs):
        import copy
        return copy.deepcopy(dict(self))


def adapter_snapshot(value, provider, identifier, tracker):
    accessed = datetime.now(timezone.utc).isoformat()
    cache_hit = getattr(tracker, 'cache_only', False) or bool(tracker.events and tracker.events[-1].get('cache_hit'))
    # Legacy entries remain readable for record consistency, explicitly unverified.
    # No provenance, timestamp or verification status is invented or written back.
    if not isinstance(value, dict):
        raise ValueError('Unsupported registry cache record')
    if 'schema_version' not in value:
        payload = value.get('payload', value) if provider == 'OpenRegister' else value
        if not isinstance(payload, dict):
            raise ValueError('Unsupported legacy registry payload')
        return RegistrySnapshot(payload, retrieved_at=value.get('retrieved_at') if provider == 'OpenRegister' else None,
                                cache_accessed_at=accessed, cache_hit=cache_hit)
    record = CorporateCacheRecord.model_validate(value).require_identity(provider, 'Germany' if provider == 'OpenRegister' else 'UK', identifier)
    if record.retrieved_at and datetime.fromisoformat(record.retrieved_at.replace('Z', '+00:00')) > datetime.fromisoformat(accessed):
        raise ValueError('Provider retrieval timestamp is in the future')
    return RegistrySnapshot(record.payload, retrieved_at=record.retrieved_at, cache_accessed_at=accessed,
        cache_hit=cache_hit, evidence_status=record.verification_status, evidence_origin=record.provenance.origin)
