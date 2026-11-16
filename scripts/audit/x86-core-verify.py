#!/usr/bin/env python3
"""x86 软件核心输入门禁：真实 ELF/接口/闭包/来源；不代替设备运行。"""
import hashlib
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'native/tooling/normal-core/vendor'))
from portable_elf import ELF
NAMES={'libmpv.so','libavcodec.so.62','libavfilter.so.11','libavformat.so.62',
       'libavutil.so.60','libswscale.so.9','libswresample.so.6','libc++_shared.so'}
SYSTEM={'libc.so','libohaudio.so','libdeviceinfo_ndk.z.so','libnative_window.so','libEGL.so'}
REQUIRED={'mpv_create','mpv_initialize','mpv_terminate_destroy','mpv_command_async',
 'mpv_render_context_create','mpv_render_context_render','mpv_client_api_version',
 'mpv_ohcodec_terminal_api_version','mpv_ohcodec_terminal_register','mpv_ohcodec_terminal_enable',
 'mpv_ohcodec_terminal_snapshot','mpv_host_recovery_api_version','mpv_host_recovery_generation',
 'mpv_host_recovery_audio_pending','mpv_host_recovery_stop_audio','mpv_host_loadfile_async','mpv_host_fault_snapshot'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect(data):
 if len(data)<64 or data[:7]!=b'\x7fELF\x02\x01\x01' or struct.unpack_from('<HH',data,16)!=(3,62):
  raise ValueError('不是 x86_64 ELF64 共享库')
 elf=ELF(data);exports=set();imports=set();needed=[];soname=[];rpath=[]
 for index,symbols in elf.symtables.items():
  if elf.sections[index]['type']!=11:continue
  for s in symbols:
   if s['sectionIndex']==0:imports.add(s['name'])
   elif s['info']>>4 in [1,2] and s['visibility']&3 in [0,3]:exports.add(s['name'])
 for section in elf.sections:
  if section['type']!=6:continue
  strings=elf.data(elf.sections[section['link']]);raw=elf.data(section)
  for offset in range(0,len(raw),16):
   tag,value=struct.unpack_from('<qQ',raw,offset)
   if tag in [1,14,15,29]:
    (needed if tag==1 else soname if tag==14 else rpath).append(elf.cstr(strings,value))
 allocated={s['name']:{'size':s['size'],'sha256':None if s['type']==8 else hashlib.sha256(elf.data(s)).hexdigest()} for s in elf.sections if s['flags']&2}
 return {'exports':exports,'imports':imports,'needed':needed,'soname':soname,'rpath':rpath,'allocated':allocated}
def validate_core(info):
 if not REQUIRED<=info['exports']:raise ValueError('缺少完整播放/宿主恢复接口')
 if any(n.startswith('av_ohcodec_') for n in info['imports']):raise ValueError('软件核心仍引用 OHCodec')
 if 'OH_AudioRenderer_Start' not in info['imports']:raise ValueError('缺少真实 OHAudio 输出')
 if set(info['needed'])-(NAMES|SYSTEM):raise ValueError('未知动态依赖')
 if info['rpath']:raise ValueError('核心保留构建 RPATH')
def verify(base):
 manifest=json.loads((base/'manifest.json').read_text());rows=manifest['libraries']
 if len(rows)!=8 or {r['path'] for r in rows}!={'x86_64/'+n for n in NAMES}:raise ValueError('八库集合错误')
 result={}
 for row in rows:
  p=base/row['path']
  if sha(p)!=row['sha256'] or p.stat().st_size!=row['size']:raise ValueError('库摘要漂移：'+p.name)
  info=inspect(p.read_bytes())
  if info['soname']!=[p.name] or info['needed']!=row['needed'] or set(info['needed'])-(NAMES|SYSTEM):raise ValueError('SONAME/依赖闭包错误')
  if info['rpath']:raise ValueError('库保留构建 RPATH')
  if p.name=='libmpv.so':
   validate_core(info)
   symbols=base/manifest['symbolCompanion']['path']
   if sha(symbols)!=manifest['symbolCompanion']['sha256'] or inspect(symbols.read_bytes())['allocated']!=info['allocated']:raise ValueError('符号伴随文件未绑定运行库')
  if p.name=='libavformat.so.62' and 'ohcodec_smb_runtime_configure_v1' not in info['exports']:raise ValueError('缺 SMB 宿主配置接口')
  result[p.name]=row['sha256']
 lock=json.loads((base/'source-lock.json').read_text())
 for filename,key in [('player-sources.tar.gz','sourceArchiveSHA256'),('source-files.json','sourceFilesSHA256')]:
  if sha(base/filename)!=lock[key]:raise ValueError('对应源码摘要错误')
 if sha(ROOT/'native/patches/phase30/0016-optional-ohcodec-software-build.patch')!=lock['patchSHA256']:raise ValueError('补丁摘要错误')
 if sha(ROOT/'native/scripts/build-x86-core.py')!=lock['builderSHA256']:raise ValueError('核心构建配方漂移')
 producer=json.loads((base/manifest['producerEvidence']).read_text())
 if producer['sha256']!=result['libmpv.so'] or producer['scriptSHA256']!=lock['builderSHA256']:raise ValueError('构建结果未绑定当前核心和配方')
 sdk_path=base/'provenance/ffmpeg-sdk-manifest.json'
 if sha(sdk_path)!=lock['ffmpegSdkManifestSHA256']:raise ValueError('上游SDK身份漂移')
 sdk=json.loads(sdk_path.read_text())
 source_libs={Path(r['path']).name:r['sha256'] for r in sdk['files'] if r['path'].startswith('lib/')}
 for name,digest in result.items():
  if name.startswith(('libav','libsw')) and source_libs.get(name)!=digest:raise ValueError('六库不属于固定r3 SDK')
 config=(base/'provenance/mpv-config.h').read_text()
 if '#define HAVE_OHCODEC 0' not in config or '#define HAVE_OHOS 1' not in config:raise ValueError('构建未保留OHOS或未禁用OHCodec')
 return {'passed':True,'architecture':'x86_64','libraries':result,'deviceVerified':False}
if __name__=='__main__':
 try:print(json.dumps(verify(ROOT/'release/inputs/018-x86-core'),ensure_ascii=False,indent=2))
 except (ValueError,KeyError,OSError,AssertionError,struct.error) as error:
  print('x86核心门禁拒绝：'+str(error),file=sys.stderr);raise SystemExit(1)
