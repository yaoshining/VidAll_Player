from pathlib import Path
import json,re,subprocess,hashlib

def inspect(p,label):
 text=subprocess.check_output([str(LLVM/'llvm-readelf'),'--dyn-syms','--wide',str(p)],text=True);dyn=subprocess.check_output([str(LLVM/'llvm-readelf'),'--dynamic',str(p)],text=True)
 (O/f'{label}-dynsym.txt').write_text(text);(O/f'{label}-dynamic.txt').write_text(dyn)
 rows=[]
 for line in text.splitlines():
  m=re.match(r'\s*\d+:\s+([0-9a-f]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',line)
  if m:rows.append(dict(zip(['address','size','type','bind','visibility','index','name'],m.groups())))
 return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':rows,'needed':re.findall(r'\(NEEDED\).*\[(.+)\]',dyn),'soname':re.findall(r'\(SONAME\).*\[(.+)\]',dyn),'runpath':re.findall(r'\((?:RUNPATH|RPATH)\).*\[(.+)\]',dyn)}

def exported(b):return {s['name'].replace('@@','@'):s for s in b['rows'] if s['index']!='UND' and s['bind'] in ['GLOBAL','WEAK'] and s['visibility']=='DEFAULT'}

def imports(b):return {s['name']for s in b['rows']if s['index']=='UND' and '@LIB' in s['name'] and s['name'].split('@')[1].split('_')[0]in ['LIBAVCODEC','LIBAVUTIL','LIBAVFILTER','LIBSWRESAMPLE','LIBSWSCALE','LIBAVFORMAT']}
