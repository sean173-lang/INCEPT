"""Minimal Phase 1 FastAPI facade. n8n owns sequencing, approvals and branches."""
import hmac
import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException

from scripts.service_schemas import ErrorResponse, ErrorDetail, ServiceError
from scripts.onboarding import OnboardingService, DEFAULT_DB
from scripts.onboarding_schemas import OnboardingRequest, OnboardingBundle
from scripts.natural_intake import EmailInquiry,ExtractionService
from scripts.payment_research import PaymentSourceRequest,verify_payment_source
from scripts.ai_synthesis import SynthesisRequest, SynthesisResponse, SynthesisService


def error_response(status, code, message, fields=None):
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, fields=fields or []))
    return JSONResponse(status_code=status, content=payload.model_dump())


def create_app(*, development=True, service_token=None, onboarding_db=DEFAULT_DB,
               ai_service=None, extraction_service=None, **_legacy_options):
    if not development and not service_token:
        raise ValueError('Live mode requires a service authentication token')
    extractor=extraction_service or ExtractionService()
    if extractor.config.enabled and not service_token:
        raise ValueError('Live extraction requires service authentication')
    synthesis=ai_service or SynthesisService()
    if synthesis.config.enabled and not service_token:
        raise ValueError('AI synthesis opt-in requires service authentication even in development')
    app = FastAPI(title='INCEPT German legal intake', version='0.3.0',
                  description='Authenticated Gmail inquiry extraction, official German source checks and lawyer-reviewed AI assessment.')
    onboarding = OnboardingService(onboarding_db)
    app.state.onboarding_service = onboarding
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
        known = {'body','message_id','sender','recipient','subject','client_name','counterparty','matter_summary',
                 'requested_assistance','alleged_facts','dates','monetary_amounts','supporting_documents_mentioned'}
        fields = sorted({'.'.join(str(p) if p in known else '<field>' for p in item['loc']) for item in error.errors()})
        return error_response(422, 'invalid_request', 'Request fields are invalid; consult the typed API schema.', fields)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request, error):
        return error_response(error.status_code, 'http_error', 'The requested HTTP operation is unavailable.')

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
    )


app = app_from_environment()
