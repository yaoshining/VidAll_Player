"""实际归档/ELF夹具验证当前 ARM64 八库+NAPI 合同，不冒充目标构建。"""
import hashlib,importlib.util,io,json,os,shutil,struct,subprocess,tarfile,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NAMES={'libmpv.so','libavcodec.so.62','libavformat.so.62','libavfilter.so.11','libavutil.so.60','libswresample.so.6','libswscale.so.9','libc++_shared.so'}
def elf(needed='libmpv.so',rpath=False,machine=183):
 strings=b'\0'+needed.encode()+b'\0/private/build\0';offset=64+2*56;tags=[(1,1),(5,offset+5*16),(10,len(strings)),(15 if rpath else 21,1),(0,0)]
 dynamic=b''.join(struct.pack('<qQ',*x) for x in tags);size=offset+len(dynamic)+len(strings)
 header=struct.pack('<16sHHIQQQIHHHHHH',b'\x7fELF\x02\x01\x01'+b'\0'*9,3,machine,1,0,64,0,0,64,56,2,64,0,0)
 return header+struct.pack('<IIQQQQQQ',1,4,0,0,0,size,size,4096)+struct.pack('<IIQQQQQQ',2,4,offset,offset,offset,len(dynamic),len(dynamic),8)+dynamic+strings
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=Path(self.tmp.name)
  spec=importlib.util.spec_from_file_location('har_gate',ROOT/'native/tests/har-native-packaging.py');self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  self.readelf=shutil.which('llvm-readelf') or '/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/llvm-readelf'
  self.data={n:elf() for n in NAMES|{'libvidall_player_native.so'}};self.lock=[{'path':'arm64-v8a/'+n,'sha256':hashlib.sha256(v).hexdigest(),'size':len(v)} for n,v in self.data.items() if n in NAMES]
 def archives(self,har_extra=None,hap_extra=None,omit=None,changed=None,bridge=None,duplicate=False,symlink=False):
  har=self.d/'test.har';hap=self.d/'test.hap';source=dict(self.data)
  if omit:source.pop(omit)
  if changed:source[changed]=source[changed]+b'corrupt'
  if bridge is not None:source['libvidall_player_native.so']=bridge
  with tarfile.open(har,'w:gz') as t:
   for name,data in source.items():
    x=tarfile.TarInfo('package/libs/arm64-v8a/'+name);x.size=len(data);t.addfile(x,io.BytesIO(data))
   for name in ([har_extra] if har_extra else [])+(['package/libs/arm64-v8a/libmpv.so'] if duplicate else []):
    x=tarfile.TarInfo(name);x.size=1;t.addfile(x,io.BytesIO(b'x'))
   if symlink:
    x=tarfile.TarInfo('package/evil');x.type=tarfile.SYMTYPE;x.linkname='/tmp/else';t.addfile(x)
  with zipfile.ZipFile(hap,'w') as z:
   for name,data in source.items():z.writestr('libs/arm64-v8a/'+name,data)
   if hap_extra:z.writestr(hap_extra,b'x')
  return har,hap
 def verify(self,**kwargs):return self.m.verify(*self.archives(**kwargs),self.lock,self.readelf)
 def test_positive_arm64_nine_libraries(self):self.assertTrue(self.verify()['passed'])
 def test_missing_or_changed_core_rejected(self):
  for n in NAMES:
   with self.subTest(name=n),self.assertRaises(ValueError):self.verify(omit=n)
   with self.subTest(changed=n),self.assertRaises(ValueError):self.verify(changed=n)
 def test_extra_abi_and_unknown_library_rejected(self):
  for name in ['x86_64/libmpv.so','arm64-v8a/extra.so','arm64-v8a/nested/libmpv.so']:
   with self.subTest(har=name),self.assertRaises(ValueError):self.verify(har_extra='package/libs/'+name)
   with self.subTest(hap=name),self.assertRaises(ValueError):self.verify(hap_extra='libs/'+name)
 def test_bad_architecture_needed_and_rpath(self):
  for b in [elf(machine=62),elf(needed='other.so'),elf(rpath=True),b'not elf']:
   with self.subTest(bridge=b[:20]),self.assertRaises(ValueError):self.verify(bridge=b)
 def test_archive_paths_duplicate_and_symlink(self):
  for args in [{'har_extra':'../escape'},{'hap_extra':'../escape'},{'duplicate':True},{'symlink':True}]:
   with self.subTest(args=args),self.assertRaises(ValueError):self.verify(**args)
 def test_bridge_transfer_drift(self):
  har,hap=self.archives();
  with zipfile.ZipFile(hap,'w') as z:
   for n,d in self.data.items():z.writestr('libs/arm64-v8a/'+n,d+(b'changed' if n=='libvidall_player_native.so' else b''))
  with self.assertRaises(ValueError):self.m.verify(har,hap,self.lock,self.readelf)
 def test_lock_duplicate_rejected(self):
  self.lock[-1]=dict(self.lock[0])
  with self.assertRaises(ValueError):self.verify()
 def test_static_gate_and_sync_mutation(self):
  r=subprocess.run(['bash','native/tests/har-native-packaging.test.sh'],cwd=ROOT,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  files=['native/tests/har-native-packaging.test.sh','packages/vidall-player/build-profile.json5','packages/vidall-player/src/main/cpp/CMakeLists.txt','packages/vidall-player/src/main/cpp/napi_init.cpp','packages/vidall-player/src/main/cpp/types/libvidall_player_native/index.d.ts','packages/vidall-player/src/main/cpp/types/libvidall_player_native/oh-package.json5','packages/vidall-player/src/main/ets/native/harNativePackagingProbe.ets','packages/vidall-player/src/main/ets/native/nativeBridge.ets','packages/vidall-player/Index.ets']
  for rel in files:
   dst=self.d/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
  types=self.d/files[4];types.write_text(types.read_text().replace('): Promise<NativeSessionResult>;','): NativeSessionResult;'))
  r=subprocess.run(['bash',str(self.d/files[0])],capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('Promise<NativeSessionResult>',r.stderr)
if __name__=='__main__':unittest.main()
