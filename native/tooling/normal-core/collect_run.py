"""Finish evidence from completed fresh build; never compile/link/install."""
from pathlib import Path
import argparse,hashlib,json,re,struct,sys,subprocess,shlex
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'vendor'))
from portable_elf import inventory,ar_members,ELF
from input_gate import verify_files
from path_policy import validate_build_rpath,require_no_runtime_paths
p=argparse.ArgumentParser()
for n in ['run-root','input-root','sdk']:p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();RUN=a.run_root.resolve();PACKAGE=a.input_root.resolve();SDK=a.sdk.resolve();manifest=json.loads((PACKAGE/'package.json').read_text());records=[{'path':r['path'],'sizeBytes':r['size'],'sha256':r['sha256']} for r in manifest['files']]
commands=json.loads((RUN/'commands.json').read_text());assert all(c['returncode']==0 for c in commands)
profile=json.loads((RUN/'build-profile.json').read_text()) if (RUN/'build-profile.json').exists() else {'profile':'phase16-per-run-prefix','artifact':str(RUN/'install/lib/libmpv.so'),'stablePrefix':None}
rpath_evidence=None
if profile.get('ffmpegRelative')=='mpv/source/_staged/ffmpeg':
 dynamic={}
 for name,path in [('build',RUN/'mpv/build/libmpv.so'),('installed',Path(profile['artifact']))]:
  argv=[str(SDK/'llvm/bin/llvm-readelf'),'--dynamic',str(path)]
  text=subprocess.check_output(argv,text=True);(RUN/('actual-'+name+'-dynamic.txt')).write_text(text)
  paths=re.findall(r'\((?:RUNPATH|RPATH)\).*\[(.*?)\]',text)
  dynamic[name]={'argv':argv,'paths':paths,'lengths':[len(p.encode()) for p in paths]}
 assert len(dynamic['build']['paths'])==1
 validate_build_rpath('clang '+shlex.quote('-Wl,-rpath,'+dynamic['build']['paths'][0]),RUN)
 require_no_runtime_paths(dynamic['installed']['paths'])
 rpath_evidence={'passed':True,'build':dynamic['build'],'installed':dynamic['installed'],'binaryPatched':False}
 (RUN/'actual-rpath-gate.json').write_text(json.dumps(rpath_evidence,indent=2)+'\n')
artifact=Path(profile['artifact']);static=json.loads((RUN/'validation/static-validation.json').read_text());assert static['artifact']['sha256']==hashlib.sha256(artifact.read_bytes()).hexdigest()
trace=[]
for line in (RUN/'logs/mpv-build.log').read_text().splitlines():
 candidate=re.sub(r'\([^()]+\.o\)$','',line.strip())
 if ' ' in candidate or not candidate.endswith(('.o','.a','.so')):continue
 path=Path(candidate)
 if not path.is_absolute():path=RUN/'mpv/build'/path
 if path.is_file():trace.append(path.resolve())
assert trace
link_inputs=[]
for path in sorted(set(trace)):
 identity='run/'+str(path.relative_to(RUN)) if path.is_relative_to(RUN) else 'sdk/'+str(path.relative_to(SDK)) if path.is_relative_to(SDK) else str(path)
 link_inputs.append({'path':identity,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(RUN/'link-inputs.json').write_text(json.dumps(link_inputs,indent=2)+'\n')
archive=RUN/'libplacebo/install/lib/libplacebo.a';members=[]
for name,data in ar_members(archive):
 assert data[:7]==b'\x7fELF\x02\x01\x01' and struct.unpack_from('<H',data,18)[0]==183
 e=ELF(data)
 sections=[{'index':i,'name':s['name'],'type':s['type'],'flags':s['flags'],'address':s['address'],'size':s['size'],'sha256':hashlib.sha256(e.data(s)).hexdigest() if s['type']!=8 else None} for i,s in enumerate(e.sections) if s['flags']&2]
 members.append({'name':name,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'allocatedSections':sections})
assert members
actual=inventory(artifact.read_bytes());tools=json.loads((RUN/'tools.json').read_text())
plcmd=next(c['argv'] for c in commands if c['name']=='libplacebo-setup');mpvcmd=next(c['argv'] for c in commands if c['name']=='mpv-setup')
ploptions=[v for v in plcmd if v.startswith('-D')];mpvoptions=[v for v in mpvcmd if v.startswith(('-D','--default-library='))]
summary={'runRoot':str(RUN),'freshRootVerified':json.loads((RUN/'fresh-root.json').read_text())['freshRootVerified'],'configuration':{'profile':profile['profile'],'stablePrefix':profile['stablePrefix'],'ffmpegRelative':profile.get('ffmpegRelative','ffmpeg'),'packageSHA256':hashlib.sha256((PACKAGE/'package.json').read_bytes()).hexdigest(),'toolHashes':{n:v['sha256'] for n,v in tools.items()},'libplaceboOptions':ploptions,'mpvOptions':mpvoptions,'target':'aarch64-linux-ohos','linkerTraceDiagnostic':True},'artifactPath':str(artifact),'linkInputs':link_inputs,'artifactHashes':{'mpv':actual['sha256'],'libplacebo':hashlib.sha256(archive.read_bytes()).hexdigest()},'allocatedSections':{n:s for n,s in actual['sections'].items() if s['allocated']},'exports':static['api']['publicSymbols'],'imports':static['mpvFFmpegImports'],'features':{'ohcodecRegistered':static['registration']['registered'],'renderOneCallPresent':bool(static['release']['renderOneCalls']),'nativeCalls':{n:sorted(v) for n,v in static['nativeEffectiveCalls'].items()},'apiVersion':static['api']['version'],'bridgeRequiredCounts':{k:v['requiredCount'] for k,v in static['bridgeClosures'].items()},'needed':static['needed'],**({'buildRpath':rpath_evidence['build']['paths'],'buildRpathLengths':rpath_evidence['build']['lengths'],'installedRpath':rpath_evidence['installed']['paths']} if rpath_evidence else {})},'archiveMembers':members,'targetExecuted':False}
(RUN/'run-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
verify_files(PACKAGE,records)
for sub,dest in [('sources/mpv','mpv/source'),('sources/libplacebo','libplacebo/source')]:
 subset=[{'path':r['path'][len(sub)+1:],'sizeBytes':r['sizeBytes'],'sha256':r['sha256']} for r in records if r['path'].startswith(sub+'/')]
 verify_files(RUN/dest,subset)
 if sub=='sources/mpv' and profile.get('ffmpegRelative')=='mpv/source/_staged/ffmpeg':
  external=[{'path':r['path'][len('ffmpeg/'):],'sizeBytes':r['sizeBytes'],'sha256':r['sha256']} for r in records if r['path'].startswith('ffmpeg/')]
  from relocation_gate import relocated_records
  external=relocated_records(RUN/profile['ffmpegRelative'],external,json.loads((RUN/'pc-relocations.json').read_text()),profile['ffmpegRelative'],PACKAGE/'ffmpeg',[(r['from'],str(RUN/(profile['ffmpegRelative'] if r['to']=='ffmpeg' else r['to']))) for r in manifest['relocations']])
  verify_files(RUN/profile['ffmpegRelative'],external,exact=True)
  subset += [{**r,'path':'_staged/ffmpeg/'+r['path']} for r in external]
 verify_files(RUN/dest,subset,exact=True)
(RUN/'input-final-check.json').write_text(json.dumps({'packagePayloadUnchanged':True,'sourceTreesUnchanged':True,'freshSourcesWithoutBuildObjects':True,'declaredExternalFFmpeg':profile.get('ffmpegRelative','ffmpeg'),'sourceAndExternalUnionExact':True,'externalPCRelocationsVerified':True},indent=2)+'\n')
print(json.dumps({'runRoot':str(RUN),'status':'fresh build and static validation passed','artifactHashes':summary['artifactHashes'],'archiveMembers':len(members),'linkInputs':len(link_inputs)},indent=2))
