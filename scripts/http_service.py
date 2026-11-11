"""Minimal Phase 1 FastAPI facade. n8n owns sequencing, approvals and branches."""
import hmac
import os
from pathlib import Path

import requests
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException

from scripts.api_usage import (ApprovalRequired, BudgetExceeded, DuplicateRequestBlocked,
                               UsageBlocked, UsageTracker, use_tracker)
from scripts.company_service import CompanyService, ServiceError
from scripts.research_pipeline import ResearchPipeline
from scripts.research_schemas import (RetrievalRequest, RetrievalResponse, CreateResearchRun,
                                      RunPlan, ToolRequest, ResearchReport)
from scripts.service_schemas import (CompanyInput, VerificationRequest, ResearchRequest, SearchResponse,
                                     VerificationResponse, ResearchResponse, ErrorResponse, ErrorDetail, UsageResponse)
from scripts.onboarding import OnboardingService, DEFAULT_DB
from scripts.onboarding_schemas import OnboardingRequest, OnboardingBundle
from scripts.natural_intake import EmailInquiry,ExtractionService
from scripts.payment_research import PaymentSourceRequest,verify_payment_source
from scripts.ai_synthesis import SynthesisRequest, SynthesisResponse, SynthesisService
from scripts.primary_research import PrimaryResearchRequest, PrimaryResearchResult, verify_research
from scripts.corporate_intelligence import CorporateIntelligence, CorporateRequest, CorporateResult


def error_response(status, code, message, fields=None):
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, fields=fields or []))
    return JSONResponse(status_code=status, content=payload.model_dump())


def create_app(*, development=True, service_token=None, allow_paid=False,
               max_openregister_credits=50, max_tavily_searches=5, max_session_spend=None,
               prices=None, currency='EUR', cache_dir='data/api_cache', ledger_path='data/api_usage.jsonl',
               verification_ttl=900, onboarding_db=DEFAULT_DB, corporate_cache_dir='data/api_cache', ai_service=None, extraction_service=None):
    if not development and not service_token:
        raise ValueError('Live mode requires a service authentication token')
    extractor=extraction_service or ExtractionService()
    if extractor.config.enabled and not service_token:
        raise ValueError('Live extraction requires service authentication')
    synthesis=ai_service or SynthesisService(corporate_cache_dir=corporate_cache_dir,allow_demo=development)
    if synthesis.config.enabled and not service_token:
        raise ValueError('AI synthesis opt-in requires service authentication even in development')
    tracker = UsageTracker(approved=allow_paid, development=development,
                           max_openregister_credits=max_openregister_credits, max_tavily_searches=max_tavily_searches,
                           max_session_spend=max_session_spend, prices=prices, currency=currency,
                           cache_dir=cache_dir, ledger_path=ledger_path)
    service = CompanyService(tracker, verification_ttl=verification_ttl)
    app = FastAPI(title='INCEPT intake and corporate services', version='0.2.0',
                  description='Company services and bounded local research tools for n8n. Development fixtures by default.')
    app.state.tracker = tracker
    app.state.company_service = service
    pipeline = ResearchPipeline(service)
    app.state.research_pipeline = pipeline
    onboarding = OnboardingService(onboarding_db)
    app.state.onboarding_service = onboarding
    corporate_intelligence=CorporateIntelligence(corporate_cache_dir,allow_demo=development)
    app.state.ai_synthesis=synthesis
    auth_header = APIKeyHeader(name='X-LEGALFLOW-Service-Key', auto_error=False)

    def authorize(key: str | None = Depends(auth_header)):
        if service_token and (not key or not hmac.compare_digest(key.encode(), service_token.encode())):
            raise ServiceError(401, 'service_authentication_required', 'Valid service authentication is required.')

    @app.exception_handler(ServiceError)
    async def service_error_handler(request, error):
        return error_response(error.status_code, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, error):
        # FastAPI normally includes submitted values in errors. Do not reflect
        # tokens or arbitrary request data back to the caller.
        known = {'body', 'company_name', 'jurisdiction', 'provider_company_id', 'registration_number',
                 'register_court', 'register_type', 'verification_id'}
        fields = sorted({'.'.join(str(p) if p in known else '<field>' for p in item['loc']) for item in error.errors()})
        return error_response(422, 'invalid_request', 'Request fields are invalid; consult the typed API schema.', fields)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request, error):
        return error_response(error.status_code, 'http_error', 'The requested HTTP operation is unavailable.')

    def execute(call):
        try:
            with use_tracker(tracker):
                return call()
        except ServiceError:
            raise
        except ApprovalRequired:
            raise ServiceError(403, 'approval_required', 'Paid cache misses require server-side approval; request bodies cannot authorize spending.') from None
        except BudgetExceeded:
            raise ServiceError(429, 'budget_exceeded', 'The configured budget blocks this operation, including unknown costs under a finite spending cap.') from None
        except DuplicateRequestBlocked:
            raise ServiceError(409, 'duplicate_request_blocked', 'A previous attempt is failed or uncertain; no automatic retry was made.') from None
        except UsageBlocked:
            raise ServiceError(403, 'operation_blocked', 'The operation is not permitted by the usage policy.') from None
        except Exception as error:
            status = getattr(error, 'status_code', None)
            if status is None:
                status = getattr(getattr(error, 'response', None), 'status_code', None)
            if status == 429:
                raise ServiceError(502, 'provider_rate_limited', 'The provider rate-limited the request; do not automatically retry paid operations.') from None
            if status in (401, 403):
                raise ServiceError(502, 'provider_access_failed', 'Provider authentication or permissions failed; contact the service operator.') from None
            if status == 404:
                raise ServiceError(502, 'provider_resource_not_found', 'The provider did not return the requested resource.') from None
            names = {cls.__name__ for cls in type(error).__mro__}
            if isinstance(error, requests.exceptions.Timeout) or names & {'APITimeoutError', 'TimeoutException'}:
                raise ServiceError(504, 'provider_timeout', 'Provider request timed out; completion and billing may be uncertain.') from None
            if isinstance(error, requests.exceptions.ConnectionError) or names & {'APIConnectionError', 'NetworkError'}:
                raise ServiceError(502, 'provider_connection_failed', 'Provider connection failed; no retry was made.') from None
            raise ServiceError(502, 'provider_operation_failed', 'The provider operation could not be completed or its response was unsupported.') from None

    errors = {status: {'model': ErrorResponse} for status in (401, 403, 409, 422, 429, 502, 504)}

    @app.get('/health')
    def health():
        return {'status': 'ok', 'development': development}

    @app.post('/v1/onboarding/preview', response_model=OnboardingBundle,
              dependencies=[Depends(authorize)], responses={**errors,503:{'model':ErrorResponse}})
    def onboarding_preview(request: OnboardingRequest):
        if not development and request.synthetic_data:
            raise ServiceError(403,'synthetic_fixture_blocked','Live services do not accept synthetic intake fixtures.')
        return onboarding.preview(request)

    @app.post('/v1/onboarding/assessment', response_model=OnboardingBundle,
              dependencies=[Depends(authorize)], responses={**errors,503:{'model':ErrorResponse}})
    def onboarding_assessment(request: OnboardingRequest):
        if not development and request.synthetic_data:
            raise ServiceError(403,'synthetic_fixture_blocked','Live services do not accept synthetic intake fixtures.')
        return onboarding.assess(request)

    @app.post('/v1/onboarding/extract',dependencies=[Depends(authorize)],responses=errors)
    def extract_natural_inquiry(request: EmailInquiry):
        return extractor.run(request)

    @app.post('/v1/onboarding/payment-research/verify',dependencies=[Depends(authorize)],responses=errors)
    def payment_research(request: PaymentSourceRequest):
        try:
            return verify_payment_source(request)
        except ValueError:
            raise ServiceError(422,'invalid_research_metadata','Source retrieval metadata could not be validated.') from None

    @app.post('/v1/onboarding/synthesis', response_model=SynthesisResponse,
              dependencies=[Depends(authorize)], responses=errors)
    def mandate_synthesis(request: SynthesisRequest):
        if not development and request.bundle.synthetic_data:
            raise ServiceError(403,'synthetic_fixture_blocked','Live services do not accept synthetic intake fixtures.')
        return synthesis.run(request)

    @app.post('/v1/onboarding/corporate-intelligence',response_model=CorporateResult,
              dependencies=[Depends(authorize)],responses=errors)
    def corporate_client_intelligence(request: CorporateRequest):
        return corporate_intelligence.collect(request)

    @app.post('/v1/onboarding/research/verify',response_model=PrimaryResearchResult,
              dependencies=[Depends(authorize)],responses=errors)
    def verify_primary_research(request: PrimaryResearchRequest):
        if not development:
            raise ServiceError(403,'development_required','Primary-source verification supports synthetic development intake only.')
        try:
            result=verify_research(request)
            return synthesis.resolver.record_primary(result,request.bundle)
        except ValueError:
            raise ServiceError(422,'research_context_mismatch','Research source and bundle context could not be validated.') from None

    @app.post('/v1/company/search', response_model=SearchResponse, dependencies=[Depends(authorize)], responses=errors)
    def search(request: CompanyInput):
        return execute(lambda: service.search(request))

    @app.post('/v1/company/verify', response_model=VerificationResponse, dependencies=[Depends(authorize)], responses=errors)
    def verify(request: VerificationRequest):
        return execute(lambda: service.verify(request))

    @app.post('/v1/research/search', response_model=ResearchResponse, dependencies=[Depends(authorize)], responses=errors)
    def research(request: ResearchRequest):
        return execute(lambda: service.research(request))

    @app.post('/v1/rag/query', response_model=RetrievalResponse, dependencies=[Depends(authorize)], responses=errors)
    def rag_query(request: RetrievalRequest):
        return execute(lambda: pipeline.retrieve(request))

    @app.post('/v1/research/runs', response_model=RunPlan, dependencies=[Depends(authorize)], responses=errors)
    def create_research_run(request: CreateResearchRun):
        return execute(lambda: pipeline.create(request))

    @app.post('/v1/research/runs/{run_id}/plan', response_model=RunPlan, dependencies=[Depends(authorize)], responses=errors)
    def research_plan(run_id: str):
        return execute(lambda: pipeline.plan(run_id))

    @app.post('/v1/research/runs/{run_id}/tools', response_model=RunPlan, dependencies=[Depends(authorize)], responses=errors)
    def research_tool(run_id: str, request: ToolRequest):
        return execute(lambda: pipeline.step(run_id, request))

    @app.post('/v1/research/runs/{run_id}/report', response_model=ResearchReport, dependencies=[Depends(authorize)], responses=errors)
    def research_report(run_id: str):
        return execute(lambda: pipeline.report(run_id))

    @app.get('/v1/usage', response_model=UsageResponse, dependencies=[Depends(authorize)])
    def usage():
        with tracker.lock:
            return tracker.summary()

    return app


def app_from_environment():
    """Fail-closed opt-ins; never edit .env or let HTTP callers change policy."""
    # The local launcher and n8n process use the repository's ignored .env;
    # load it before constructing any provider clients. Existing process values
    # take precedence, and no credential is returned by this function.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    mode = os.getenv('LEGALFLOW_SERVICE_MODE', 'development')
    if mode not in ('development', 'live'):
        raise ValueError('LEGALFLOW_SERVICE_MODE must be development or live')
    return create_app(
        development=mode == 'development', service_token=os.getenv('LEGALFLOW_SERVICE_TOKEN'),
        allow_paid=os.getenv('LEGALFLOW_SERVICE_ALLOW_PAID', '0') == '1',
        max_openregister_credits=int(os.getenv('LEGALFLOW_SERVICE_MAX_OR_CREDITS', '50')),
        max_tavily_searches=int(os.getenv('LEGALFLOW_SERVICE_MAX_TAVILY_SEARCHES', '5')),
        max_session_spend=os.getenv('LEGALFLOW_SERVICE_MAX_SPEND'),
    )


app = app_from_environment()
