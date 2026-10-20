import io,json,os,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from quiet_sentinel.core import Sentinel

class ProviderTests(unittest.TestCase):
 def test_openai(self):
  result={'output':[{'type':'message','content':[{'type':'output_text','text':'Check CPU processes.'}]}]}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}), patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as call:
   s=Sentinel(provider='openai',model='test-model')
   self.assertEqual(s.assess(None,[22],'CPU high'),'Check CPU processes.')
   req=call.call_args.args[0]
   self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
   self.assertFalse(json.loads(req.data)['store'])
   self.assertNotIn('test-only',json.dumps(s.snapshot()))
 def test_quota_failure(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch('urllib.request.urlopen',side_effect=HTTPError('url',429,'quota',{},None)):
   s=Sentinel(provider='openai')
   self.assertIn('Monitoring continues',s.assess(None,[],'test'))
   self.assertEqual(s.ai_status,'http_429')
 def test_missing_key(self):
  with patch.dict(os.environ,{},clear=True),patch('urllib.request.urlopen') as call:
   s=Sentinel(provider='openai');s.assess(None,[],'test');call.assert_not_called()
   self.assertEqual(s.ai_status,'missing_key')
 def test_ollama(self):
  with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"response":"Check logs."}')):
   self.assertEqual(Sentinel().assess(None,[],'test'),'Check logs.')
 def test_cpu_guard_and_cooldown(self):
  s=Sentinel()
  for v in [3,3,3,3,3]:s.observe('host','cpu_percent',v)
  self.assertEqual(s.observe('host','cpu_percent',4)['state'],'normal')
  self.assertEqual(s.observe('host','cpu_percent',97)['state'],'alert')
  self.assertEqual(s.observe('host','cpu_percent',98)['state'],'suppressed')
