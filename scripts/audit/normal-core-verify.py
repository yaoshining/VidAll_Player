#!/usr/bin/env python3
"""校验实际库、公开头、正常宏和导出 ABI；不代表真机验收。"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
# 固定已审查生产者证据的身份，不能只信任待验清单自报。
BINDING_SHA='8a09134394321262cf5ac954c71a7b8141c9219931bee2203d800d6119089588'
COMPILE_SHA='c67b57eaf55099bc45d888b0b7898f1960475d67be3aaabdc077d841daf80c96'
SOURCE_LOCK_SHA='3b20b841544c40ec6ec5e784ce3fe5d28b259ef10b2e4c1e0cbcd03e3b2ed96c'
RESOURCE_AUDIT_SHA='62bf0d7e8f42f1f318ce7c56850bb51f18bc8b555aa706b8a36ce5e92c8c1149'
FFMPEG_SDK_SHA='7fd9cc6e5916b0b0b864e0c522e4134795774c1bb8c45e4f331d4788c17f4bbf'
FFMPEG_MERGE_SHA='3695ec4419c31999ade8fb947b24b465760f7e62ee54579ea5ee5c1ec9e81b6f'
MIN_EXPORTS={'libmpv.so':{'mpv_create','mpv_initialize','mpv_client_api_version','mpv_ohcodec_terminal_api_version','mpv_ohcodec_terminal_register','mpv_ohcodec_terminal_enable','mpv_ohcodec_terminal_snapshot','mpv_host_recovery_api_version','mpv_host_recovery_generation','mpv_host_recovery_audio_pending','mpv_host_recovery_stop_audio','mpv_host_loadfile_async','mpv_host_fault_snapshot'},'libavformat.so.62':{'ohcodec_smb_runtime_configure_v1'}}
NAMES={'libmpv.so','libavcodec.so.62','libavfilter.so.11','libavformat.so.62','libavutil.so.60','libswresample.so.6','libswscale.so.9','libc++_shared.so'}
ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_ffmpeg_recovery(base, manifest):
 """独立绑定当前六库，不将旧 mpv 链接输入冒充当前 FFmpeg 来源。"""
 errors=[]
 key=manifest.get('ffmpegRecovery')
 if key!='provenance/ffmpeg-recovery-sdk.json':return ['FFmpeg 恢复 SDK 绑定缺失']
 sdk=base/key
 if not sdk.is_file() or sha(sdk)!=FFMPEG_SDK_SHA:return ['FFmpeg 恢复 SDK 身份不匹配']
 source=json.loads(sdk.read_text())
 if source.get('diagnosticInjection') is not False or source.get('buildOrigin')!='local':
  errors.append('FFmpeg SDK 来源或注入状态错误')
 if manifest.get('compileDefinitionsScope')!='libmpv.so' or manifest.get('ffmpegCompileDefinitions')!=[]:
  errors.append('FFmpeg 与 mpv 编译宏范围混淆')
 current={Path(r['path']).name:r['sha256'] for r in manifest.get('libraries',[])}
 for row in source['files']:
  name=Path(row['path']).name
  if row['path'].startswith('lib/') and name in NAMES:
   if current.get(name)!=row['sha256']:errors.append('FFmpeg 运行库未绑定恢复 SDK '+name)
 merge_key=manifest.get('ffmpegRecoveryMerge')
 if merge_key!='provenance/ffmpeg-recovery-merge.json':
  errors.append('FFmpeg 合并绑定缺失')
 else:
  merge=base/merge_key
  if not merge.is_file() or sha(merge)!=FFMPEG_MERGE_SHA:
   errors.append('FFmpeg 合并绑定身份不匹配')
  elif json.loads(merge.read_text()).get('sdkManifestSHA256')!=sha(sdk):
   errors.append('FFmpeg SDK 与合并记录不一致')
 return errors

def verify(base,manifest=None,verify_external=False):
 if manifest is None:
  if not (base/'manifest.json').is_file():return ['清单缺失']
  manifest=json.loads((base/'manifest.json').read_text())
 errors=verify_ffmpeg_recovery(base,manifest)
 if manifest.get('formalArtifactAllowed') is not False:errors.append('禁止正式产物授权')
 libs=manifest.get('libraries',[])
 if {Path(r['path']).name for r in libs}!=NAMES or len(libs)!=8:errors.append('运行库集合不完整')
 flags=manifest.get('compileDefinitions',[])
 if any(any(s in flag for s in ['DIAGNOSTIC','EXPERIMENT','TEST']) for flag in flags):errors.append('禁止故障宏')
 if 'MP_OHCODEC_HANDOFF_TRACE=1' not in flags:errors.append('TRACE 输入不匹配')
 if not {'include/mpv/client.h','include/mpv/render.h','include/mpv/render_gl.h','include/mpv/ohcodec_terminal.h','include/libavformat/ohcodec_smb_runtime.h'}.issubset({r['path'] for r in manifest.get('headers',[])}):errors.append('公共头集合缺失')
 for category in ['libraries','headers','evidence','licenses','resources']:
  if not manifest.get(category):errors.append(category+' 为空')
  for row in manifest.get(category,[]):
   p=base/row['path']
   if not p.is_file() or sha(p)!=row['sha256']:errors.append('内容不匹配 '+row['path'])
 nm=os.environ.get('LLVM_NM','/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/llvm-nm')
 for name, symbols in manifest.get('requiredExports',{}).items():
  p=base/'arm64-v8a'/name
  if not p.is_file():continue
  try:actual={line.split()[-1].split('@')[0] for line in subprocess.check_output([nm,'-D','--defined-only',str(p)],text=True).splitlines() if line.split()}
  except (OSError,subprocess.CalledProcessError):errors.append('ABI 工具失败 '+name);continue
  for symbol in symbols:
   if symbol not in actual:errors.append('ABI 缺失 '+symbol)
 mpv=base/'arm64-v8a/libmpv.so'
 if mpv.is_file():
  try:
   names={line.split()[-1].split('@')[0] for line in subprocess.check_output([nm,'-D','--undefined-only',str(mpv)],text=True).splitlines() if line.split()}
   if not {'OH_AudioStreamBuilder_SetRendererCallback','OH_GetSdkApiVersion'}.issubset(names):errors.append('缺少旧系统中断注册接口')
   if 'OH_AudioStreamBuilder_SetRendererInterruptCallback' in names:errors.append('引入了 API 20 专用中断接口')
  except (OSError,subprocess.CalledProcessError):errors.append('无法读取 mpv 导入')
 for library,minimum in MIN_EXPORTS.items():
  if not minimum.issubset(set(manifest.get('requiredExports',{}).get(library,[]))):errors.append('最低 ABI 集合缺失 '+library)
 for key,expected in [('producerBinding',BINDING_SHA),('compileEvidence',COMPILE_SHA)]:
  p=base/manifest.get(key,'')
  if not p.is_file() or sha(p)!=expected:errors.append('封存身份不匹配 '+key)
 binding=base/manifest.get('producerBinding','')
 if binding.is_file() and sha(binding)==BINDING_SHA:
  expected=json.loads(binding.read_text())
  if {Path(r['path']).name:r['sha256'] for r in libs}!=expected:errors.append('与封存运行库绑定不同')
 compilation=base/manifest.get('compileEvidence','')
 if compilation.is_file() and sha(compilation)==COMPILE_SHA:
  c=json.loads(compilation.read_text()); observed=c.get('observedMacros',{})
  if observed!={'TRACE':True,'TEST':False,'DIAGNOSTIC':False,'EXPERIMENT':False,'RETURN_REPLACEMENT':False}:errors.append('实际编译宏不是正常组合')
  # 本次只编译 mpv；FFmpeg 编译宏不能从旧构建记录推断。
  commands=[r.get('command','') for r in c.get('translationUnits',[])]
  if c.get('ffmpegInputManifestSHA256')!=FFMPEG_SDK_SHA or 'ffmpegExplicitFlags' in c:errors.append('mpv 链接 SDK 来源错误')
  if len(commands)<3 or any('-DMP_OHCODEC_HANDOFF_TRACE=1' not in x for x in commands):errors.append('实际编译 TRACE 证据不足')
  if any(any(s in x for s in ['-DMP_OHCODEC_DIAGNOSTIC','-DMP_OHCODEC_LIFECYCLE_EXPERIMENT','-DMP_OHCODEC_HANDOFF_TEST','-DMP_OHCODEC_TEST']) for x in commands):errors.append('实际编译含故障宏')
  if c.get('mpvLibrarySHA256')!={Path(r['path']).name:r['sha256'] for r in libs}.get('libmpv.so'):errors.append('编译产物绑定错误')
 source=base/'provenance/source-lock.json'
 if not source.is_file() or sha(source)!=SOURCE_LOCK_SHA:errors.append('来源锁身份不匹配')
 else:
  lock=json.loads(source.read_text())
  update=lock['mpvUpdate']
  for item in [update, *update.get('additionalPatches', [])]:
   patch=ROOT/item['patch']
   if not patch.is_file() or sha(patch)!=item['patchSHA256']:errors.append('主线 mpv 补丁与来源锁不匹配 '+item['patch'])
  recovery=lock.get('hostRecovery',{})
  recovery_lock=base/'provenance/host-recovery-input.json'
  if recovery.get('inputLock')!='host-recovery-input.json' or not recovery_lock.is_file() or sha(recovery_lock)!=recovery.get('inputLockSHA256'):
   errors.append('宿主恢复输入锁缺失或不匹配')
  else:
   inputs=json.loads(recovery_lock.read_text())
   if inputs.get('ffmpegManifestSHA256')!=FFMPEG_SDK_SHA:errors.append('宿主恢复 SDK 不匹配')
   for item in inputs.get('patches',[])+inputs.get('addedSources',[])+recovery.get('tooling',[]):
    path=ROOT/item['path']
    if not path.is_file() or sha(path)!=item['sha256']:errors.append('宿主恢复构建来源不匹配 '+item['path'])
   if recovery.get('libmpvSHA256')!=sha(base/'arm64-v8a/libmpv.so'):errors.append('恢复核心库绑定不匹配')
  if verify_external:
   for row in lock['exactReferences']:
    p=Path(row['path'])
    if not p.is_file() or sha(p)!=row['sha256']:errors.append('外部来源不匹配 '+row['path'])
   build_root=os.environ.get('VIDALL_MPV_BUILD_ROOT')
   if not build_root:
    try:
     summary=json.loads((base/'provenance/mpv-run-summary.json').read_text())
     build_root=summary.get('runRoot') if isinstance(summary,dict) else None
    except (OSError,ValueError):
     build_root=None
   if not isinstance(build_root,str) or not build_root.strip():
    errors.append('无效或缺失的 mpv 构建目录证据')
   else:
    archive=Path(build_root)/lock['staticLibplacebo']['path'].removeprefix('run/')
    try:
     archive_matches=archive.is_file() and sha(archive)==lock['staticLibplacebo']['sha256']
    except (OSError, ValueError):
     archive_matches=False
    if not archive_matches:errors.append('静态 libplacebo 与来源锁不匹配，请设置 VIDALL_MPV_BUILD_ROOT')
 resource_audit=base/'provenance/samba-resource-audit.json'
 if not resource_audit.is_file() or sha(resource_audit)!=RESOURCE_AUDIT_SHA:errors.append('资源来源证据身份不匹配')
 else:
  resource=json.loads(resource_audit.read_text())
  actual_resources={r['path']:r['sha256'] for r in manifest.get('resources',[])}
  for row in resource['requiredExternalFiles']:
   if actual_resources.get(row['input'])!=row['sha256']:errors.append('必要资源缺失或不匹配 '+row['input'])
  avformat=base/'arm64-v8a/libavformat.so.62'
  if avformat.is_file():
   blob=avformat.read_bytes()
   for table in resource['tables']:
    offset=table['exactBytesInCurrentAvformatAtOffset'];data=blob[offset:offset+table['bytes']]
    if hashlib.sha256(data).hexdigest()!=table['sha256']:errors.append('内嵌字符表不匹配 '+table['name'])
  if verify_external:
   for row in resource['sources']:
    p=Path(row['path'])
    if not p.is_file() or sha(p)!=row['sha256']:errors.append('资源源码不匹配 '+row['path'])
 if set(manifest.get('requiredExports',{}))!={'libmpv.so','libavformat.so.62'}:errors.append('ABI 集合缺失')
 return errors
if __name__=='__main__':
 arguments=[a for a in sys.argv[1:] if not a.startswith('--')]
 base=Path(arguments[0]) if arguments else Path(__file__).resolve().parents[2]/'release/inputs/004-normal-core'
 errors=verify(base,verify_external='--verify-external' in sys.argv);print(json.dumps({'passed':not errors,'errors':errors},ensure_ascii=False,indent=2));sys.exit(bool(errors))
