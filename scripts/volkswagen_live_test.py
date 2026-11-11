"""Separate loopback-only service/CLI for one fixed, explicitly approved test.

No module-level app or server is started on import. Supported launch binds only
127.0.0.1:8001 and cannot change the existing development service/workflow.
"""
import argparse
import json
from pathlib import Path
import sqlite3

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException

from scripts.volkswagen_profile import ProfileError, STATE_DIR
from scripts.volkswagen_continuation import VolkswagenContinuation, DIRECT_ACK

ACKNOWLEDGEMENT = 'Volkswagen AG | Germany | Amtsgericht Braunschweig | HRB 100484 | 15 credits'


class EmptyRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


def failure(status, code, message):
    return JSONResponse(status_code=status,content={'status':'blocked','error':{'code':code,'message':message},'provider_retries':False})


def create_app(*, enable_live_test=False, directory=STATE_DIR, config=None, cache_dir=None, transport=None, clock=None):
    kwargs={'directory':directory,'cache_dir':cache_dir,'transport':transport}
    if config is not None:kwargs['config']=config
    if clock is not None:kwargs['clock']=clock
    profile=VolkswagenContinuation(**kwargs)
    app=FastAPI(title='Isolated Volkswagen register test',version='0.1.0')
    app.state.profile=profile
    approval_header=APIKeyHeader(name='X-LEGALFLOW-Test-Approval',auto_error=False)

    @app.middleware('http')
    async def loopback_only(request:Request,call_next):
        if request.client is None or request.client.host not in ('127.0.0.1','::1'):
            return failure(403,'loopback_required','This service accepts loopback clients only.')
        return await call_next(request)

    @app.exception_handler(ProfileError)
    async def profile_error(request,error):
        return failure(error.status,error.code,error.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        return failure(422,'invalid_request','No company, tool, endpoint, approval or budget overrides are accepted in the request body.')

    @app.exception_handler(HTTPException)
    async def http_error(request,error):
        return failure(error.status_code,'operation_unavailable','This isolated profile does not expose that operation.')

    @app.exception_handler(sqlite3.Error)
    async def database_error(request,error):
        return failure(503,'ledger_unavailable','Persistent state could not be validated; requests are blocked.')

    @app.get('/health')
    def health():
        return {'status':'ok','profile':'volkswagen-register-test-v1','live_test_enabled':enable_live_test,
                'loopback_port':8001,'financials_enabled':False,'other_providers_enabled':False}

    @app.get('/v1/volkswagen/status')
    def status():
        return profile.status()

    @app.get('/v1/volkswagen/result')
    def result():
        return profile.result() or {'status':'not_completed'}

    @app.get('/v1/volkswagen/preview')
    def preview():
        return profile.preview()

    @app.post('/v1/volkswagen/verify')
    def verify(request:EmptyRequest,approval:str|None=Depends(approval_header)):
        if not enable_live_test:
            raise ProfileError('live_test_disabled','Start this separate service with --enable-live-test before executing an approved test.',403)
        return profile.verify(approval)

    @app.get('/v1/volkswagen/direct-detail/result')
    def direct_result():
        return profile.direct_result()

    @app.post('/v1/volkswagen/direct-detail/verify')
    def verify_direct(request:EmptyRequest,approval:str|None=Depends(approval_header)):
        if not enable_live_test:
            raise ProfileError('live_test_disabled','The separate live-test service must be explicitly enabled.',403)
        return profile.verify_direct(approval)

    return app


def main():
    parser=argparse.ArgumentParser(description='Isolated Volkswagen test; no paid calls except explicitly approved verify')
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve')
    serve.add_argument('--enable-live-test',action='store_true',help='Enable only the isolated fixed-scope verification endpoint, not automatic execution')
    approve=commands.add_parser('approve')
    approve.add_argument('--acknowledge',required=True,help='Exact fixed-scope acknowledgement; writes a local one-test approval artifact, no API call')
    direct=commands.add_parser('approve-direct')
    direct.add_argument('--acknowledge',required=True)
    commands.add_parser('verify-direct')
    commands.add_parser('direct-result')
    commands.add_parser('status')
    commands.add_parser('preview')
    commands.add_parser('verify')
    args=parser.parse_args()
    try:
        if args.command=='serve':
            import uvicorn
            uvicorn.run(create_app(enable_live_test=args.enable_live_test),host='127.0.0.1',port=8001,workers=1,
                        proxy_headers=False,access_log=False)
        elif args.command=='approve':
            print(json.dumps(VolkswagenContinuation().approve(args.acknowledge),indent=2))
        elif args.command=='approve-direct':
            print(json.dumps(VolkswagenContinuation().approve_direct(args.acknowledge),indent=2))
        elif args.command=='direct-result':
            print(json.dumps(VolkswagenContinuation().direct_result(),indent=2))
        elif args.command=='status':
            print(json.dumps(VolkswagenContinuation().status(),indent=2))
        elif args.command=='preview':
            print(json.dumps(VolkswagenContinuation().preview(),indent=2))
        else:
            # One local HTTP request. The approval nonce never appears in argv,
            # stdout, URLs or environment; provider credentials stay in Python.
            import requests
            direct=args.command=='verify-direct'
            nonce=(STATE_DIR/('direct-approval.local' if direct else 'approval.local')).read_text().strip()
            endpoint='/v1/volkswagen/direct-detail/verify' if direct else '/v1/volkswagen/verify'
            with requests.Session() as session:
                session.trust_env=False
                session.mount('http://',requests.adapters.HTTPAdapter(max_retries=0))
                response=session.post('http://127.0.0.1:8001'+endpoint,json={},
                                      headers={'X-LEGALFLOW-Test-Approval':nonce},timeout=75,allow_redirects=False)
                if response.status_code==200:
                    result=response.json()
                    print(json.dumps(result,indent=2))
                    if result.get('status')!='verified':
                        raise SystemExit(1)
                else:
                    print(json.dumps({'status':'blocked','http_status':response.status_code,'message':'Inspect the local profile status. No automatic retry was made.'}))
    except ProfileError as error:
        print(json.dumps({'status':'blocked','error':{'code':error.code,'message':error.message}}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status':'blocked','message':'The isolated profile could not complete. Inspect persistent state before any further action; no automatic retry was made.'}))
        raise SystemExit(1)


if __name__=='__main__':
    main()
