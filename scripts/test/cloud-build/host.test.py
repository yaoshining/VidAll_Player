#!/usr/bin/env python3
"""完整旧native检查集合/真实命令失败传播，不冒充设备执行。"""
import importlib.util,unittest,tempfile,json,sys
from pathlib import Path
P=Path(__file__).with_name('host.py')
def module():
 s=importlib.util.spec_from_file_location('cloudhost',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Tests(unittest.TestCase):
 def test_inventory_exact(self):
  m=module();names=list(m.EXPECTED)
  self.assertTrue(m.test_inventory({'tests':[{'name':n} for n in names]}))
  for bad in [names[:-1],names+[names[0]],names+['extra']]:
   with self.assertRaises(ValueError):m.test_inventory({'tests':[{'name':n} for n in bad]})
 def test_actual_commands_fail_closed(self):
  m=module()
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);rows=[]
   self.assertIn('OK',m.command('normal',[sys.executable,'-c','print("OK")'],out,dict(),out,rows,5))
   with self.assertRaises(RuntimeError):m.command('failure',[sys.executable,'-c','print("actual failure");exit(7)'],out,dict(),out,rows,5)
   self.assertEqual(rows[-1]['exit'],7);self.assertIn('actual failure',(out/'failure.log').read_text())
 def test_proof_missing_wrong_source_cases(self):
  m=module();src={'checkoutSHA':'a'*40,'treeSHA':'b'*40,'trackedBytesSHA256':'c'*64};r={'passed':True,'sourceBefore':src,'sourceAfter':src,'ctestNames':sorted(m.EXPECTED),'ctestPassed':14,'diagnosticsJS':['diagnostics-session','diagnostics-device']}
  self.assertTrue(m.proof(r,src))
  for key in r:
   b=dict(r);b.pop(key);self.assertFalse(m.proof(b,src),key)
if __name__=='__main__':unittest.main()
