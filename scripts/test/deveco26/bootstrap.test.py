#!/usr/bin/env python3
"""准备链真实流/文件测试；无网络或挂载副作用。"""
from unittest.mock import patch
import subprocess,os
import importlib.util,unittest,tempfile,io,hashlib,zipfile,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
class Bootstrap(unittest.TestCase):
 def setUp(self):
  s=importlib.util.spec_from_file_location('bootstrap',HERE/'bootstrap.py');self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m);self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
 def test_common_is_required_dependency(self):
  p=json.loads((HERE/'cli/package.json').read_text())
  self.assertEqual(p['dependencies'].get('@deveco/deveco-cli-common'),'1.3.4')
 def test_stream_complete_and_cache(self):
  p=self.root/'data';h=hashlib.sha256(b'abcd').hexdigest();self.m.copy_checked(io.BytesIO(b'abcd'),p,4,h);self.assertEqual(p.read_bytes(),b'abcd')
 def test_stream_truncated_or_overlong(self):
  for data in [b'abc',b'abcde']:
   p=self.root/'data'
   with self.assertRaises(ValueError):self.m.copy_checked(io.BytesIO(data),p,4,hashlib.sha256(b'abcd').hexdigest())
   self.assertFalse(p.exists())
 def test_stream_wrong_hash(self):
  with self.assertRaises(ValueError):self.m.copy_checked(io.BytesIO(b'abcd'),self.root/'data',4,'0'*64)
 def test_url_only_exact_vendor_origin(self):
  allowed='https://vendor.test/path/file.zip';self.m.validate_url(allowed+'?signature=hidden',allowed)
  for u in ['http://vendor.test/path/file.zip','https://evil.test/path/file.zip','https://vendor.test/other','https://user:pass@vendor.test/path/file.zip']:
   with self.assertRaises(ValueError):self.m.validate_url(u,allowed)
 def test_resource_check(self):
  self.m.check_space(12000,4000,4000,3000)
  with self.assertRaises(ValueError):self.m.check_space(10000,4000,4000,3000)
 def test_missing_url_fails_before_request(self):
  with self.assertRaises(ValueError):self.m.validate_url('', 'https://vendor.test/file.zip')
 def test_dmg_zip_exact_member(self):
  p=self.root/'in.zip';data=b'dmg';name='folder/a.dmg';lock={'member':name,'bytes':3,'sha256':hashlib.sha256(data).hexdigest()}
  with zipfile.ZipFile(p,'w') as z:z.writestr(name,data)
  self.m.extract_dmg(p,self.root/'out.dmg',lock);self.assertEqual((self.root/'out.dmg').read_bytes(),data)
 def test_dmg_zip_duplicate_rejected(self):
  p=self.root/'in.zip';name='folder/a.dmg';lock={'member':name,'bytes':3,'sha256':hashlib.sha256(b'dmg').hexdigest()}
  with zipfile.ZipFile(p,'w') as z:z.writestr(name,b'dmg');z.writestr(name,b'dmg')
  with self.assertRaises(ValueError):self.m.extract_dmg(p,self.root/'out.dmg',lock)
 def test_http_expired_error_is_sanitized(self):
  self.assertEqual(self.m.failure_record(ValueError('https://host/file?secret=LEAK')),{'passed':False,'errorType':'ValueError','formalArtifactAllowed':False})
 def test_http_status_and_phase_without_url(self):
  import urllib.error
  e=urllib.error.HTTPError('https://vendor.test/file?secret=LEAK',403,'secret=LEAK',{},None)
  r=self.m.failure_record(e,'download');self.assertEqual(r['httpStatus'],403);self.assertEqual(r['phase'],'download');self.assertNotIn('LEAK',json.dumps(r))
 def test_timeout_without_exception_text(self):
  r=self.m.failure_record(TimeoutError('https://vendor.test/?secret=LEAK'),'download');self.assertTrue(r['timedOut']);self.assertFalse(r['passed']);self.assertNotIn('LEAK',json.dumps(r))
 def cleanup_fixture(self):
  out=self.root/'out';mount=out/'environment/mounted';mount.mkdir(parents=True);(out/'environment/paths.json').write_text('{}');return out,mount
 def test_cleanup_stops_owned_daemon_before_unmount(self):
  out,mount=self.cleanup_fixture();calls=[]
  with patch.object(self.m.os.path,'ismount',side_effect=[True,False]),patch.object(self.m,'verify_cleanup_tools',create=True),patch.object(self.m,'run_command',side_effect=lambda args,*rest:calls.append([str(x) for x in args])):
   self.m.cleanup(out)
  self.assertEqual(calls[0][-1],'--stop-daemon');self.assertEqual(calls[1][0],'hdiutil');self.assertEqual(calls[1][1],'detach')
 def test_cleanup_unmount_failure_stays_failed(self):
  out,mount=self.cleanup_fixture()
  def command(args,*rest):
   if args[0]=='hdiutil':raise ValueError('busy')
  with patch.object(self.m.os.path,'ismount',return_value=True),patch.object(self.m,'verify_cleanup_tools',create=True),patch.object(self.m,'run_command',side_effect=command):
   with self.assertRaises(ValueError):self.m.cleanup(out)
 def test_cleanup_waits_past_transient_busy(self):
  out,mount=self.cleanup_fixture();work=out/'work';work.mkdir();detaches=[]
  def command(args,w,name,timeout,*rest):
   if args[0]!='hdiutil':return ''
   detaches.append(name);(w/(name+'.log')).write_text('Resource busy' if len(detaches)==1 else 'detached')
   if len(detaches)==1:
    error=getattr(self.m,'CommandFailure',None)
    raise error(name,16) if error else ValueError('Resource busy')
   return ''
  with patch.object(self.m.os.path,'ismount',side_effect=[True,False]),patch.object(self.m,'verify_cleanup_tools'),patch.object(self.m,'run_command',side_effect=command):self.m.cleanup(out)
  self.assertEqual(len(detaches),2)
 def test_detach_busy_then_success(self):
  work=self.root/'work';work.mkdir();calls=[]
  def command(args,w,name,timeout,*rest):
   calls.append(name);(w/(name+'.log')).write_text('资源忙' if len(calls)==1 else 'detached')
   if len(calls)==1:raise self.m.CommandFailure(name,16)
   return ''
  with patch.object(self.m,'run_command',side_effect=command):self.m.detach_bounded(self.root/'mounted',work,deadline=self.m.time.monotonic()+1)
  self.assertEqual(calls,['unmount-01','unmount-02'])
 def test_detach_persistent_busy_rejected(self):
  work=self.root/'work';work.mkdir();calls=[]
  def command(args,w,name,timeout,*rest):
   calls.append(name);(w/(name+'.log')).write_text('Resource busy');raise self.m.CommandFailure(name,16)
  with patch.object(self.m,'run_command',side_effect=command):
   with self.assertRaises(self.m.CommandFailure):self.m.detach_bounded(self.root/'mounted',work,deadline=self.m.time.monotonic()+2)
  self.assertEqual(len(calls),5)
 def test_detach_nonbusy_not_retried(self):
  work=self.root/'work';work.mkdir();calls=[]
  def command(args,w,name,timeout,*rest):
   calls.append(name);(w/(name+'.log')).write_text('not permitted');raise self.m.CommandFailure(name,1)
  with patch.object(self.m,'run_command',side_effect=command):
   with self.assertRaises(self.m.CommandFailure):self.m.detach_bounded(self.root/'mounted',work,deadline=self.m.time.monotonic()+2)
  self.assertEqual(len(calls),1)
 def test_command_timeout_keeps_evidence(self):
  work=self.root/'work';work.mkdir()
  with patch.object(self.m.subprocess,'run',side_effect=subprocess.TimeoutExpired('hdiutil',1,output=b'waiting')):
   with self.assertRaises(subprocess.TimeoutExpired):self.m.run_command(['hdiutil'],work,'timeout-attempt',1)
  record=json.loads((work/'timeout-attempt.json').read_text());self.assertTrue(record['timedOut']);self.assertIsNone(record['exit']);self.assertEqual((work/'timeout-attempt.log').read_text(),'waiting')
 def test_owned_wait_timeout_and_permission(self):
  with patch.object(self.m,'pid_alive',return_value=True):
   with self.assertRaises(TimeoutError):self.m.wait_owned_pids([12],self.m.time.monotonic())
  with patch.object(self.m.os,'kill',side_effect=PermissionError):
   with self.assertRaises(PermissionError):self.m.pid_alive(12)
 def test_stopped_pid_must_match_owned_registry(self):
  self.assertEqual(self.m.stopped_pids('Stopped daemon pid 12.',{12}),[12])
  with self.assertRaises(ValueError):self.m.stopped_pids('Stopped daemon pid 13.',{12})
if __name__=='__main__':unittest.main()
