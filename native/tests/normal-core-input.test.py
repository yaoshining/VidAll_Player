#!/usr/bin/env python3
"""对实际接入清单运行正例及篡改/遗漏负例。"""
import importlib.util,json,tempfile,unittest,copy,shutil,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/audit/normal-core-verify.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
BASE=ROOT/'release/inputs/004-normal-core'
class BindingTests(unittest.TestCase):
 def test_actual_current_inputs(self):self.assertEqual(audit.verify(BASE),[])
 def mutated(self,change):
  d=json.loads((BASE/'manifest.json').read_text());change(d)
  return audit.verify(BASE,d)
 def test_missing_manifest(self):
  with tempfile.TemporaryDirectory() as t:self.assertIn('清单缺失',audit.verify(Path(t)))
 def test_wrong_library(self):self.assertTrue(self.mutated(lambda d:d['libraries'][0].update(sha256='0'*64)))
 def test_missing_library(self):self.assertTrue(self.mutated(lambda d:d['libraries'].pop()))
 def test_fault_macro(self):self.assertTrue(self.mutated(lambda d:d['compileDefinitions'].append('MP_OHCODEC_DIAGNOSTIC=1')))
 def test_missing_abi(self):self.assertTrue(self.mutated(lambda d:d['requiredExports']['libmpv.so'].append('mpv_missing_api_999')))
 def test_changed_header(self):self.assertTrue(self.mutated(lambda d:d['headers'][0].update(sha256='0'*64)))
 def test_formal_not_allowed(self):self.assertTrue(self.mutated(lambda d:d.update(formalArtifactAllowed=True)))
 def test_empty_abi(self):self.assertTrue(self.mutated(lambda d:d['requiredExports'].update({'libmpv.so':[]})))
 def test_claim_only_macro(self):self.assertTrue(self.mutated(lambda d:d.update(compileEvidence='README.md')))
 def changed_file(self,name,change):
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp)/'inputs';shutil.copytree(BASE,target,copy_function=os.symlink)
   p=target/name;d=json.loads(p.read_text());p.unlink();change(d);p.write_text(json.dumps(d))
   m=json.loads((BASE/'manifest.json').read_text())
   import hashlib
   for row in m['evidence']:
    if row['path']==name:row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
   return audit.verify(target,m)
 def test_forged_producer_binding(self):self.assertTrue(self.changed_file('provenance/normal-library-binding.json',lambda d:d.update({'libmpv.so':'0'*64})))
 def test_forged_compile_macro(self):self.assertTrue(self.changed_file('provenance/normal-compile-binding.json',lambda d:d['translationUnits'][0].update(command='clang -DMP_OHCODEC_HANDOFF_TEST=1')))
 def test_resource_hash(self):self.assertTrue(self.mutated(lambda d:d['resources'][0].update(sha256='0'*64)))
 def test_forged_source_lock(self):self.assertTrue(self.changed_file('provenance/source-lock.json',lambda d:d.update(exactReferences=[])))
 def test_missing_header(self):self.assertTrue(self.mutated(lambda d:d['headers'].clear()))
 def test_unrelated_resource_cannot_replace_smb_config(self):
  import hashlib
  row={'path':'README.md','sha256':hashlib.sha256((BASE/'README.md').read_bytes()).hexdigest()}
  self.assertTrue(self.mutated(lambda d:d.update(resources=[row])))
if __name__=='__main__':unittest.main()
