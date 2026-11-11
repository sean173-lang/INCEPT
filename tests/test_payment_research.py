from datetime import datetime,timezone
from offline_support import OfflineTestCase
from scripts.payment_research import PaymentSourceRequest,verify_payment_source,CORPUS
from scripts.local_rag import LocalRAG

class PaymentResearchTests(OfflineTestCase):
 def request(self,number='611'):
  card=next(c for c in LocalRAG(CORPUS).chunks.values() if c['id']=='payment-bgb-'+number)
  return PaymentSourceRequest(synthetic_data=True,provision=number,source_url=card['source_url'],retrieved_at=datetime.now(timezone.utc).isoformat(),http_status=200,source_html='<h1>§ '+number+'</h1><div class="jurAbsatz">'+card['text']+'</div>')
 def test_relevant_service_performance_and_acceptance_rules_have_exact_sources(self):
  for n in ('611','320','641'):
   result=verify_payment_source(self.request(n));self.assertEqual(result['status'],'wording_verified');self.assertFalse(result['case_finding_verified']);self.assertIsNone(result['confirmed_deadline'])
 def test_wrong_source_changed_wording_http_failure_and_future_date(self):
  for change in ({'source_url':'https://example.invalid'},{'source_html':'<h1>§ 286</h1>not applicable'},{'http_status':503}):
   self.assertEqual(verify_payment_source(self.request().model_copy(update=change))['status'],'unavailable')
  with self.assertRaises(ValueError):verify_payment_source(self.request().model_copy(update={'retrieved_at':'2099-01-01T00:00:00+00:00'}))
 def test_original_declared_charset_bytes_preserved_and_lossy_text_rejected(self):
  import base64
  req=self.request();html='<meta charset="iso-8859-1">'+req.source_html
  response=verify_payment_source(req.model_copy(update={'source_html':'','source_bytes_base64':base64.b64encode(html.encode('iso-8859-1')).decode()}))
  self.assertEqual(response['status'],'wording_verified');self.assertEqual(response['source_encoding'],'iso8859-1')
  with self.assertRaises(ValueError):verify_payment_source(req.model_copy(update={'source_html':req.source_html+'\ufffd'}))
 def test_workflow_reuses_existing_binary_transport_for_official_sources(self):
  from scripts.incept_prose_workflow import build_workflow
  nodes={n['name']:n for n in build_workflow()['nodes']}
  for provision in ('611','320','641'):
   response=nodes['Retrieve Official BGB '+provision]['parameters']['options']['response']['response']
   self.assertEqual(response['responseFormat'],'file');self.assertEqual(response['outputPropertyName'],'official_source')
   code=nodes['Prepare Source Check '+provision]['parameters']['jsCode']
   self.assertIn('getBinaryDataBuffer',code);self.assertIn('source_bytes_base64',code)
