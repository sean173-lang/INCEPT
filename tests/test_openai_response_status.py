"""Sanitized offline handling for OpenAI Responses API completion states."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from scripts.ai_synthesis import AIConfig, SynthesisService
from scripts.ai_synthesis_demo import requests_for_demo


FIXTURES=json.loads(Path('tests/fixtures/responses_api_statuses.json').read_text())


def ns(value):
    if isinstance(value,dict):return SimpleNamespace(**{k:ns(v) for k,v in value.items()})
    if isinstance(value,list):return [ns(v) for v in value]
    return value


def dump_ns(value):
    if isinstance(value,SimpleNamespace):return {k:dump_ns(v) for k,v in vars(value).items() if not callable(v)}
    if isinstance(value,list):return [dump_ns(v) for v in value]
    return value


class ResponsesStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.request=requests_for_demo(self.root/'db.sqlite3',self.root/'cache')['individual']

    def run_fixture(self,fixture,label):
        payload=ns(fixture)
        usage=payload.usage
        if usage is not None:payload.usage.model_dump=lambda:dump_ns(payload.usage)
        client=MagicMock();client.__enter__.return_value=client
        client.responses.create.return_value=payload
        http=MagicMock();http.__enter__.return_value=object()
        config=AIConfig(enabled=True,model='gpt-4o-mini',max_input_tokens=100000,max_output_tokens=8000,timeout=45)
        service=SynthesisService(config,ledger_path=self.root/(label+'.sqlite3'))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}),patch('openai.OpenAI',return_value=client),patch('httpx.Client',return_value=http):
            result=service.run(self.request)
        return result,client

    def test_completed_response_preserves_text_and_usage(self):
        f=ns(FIXTURES['completed']);f.usage.model_dump=lambda:dump_ns(f.usage)
        client=MagicMock();client.__enter__.return_value=client;client.responses.create.return_value=f
        http=MagicMock();http.__enter__.return_value=object()
        service=SynthesisService(AIConfig(enabled=True,model='gpt-4o-mini',max_output_tokens=8000),ledger_path=self.root/'done.sqlite3')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}),patch('openai.OpenAI',return_value=client),patch('httpx.Client',return_value=http):
            text,usage=service.openai_call({'contract_version':'2.0','context':{},'sources':{},'excerpts':{},'issue_support':{}})
        self.assertEqual(text,'{}');self.assertEqual(usage['output_tokens'],40)
        self.assertEqual(client.responses.create.call_args.kwargs['max_output_tokens'],8000)

    def test_environment_override_sets_synthesis_cap_to_8000(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key','INCEPT_AI_LIVE_ENABLED':'1',
                                   'INCEPT_AI_MODEL':'gpt-4o-mini','INCEPT_AI_MAX_OUTPUT_TOKENS':'8000'}):
            config=AIConfig.from_environment()
        self.assertEqual(config.max_output_tokens,8000)

    def test_incomplete_failed_refused_and_unexpected_statuses_are_distinguished(self):
        expected={
            'incomplete_max_output':('incomplete','max_output_tokens',False,8000),
            'failed':('failed',None,False,0),
            'refused':('refused',None,True,10),
            'unexpected':('unexpected',None,False,None),
        }
        for key,(status,reason,refused,tokens) in expected.items():
            with self.subTest(key=key):
                result,client=self.run_fixture(FIXTURES[key],key)
                self.assertEqual(result.status,'unavailable')
                self.assertEqual(result.provider_response_status,status)
                self.assertEqual(result.provider_incomplete_reason,reason)
                self.assertEqual(result.provider_refusal,refused)
                self.assertEqual((result.usage or {}).get('output_tokens'),tokens)
                if key=='incomplete_max_output':self.assertEqual(result.usage['output_tokens_details']['reasoning_tokens'],0)
                self.assertFalse(result.model_used)
                self.assertIsNone(result.synthesis)
                if key=='failed':
                    self.assertEqual(result.provider_error_code,'server_error')
                    self.assertEqual(result.provider_error_message,'Provider response failed; message withheld.')
                log=self.root/'validation_diagnostics.jsonl'
                row=json.loads(log.read_text().splitlines()[-1])
                self.assertEqual(row['provider_status'],status)
                self.assertNotIn('Sanitized fixture message',json.dumps(row))
                if key=='failed':self.assertEqual(row['provider_error_code'],'server_error')
                self.assertEqual(result.output_token_limit,8000)


if __name__=='__main__':unittest.main()
