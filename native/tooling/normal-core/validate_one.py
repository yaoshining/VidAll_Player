"""Phase16 evidence orchestration. Read only inputs; writes only this directory.
Reuses sealed ELF/ABI helpers and focused TDD gates. Never executes target code.
"""
from pathlib import Path
import argparse,ast,hashlib,json,re,struct,subprocess,sys
O=None
sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
from portable_elf import Binary
from registration_gate import inspect_ohcodec_registration
from interop_gate import compiled_interop_inputs,render_one_calls,unique_plt_address,direct_bl_calls
import abi_helpers as abi
from path_policy import require_no_runtime_paths
p=argparse.ArgumentParser()
for name in ['artifact','symbols','build','source','map','ffmpeg-lib','link-command','evidence-root','input-root','sdk']:p.add_argument('--'+name,type=Path,required=True)
args=p.parse_args()
O=args.evidence_root.resolve();O.mkdir(parents=True,exist_ok=False)
LLVM=args.sdk.resolve()/'llvm/bin';INPUT=args.input_root.resolve();VENDOR=Path(__file__).resolve().parent/'vendor'
args.artifact=args.artifact.resolve();args.symbols=args.symbols.resolve();args.build=args.build.resolve();args.source=args.source.resolve()
abi.O=O;abi.LLVM=LLVM
inspect=abi.inspect;exported=abi.exported;imports=abi.imports
helper=VENDOR/'abi_helpers.py'
commands=[];pins=[]
inputs=[args.artifact,args.symbols,args.map,args.link_command,args.build/'compile_commands.json',helper,VENDOR/'portable_elf.py',VENDOR/'registration_gate.py',VENDOR/'interop_gate.py']
for path in inputs:
 raw=path.read_bytes();pins.append({'path':str(path.resolve()),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
(O/'build-input-pins-before.json').write_text(json.dumps(pins,indent=2)+'\n')
# Binary binds every allocated section to the supplied symbol companion.
b=Binary(args.artifact,symbol_path=args.symbols)
executable=[(s['address'],s['address']+s['size']) for s in b.inventory['sections'].values() if s['allocated'] and s['flags']&4]
symbol_b=Binary(args.symbols)
maptext=args.map.read_text();linked=[];maplines=[];mapped_regions=[]
for line in maptext.splitlines():
 m=re.match(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+\.o):\((\.text[^)]*)\)\s*$',line)
 if m and int(m[3],16)>0:
  object_path=(args.build/m[4]).resolve();linked.append(object_path);maplines.append(line)
  mapped_regions.append({'object':str(object_path),'address':int(m[1],16),'size':int(m[3],16),'section':m[5]})
selected=compiled_interop_inputs(json.loads((args.build/'compile_commands.json').read_text()),args.source,args.build,linked)
linktext=args.link_command.read_text()
for row in selected:
 obj=Path(row['object']);raw=obj.read_bytes();pins.append({'path':str(obj),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 assert str(obj) in linktext or str(obj.relative_to(args.build)) in linktext, 'object missing from actual link command'
 cmd=[str(LLVM/'llvm-readelf'),'--relocs','--symbols','--wide',str(obj)];res=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);dest=O/(obj.name+'-references.txt');dest.write_text(res.stdout);commands.append({'argv':cmd,'exitCode':res.returncode,'output':dest.name});assert res.returncode==0
 regions=[region for region in mapped_regions if region['object']==str(obj)];assert regions
 snippets=[]
 for region in regions:
  assert any(a<=region['address'] and region['address']+region['size']<=z for a,z in executable)
  cmd=[str(LLVM/'llvm-objdump'),'-d','--start-address='+str(region['address']),'--stop-address='+str(region['address']+region['size']),str(args.symbols)];res=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert res.returncode==0;snippets.append(res.stdout);commands.append({'argv':cmd,'exitCode':res.returncode,'output':obj.name+'-final-text.txt'})
 (O/(obj.name+'-final-text.txt')).write_text('\n'.join(snippets))
 row['mappedExecutableRegions']=regions
(O/'selected-interop-inputs.json').write_text(json.dumps({'inputs':selected,'matchingMapText':[line for line in maplines if 'hwdec_ohcodec' in line]},indent=2)+'\n')
table=b.symbol('ra_hwdec_drivers');registration=inspect_ohcodec_registration(b,table['address'],table['size'],executable)
callback_symbols={}
for name,address in registration['callbacks'].items():
 matches=[s for s in symbol_b.inventory['symbols'] if s['value']==address and s['type']==2 and s['sectionIndex'] and s['size']>0]
 extents={(s['value'],s['size']) for s in matches};assert len(extents)==1,(name,matches)
 callback_symbols[name]={'address':address,'size':next(iter(extents))[1],'names':sorted({s['name'] for s in matches})}
cmd=[str(LLVM/'llvm-objdump'),'-d','--section=.plt',str(args.artifact)];res=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(O/'actual-plt.txt').write_text(res.stdout);commands.append({'argv':cmd,'exitCode':res.returncode,'output':'actual-plt.txt'});assert res.returncode==0
plttext=res.stdout;releaseplt=unique_plt_address(plttext,'av_ohcodec_release_buffer');mapper=callback_symbols['mapperMap']
releasecalls=render_one_calls(b,mapper['address'],mapper['size'],releaseplt,executable)
interesting={**callback_symbols}
for name in ('ohcodec_interop_gl_init','ohcodec_interop_pl_init','ohcodec_surface_init','ohcodec_surface_destroy','mpv_client_api_version'):
 interesting[name]=b.symbol(name)
for name,extent in interesting.items():
 cmd=[str(LLVM/'llvm-objdump'),'-d','--start-address='+str(extent['address']),'--stop-address='+str(extent['address']+extent['size']),str(args.symbols)];res=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);dest=O/(name+'-disassembly.txt');dest.write_text(res.stdout);commands.append({'argv':cmd,'exitCode':res.returncode,'output':dest.name});assert res.returncode==0
# Exact fixed API implementation, no emulation or arbitrary instruction inference.
api=interesting['mpv_client_api_version'];apibytes=b.at(api['address'],api['size']);assert apibytes==struct.pack('<III',0x528000a0,0x72a00040,0xd65f03c0),apibytes.hex()
driver_init=callback_symbols['driverInit'];interop_binding={'kind':'compiler-unrolled direct BL calls from registered driver init','targets':{}}
for name in ('ohcodec_interop_gl_init','ohcodec_interop_pl_init'):
 interop_binding['targets'][name]={'address':interesting[name]['address'],'calls':direct_bl_calls(b,driver_init['address'],driver_init['size'],interesting[name]['address'],executable)}
native_effective_calls={}
for source_name,targets in {'hwdec_ohcodec.c':['OH_NativeImage_AcquireNativeWindow','OH_NativeImage_SetOnFrameAvailableListener'],'hwdec_ohcodec_gl.c':['OH_NativeImage_Create','OH_NativeImage_UpdateSurfaceImage'],'hwdec_ohcodec_pl.c':['OH_ConsumerSurface_Create','OH_ConsumerSurface_SetDefaultUsage','OH_NativeImage_AcquireNativeWindowBuffer','OH_NativeImage_ReleaseNativeWindowBuffer','vkGetDeviceProcAddr','pl_vulkan_wrap']}.items():
 row=next(r for r in selected if Path(r['source']).name==source_name);native_effective_calls[source_name]={}
 for name in targets:
  target=b.symbol(name)['address'] if name=='pl_vulkan_wrap' else unique_plt_address(plttext,name);calls=[]
  for region in row['mappedExecutableRegions']:
   try:calls.extend(direct_bl_calls(b,region['address'],region['size'],target,executable))
   except ValueError as error:
    if str(error)!='no direct BL to bound target':raise
  assert calls,(source_name,name)
  native_effective_calls[source_name][name]={'target':target,'calls':calls}
new=inspect(args.artifact,'actual-mpv');tv=inspect(INPUT/'baseline/tv-har/libmpv.so','baseline-tv-mpv');old=inspect(INPUT/'baseline/player-har/libmpv.so','baseline-player-mpv')
require_no_runtime_paths(new['runpath'])
newex=exported(new);public=sorted(n.split('@')[0] for n in newex if n.startswith('mpv_'));tvpublic=sorted(n.split('@')[0] for n in exported(tv) if n.startswith('mpv_'))
extension={'mpv_ohcodec_terminal_api_version','mpv_ohcodec_terminal_register','mpv_ohcodec_terminal_enable','mpv_ohcodec_terminal_snapshot'}
extension.update({'mpv_host_recovery_api_version','mpv_host_recovery_generation','mpv_host_recovery_audio_pending','mpv_host_recovery_stop_audio','mpv_host_loadfile_async','mpv_host_fault_snapshot'})
assert not any(n.startswith('mp_host_') for n in newex), 'internal recovery symbol exported'
test_build = '-DMP_OHCODEC_HANDOFF_TEST=1' in (args.build/'compile_commands.json').read_text()
if test_build: extension.add('mpv_ohcodec_handoff_test_waiting')
assert len(tvpublic)==54 and len(public)==54+len(extension)
assert set(public)==set(tvpublic)|extension, (set(public)-set(tvpublic),extension)
assert not any(n.startswith('mp_ohcodec_terminal_') for n in newex), 'internal terminal symbol exported' 
assert 'av_ohcodec_release_buffer@LIBAVCODEC_62' in imports(new)
bridge_rows={}
for label in ['tv','player']:
 bridge=inspect(INPUT/f'baseline/{label}-har/libvidall_player_native.so',label+'-bridge');needs={s['name'] for s in bridge['rows'] if s['index']=='UND' and s['name'].startswith('mpv_')};missing=needs-set(public);assert not missing
 bridge_rows[label]={'input':bridge['path'],'sha256':bridge['sha256'],'requiredCount':len(needs),'required':sorted(needs),'missing':sorted(missing)}
producer={}
for lib,ver in {'avcodec':62,'avutil':60,'avfilter':11,'swresample':6,'swscale':9,'avformat':62}.items():
 path=args.ffmpeg_lib/f'lib{lib}.so.{ver}';producer[lib]=inspect(path,'producer-'+lib);raw=path.read_bytes();pins.append({'path':str(path.resolve()),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
exports=set().union(*(set(exported(v)) for v in producer.values()));closures={}
for name,lib in {**producer,'mpv':new}.items():
 needs=imports(lib);missing=needs-exports;closures[name]={'importCount':len(needs),'missing':sorted(missing)};assert not missing,(name,missing)
required_native={'OH_NativeImage_Create','OH_ConsumerSurface_Create','OH_ConsumerSurface_SetDefaultUsage','OH_NativeImage_AcquireNativeWindowBuffer','OH_NativeImage_ReleaseNativeWindowBuffer','vkGetDeviceProcAddr'}
actual_undef={s['name'].split('@')[0] for s in new['rows'] if s['index']=='UND'};assert required_native<=actual_undef,sorted(required_native-actual_undef)
for function,need in [('ohcodec_interop_gl_init','OH_NativeImage_Create@plt'),('ohcodec_interop_pl_init','OH_ConsumerSurface_Create@plt'),('ohcodec_interop_pl_init','OH_ConsumerSurface_SetDefaultUsage@plt')]:
 text=(O/(function+'-disassembly.txt')).read_text();assert re.search(r'\bbl\s+[^\n]*<'+re.escape(need)+'>',text),(function,need)
result={'artifact':b.record(),'symbolCompanion':symbol_b.record(),'allAllocatedSectionsExactlyBound':True,'driverTable':table,'registration':registration,'callbackSymbols':callback_symbols,'interopInitBinding':interop_binding,'nativeEffectiveCalls':native_effective_calls,'release':{'versionedImport':'av_ohcodec_release_buffer@LIBAVCODEC_62','plt':releaseplt,'renderOneCalls':releasecalls,'scope':'adjacent MOV W1,#1 + direct BL in bound registered mapper map function'},'api':{'version':'2.5','function':api,'rawBytes':apibytes.hex(),'publicCount':len(public),'publicSymbols':public,'preservedBaselineSymbols':tvpublic,'extensionSymbols':sorted(extension),'handoffTestBuild':test_build},'bridgeClosures':bridge_rows,'ffmpegClosures':closures,'mpvFFmpegImports':sorted(imports(new)),'nativeImports':sorted(n for n in actual_undef if n.startswith(('OH_','vk','egl'))),'needed':new['needed'],'producerInputs':{k:{field:v[field] for field in ['path','sha256','soname','needed']} for k,v in producer.items()},'runtimeExecuted':False,'deviceAcceptance':False,'lifecycleSafetyProven':False}
(O/'static-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
# Readonly ABI helper uses two known commands for each inspect call.
for label,path in [('actual-mpv',args.artifact),('baseline-tv-mpv',INPUT/'baseline/tv-har/libmpv.so'),('baseline-player-mpv',INPUT/'baseline/player-har/libmpv.so')]+[(label+'-bridge',INPUT/f'baseline/{label}-har/libvidall_player_native.so') for label in ['tv','player']]+[('producer-'+lib,Path(v['path'])) for lib,v in producer.items()]:
 commands += [{'argv':[str(LLVM/'llvm-readelf'),'--dyn-syms','--wide',str(path)],'output':label+'-dynsym.txt','exitCode':0},{'argv':[str(LLVM/'llvm-readelf'),'--dynamic',str(path)],'output':label+'-dynamic.txt','exitCode':0}]
(O/'build-input-pins.json').write_text(json.dumps(pins,indent=2)+'\n');(O/'validation-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
print(json.dumps({'status':'static checks passed','mpvSha256':b.record()['sha256'],'renderOneCalls':releasecalls,'apiCount':len(public),'ffmpegImportCount':len(imports(new)),'runtimeExecuted':False},indent=2))
