"""Small operations for n8n; no orchestration, RAG or autonomous tool loop."""
import re
import uuid
from datetime import datetime, timezone
from threading import RLock
import time
import unicodedata

from scripts import company_search, companies_house, german_register, company_research
from scripts.evidence_validator import validate_evidence
from scripts.service_schemas import Candidate, CompanyIdentity, SearchResponse, VerificationResponse, ResearchResponse


class ServiceError(Exception):
    def __init__(self, status_code, code, message):
        self.status_code = status_code
        self.code = code
        self.message = message


def normalized(value):
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', str(value or '')).casefold())


def registration(value):
    value = normalized(value)
    kind = value[:3] if value.startswith(('hrb', 'hra')) else None
    return kind, value[3:] if kind else value


def registration_matches(a, b, type_a=None, type_b=None):
    ka, na = registration(a)
    kb, nb = registration(b)
    ka, kb = normalized(type_a) or ka, normalized(type_b) or kb
    return bool(na and nb and na == nb and (not ka or not kb or ka == kb))


def court(value):
    return normalized(value).removeprefix('amtsgericht')


def scalar(value):
    if value is not None and not isinstance(value, str):
        raise ServiceError(502, 'unsupported_provider_response', 'The provider returned unsupported company fields.')
    return value


def valid_provider_id(value, jurisdiction):
    pattern = r'[A-Za-z0-9]{8}' if jurisdiction == 'UK' else r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}'
    return isinstance(value, str) and bool(re.fullmatch(pattern, value))


class CompanyService:
    def __init__(self, tracker, *, clock=time.monotonic, verification_ttl=900):
        self.tracker = tracker
        self.clock = clock
        self.verification_ttl = verification_ttl
        self.verified = {}
        self.lock = RLock()

    def search(self, request):
        if request.jurisdiction == 'Germany':
            results = company_search.search_companies(request.company_name)
        else:
            response = companies_house.search_company(request.company_name)
            if not isinstance(response, dict) or not isinstance(response.get('items'), list):
                raise ServiceError(502, 'unsupported_provider_response', 'The provider returned an unsupported search response.')
            results = response['items']
        if not isinstance(results, list):
            raise ServiceError(502, 'unsupported_provider_response', 'The provider returned an unsupported search response.')
        candidates = []
        for item in results:
            if not isinstance(item, dict):
                raise ServiceError(502, 'unsupported_provider_response', 'The provider returned an unsupported candidate.')
            german = request.jurisdiction == 'Germany'
            identifier = item.get('company_id') if german else item.get('company_number')
            name = item.get('name') if german else item.get('title')
            if not valid_provider_id(identifier, request.jurisdiction) or not isinstance(name, str) or not name.strip():
                raise ServiceError(502, 'unsupported_provider_response', 'The provider returned an invalid candidate identity.')
            candidates.append(Candidate(provider_company_id=identifier, name=name, jurisdiction=request.jurisdiction,
                                        registration_number=scalar(item.get('register_number') if german else identifier),
                                        register_court=scalar(item.get('register_court')) if german else None,
                                        register_type=scalar(item.get('register_type')) if german else None))
        return SearchResponse(status='candidates_found' if candidates else 'not_found', candidates=candidates,
                              message='Candidates require company-detail verification; name matches are not verified identities.' if candidates else 'No candidates returned by the selected provider.',
                              development=self.tracker.development)

    def verify(self, request):
        def result(status, message, **kwargs):
            return VerificationResponse(status=status, message=message, development=self.tracker.development, **kwargs)
        candidate = None
        selected_id = request.provider_company_id
        if selected_id is None:
            candidates = self.search(request).candidates
            if not candidates:
                return result('not_found', 'No company candidates were found.')
            matches = [c for c in candidates if normalized(c.name) == normalized(request.company_name)]
            if request.registration_number:
                matches = [c for c in matches if not c.registration_number or registration_matches(
                    request.registration_number, c.registration_number, request.register_type, c.register_type)]
            if request.register_court:
                matches = [c for c in matches if not c.register_court or court(c.register_court) == court(request.register_court)]
            # Duplicated search rows for the same ID are one candidate, but
            # conflicting registration metadata for one ID must be reviewed.
            unique = {c.provider_company_id: c for c in matches}
            if len(unique) != 1 or len({c.model_dump_json() for c in matches}) > 1:
                return result('ambiguous', 'Select a candidate explicitly; identity has not been verified.', candidates=candidates)
            candidate = next(iter(unique.values()))
            selected_id = candidate.provider_company_id
        if not valid_provider_id(selected_id, request.jurisdiction):
            return result('verification_failed', 'The selected provider identifier is invalid.')
        german = request.jurisdiction == 'Germany'
        try:
            if german:
                record = german_register.get_company(selected_id)
                raw = record.model_dump(mode='json')
                retrieved_at = getattr(record, 'retrieved_at', None)
            else:
                raw = companies_house.get_company_profile(selected_id.upper())
                retrieved_at = datetime.now(timezone.utc).isoformat()
        except Exception as error:
            status = getattr(error, 'status_code', None)
            if status is None:
                status = getattr(getattr(error, 'response', None), 'status_code', None)
            if status == 404:
                return result('not_found', 'The provider did not return company details for this identifier.')
            raise
        if not isinstance(raw, dict):
            raise ServiceError(502, 'unsupported_provider_response', 'The provider returned an unsupported details response.')
        register = (raw.get('company_register') or {}) if german else {}
        if not isinstance(register, dict):
            raise ServiceError(502, 'unsupported_provider_response', 'The provider returned unsupported registration fields.')
        name = raw.get('name') if german else raw.get('company_name')
        name = name.get('name') if isinstance(name, dict) else name
        identifier = raw.get('id') if german else raw.get('company_number')
        company = CompanyIdentity(
            provider_company_id=scalar(identifier) or '', name=scalar(name) or '', jurisdiction=request.jurisdiction,
            registration_number=scalar(register.get('register_number') if german else identifier),
            register_court=scalar(register.get('register_court')) if german else None,
            register_type=scalar(register.get('register_type')) if german else None,
            provider='OpenRegister' if german else 'Companies House', retrieved_at=scalar(retrieved_at))
        checks = {
            'provider_identifier_matches': (identifier == selected_id if german else
                                            isinstance(identifier, str) and identifier.upper() == selected_id.upper()),
            'legal_name_matches': normalized(name) == normalized(request.company_name) and bool(name),
            'registration_number_present': bool(normalized(company.registration_number)),
        }
        if german:
            checks['register_court_present'] = bool(court(company.register_court))
        raw_country = raw.get('country')
        if raw_country is not None:
            checks['jurisdiction_matches'] = normalized(raw_country) in ({'de', 'deu', 'germany', 'deutschland'} if german else {'gb', 'gbr', 'uk', 'unitedkingdom'})
        for expected_number, expected_type, key in (
            (request.registration_number, request.register_type, 'requested_registration_matches'),
            (candidate.registration_number if candidate else None, candidate.register_type if candidate else None, 'search_registration_matches'),
        ):
            if expected_number:
                checks[key] = registration_matches(expected_number, company.registration_number, expected_type, company.register_type)
        if request.register_type:
            actual_type = normalized(company.register_type) or registration(company.registration_number)[0]
            checks['register_type_matches'] = actual_type == normalized(request.register_type)
        for expected_court, key in ((request.register_court, 'requested_court_matches'),
                                    (candidate.register_court if candidate else None, 'search_court_matches')):
            if expected_court:
                checks[key] = bool(company.register_court) and court(expected_court) == court(company.register_court)
        if not all(checks.values()):
            return result('verification_failed', 'Company details are incomplete or conflict with the requested identity.', company=company, checks=checks)
        reference = uuid.uuid4().hex
        original = {'company': raw} if german else {'profile': raw}
        evidence_company = {'country': request.jurisdiction, 'name': company.name, 'company_number': company.provider_company_id,
                            'register_number': company.registration_number, 'register_court': company.register_court,
                            'incorporated': raw.get('incorporated_at' if german else 'date_of_creation'), 'original_api_data': original}
        with self.lock:
            # Expired handles are removed opportunistically; no provider refresh.
            self.verified = {k: v for k, v in self.verified.items() if self.clock() - v[2] < self.verification_ttl}
            self.verified[reference] = (company, evidence_company, self.clock())
        return result('verified', 'Identity is consistent with the selected provider record and available registration details. This is not independent legal certification.',
                      verification_id=reference, company=company, checks=checks)

    def research(self, request):
        with self.lock:
            verified = self.verified.get(request.verification_id)
        if verified is None:
            raise ServiceError(409, 'verification_required', 'Verify the company before requesting research.')
        company, evidence_company, timestamp = verified
        if self.clock() - timestamp >= self.verification_ttl:
            raise ServiceError(409, 'verification_expired', 'The verification handle expired; verify again before research.')
        research = company_research.research_company(company.name, company.jurisdiction,
                    registration_number=company.registration_number, register_court=company.register_court)
        validation = validate_evidence(evidence_company, research)
        return ResearchResponse(verification_id=request.verification_id, company=company,
                                sources=validation['sources'], missing_evidence=validation['missing_evidence'],
                                coverage_note=research.get('coverage_note') or 'Search excerpts are unverified leads; coverage is incomplete.',
                                development=self.tracker.development)
