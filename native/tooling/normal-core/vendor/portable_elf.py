from pathlib import Path
import struct,collections,re,hashlib
from types import SimpleNamespace

class ELF:
 def __init__(self,b):
  self.b=b;assert b[:6]==b'\x7fELF\x02\x01'
  off=struct.unpack_from('<Q',b,40)[0];ent,count,si=struct.unpack_from('<HHH',b,58)
  self.sections=[]
  for i in range(count):
   x=struct.unpack_from('<IIQQQQIIQQ',b,off+i*ent);self.sections.append(dict(zip(['nameOffset','type','flags','address','offset','size','link','info','alignment','entrySize'],x)))
  names=self.data(self.sections[si])
  for s in self.sections:s['name']=self.cstr(names,s['nameOffset'])
  self.byname={s['name']:s for s in self.sections};self.symtables={}
  for idx,s in enumerate(self.sections):
   if s['type'] not in [2,11]:continue
   strings=self.data(self.sections[s['link']]);syms=[]
   for off in range(s['offset'],s['offset']+s['size'],s['entrySize']):
    name,info,other,shndx,value,size=struct.unpack_from('<IBBHQQ',b,off);syms.append({'name':self.cstr(strings,name),'info':info,'visibility':other,'sectionIndex':shndx,'value':value,'size':size})
   self.symtables[idx]=syms
 def data(self,s):return self.b[s['offset']:s['offset']+s['size']] if s['type']!=8 else b''
 @staticmethod
 def cstr(b,o):return b[o:b.find(b'\0',o)].decode('utf-8','replace')
 def symbols(self):return [x for t in self.symtables.values() for x in t]
 def relocs(self):
  rows=[]
  for s in self.sections:
   if s['type']!=4:continue
   syms=self.symtables.get(s['link'],[])
   for off in range(s['offset'],s['offset']+s['size'],s['entrySize']):
    address,info,addend=struct.unpack_from('<QQq',self.b,off);si=info>>32;symbol=syms[si] if si<len(syms) else None
    rows.append({'section':s['name'],'targetSection':self.sections[s['info']]['name'],'offset':address,'type':info&0xffffffff,'addend':addend,'symbol':symbol})
  return rows
 def at(self,va,size):
  for s in self.sections:
   if s['type']!=8 and s['address']<=va< s['address']+s['size']:return self.data(s)[va-s['address']:va-s['address']+size]
  raise ValueError(hex(va))

def ar_members(p):
 b=p.read_bytes();assert b[:8]==b'!<arch>\n';off=8;long=b''
 while off<len(b):
  hdr=b[off:off+60];assert hdr[58:60]==b'`\n';name=hdr[:16].decode().strip();size=int(hdr[48:58]);data=b[off+60:off+60+size];off+=60+size+(size%2)
  if name=='//':long=data;continue
  if name in ['/','/SYM64/']:continue
  if name.startswith('#1/'):
   n=int(name[3:]);name=data[:n].rstrip(b'\0').decode();data=data[n:]
  elif name.startswith('/') and name[1:].isdigit():name=long[int(name[1:]):].split(b'\n',1)[0].rstrip(b'/').decode()
  else:name=name.rstrip('/')
  yield name,data

def inventory(data):
    def span(off,size):
        if off<0 or size<0 or off+size>len(data):raise ValueError('truncated ELF')
        return data[off:off+size]
    if len(data)<64 or data[:7]!=b'\x7fELF\x02\x01\x01':raise ValueError('requires little-endian ELF64')
    h=struct.unpack('<16sHHIQQQIHHHHHH',data[:64])
    if h[2]!=183:raise ValueError('requires AArch64')
    shoff,entsize,count,namesidx=h[6],h[11],h[12],h[13]
    if entsize!=64 or not count or namesidx>=count:raise ValueError('unsupported section table')
    raw=[struct.unpack('<IIQQQQIIQQ',span(shoff+i*64,64)) for i in range(count)]
    names=span(raw[namesidx][4],raw[namesidx][5])
    def string(table,off):
        if off>=len(table):raise ValueError('bad string offset')
        end=table.find(b'\0',off)
        if end<0:raise ValueError('unterminated string')
        return table[off:end].decode('utf-8','replace')
    sections={};symbols=[]
    for idx,s in enumerate(raw):
        name=string(names,s[0]);payload=b'' if s[1]==8 else span(s[4],s[5])
        if idx:
            if name in sections:raise ValueError('duplicate section names unsupported')
            sections[name]={'type':s[1],'flags':s[2],'address':s[3],'size':s[5],'allocated':bool(s[2]&2),'sha256':None if s[1]==8 else hashlib.sha256(payload).hexdigest()}
        if s[1] in (2,11):
            if s[6]>=count or s[9]!=24 or s[5]%24:raise ValueError('bad symbol table')
            link=raw[s[6]];strings=span(link[4],link[5])
            for pos in range(0,len(payload),24):
                n,info,other,section,value,size=struct.unpack('<IBBHQQ',payload[pos:pos+24])
                symbol=string(strings,n)
                if symbol:symbols.append({'name':symbol,'table':name,'bind':info>>4,'type':info&15,'visibility':other&3,'sectionIndex':section,'value':value,'size':size})
    return {'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'sections':sections,'symbols':symbols}

def resolve_pointer(raw,relocations):
 if len(relocations)>1:raise ValueError('ambiguous pointer relocation')
 if not relocations:return raw
 r=relocations[0]
 if r['type']!=1027:raise ValueError('unsupported pointer relocation type '+str(r['type']))
 return r['addend']

def named_registry(reader,address,size,name_offset=0):
 if size<8 or size%8:raise ValueError('invalid registry extent')
 result=[];names=set();ended=False
 for pos in range(address,address+size,8):
  target=reader.ptr(pos)
  if not target:ended=True;continue
  if ended:raise ValueError('nonzero entry after terminator')
  name=reader.cstr(reader.ptr(target+name_offset))
  if not name or name in names:raise ValueError('empty or duplicate registered name')
  names.add(name);result.append({'slot':pos,'descriptor':target,'name':name})
 if not ended:raise ValueError('registry has no terminator')
 return result

class Binary:
 def __init__(self,path,symbol_path=None,map_path=None):
  self.path=Path(path);self.raw=self.path.read_bytes();self.inventory=audit.inventory(self.raw);self.e=ns['ELF'](self.raw);self.rels=collections.defaultdict(list)
  for rel in self.e.relocs():self.rels[rel['offset']].append(rel)
  self.syms=collections.defaultdict(list)
  symbols=self.inventory['symbols']
  if symbol_path:
   data=Path(symbol_path).read_bytes();other=audit.inventory(data)
   for name,sec in self.inventory['sections'].items():
    if sec['allocated']:assert sec==other['sections'][name],(path,symbol_path,name)
   symbols=other['symbols']
  for s in symbols:
   if s['sectionIndex'] and s['size']>0:self.syms[s['name']].append({'address':s['value'],'size':s['size']})
  if map_path:
   for line in Path(map_path).read_text().splitlines():
    m=re.match(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+ (.*)',line)
    if m and len(m[4])-len(m[4].lstrip())==16 and int(m[3],16)>0:self.syms[m[4].strip()].append({'address':int(m[1],16),'size':int(m[3],16)})
 def symbol(self,name):
  unique={(x['address'],x['size'])for x in self.syms.get(name,[])}
  if len(unique)!=1:raise ValueError('missing or ambiguous symbol '+name+':'+str(unique))
  address,size=next(iter(unique));return {'address':address,'size':size}
 def at(self,address,size):
  b=self.e.at(address,size)
  if len(b)!=size:raise ValueError('truncated virtual address read')
  return b
 def ptr(self,address):return resolve_pointer(struct.unpack('<Q',self.at(address,8))[0],self.rels.get(address,[]))
 def cstr(self,address):
  if not address:raise ValueError('null string pointer')
  for sec in self.e.sections:
   if sec['type']!=8 and sec['address']<=address<sec['address']+sec['size']:
    data=self.e.data(sec)[address-sec['address']:];end=data.find(b'\0')
    if end<0:raise ValueError('unterminated string')
    return data[:end].decode('utf-8',errors='strict')
  raise ValueError('unmapped string')
 def record(self):return {'path':str(self.path.resolve()),'sha256':self.inventory['sha256'],'sizeBytes':len(self.raw)}

ns={"ELF":ELF}
audit=SimpleNamespace(inventory=inventory)
