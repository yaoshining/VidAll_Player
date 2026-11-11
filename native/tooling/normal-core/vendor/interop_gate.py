"""Narrow Phase16 static gates; not runtime or lifecycle acceptance.
Only recognizes adjacent AArch64 MOVZ W1,#1; BL signed-imm26. Other
compiler arrangements fail closed for explicit review, not guessed dataflow.
Compile rows must be linked in an independently bound final link/map record.
"""
from pathlib import Path
import shlex,struct,re

INTEROP=('hwdec_ohcodec.c','hwdec_ohcodec_gl.c','hwdec_ohcodec_pl.c')

def render_one_calls(reader,address,size,target,executable_ranges):
    if address%4 or size<8 or size%4:raise ValueError('invalid function extent')
    if not any(a<=address and address+size<=b for a,b in executable_ranges):raise ValueError('function not entirely executable')
    if target%4 or not any(a<=target< b for a,b in executable_ranges):raise ValueError('target not executable')
    raw=reader.at(address,size)
    if len(raw)!=size:raise ValueError('truncated function')
    words=struct.unpack('<'+'I'*(size//4),raw);calls=[]
    for i in range(1,len(words)):
        word=words[i]
        if words[i-1]!=0x52800021 or word&0xfc000000!=0x94000000:continue
        imm=word&0x03ffffff
        if imm&(1<<25):imm-=1<<26
        pc=address+i*4
        if pc+imm*4==target:calls.append(pc)
    if not calls:raise ValueError('no adjacent MOV W1,#1 and BL to bound release target')
    return calls

def compiled_interop_inputs(entries,source_root,build_root,linked_inputs):
    source_root=Path(source_root).resolve();build_root=Path(build_root).resolve()
    linked={Path(p).resolve() for p in linked_inputs};result=[]
    for name in INTEROP:
        expected=source_root/'video/out/hwdec'/name;matches=[]
        for entry in entries:
            base=Path(entry['directory']).resolve();file=(base/entry['file']).resolve()
            if file!=expected:continue
            args=entry.get('arguments')
            if args is None:args=shlex.split(entry['command'])
            if any(a in (';','&&','||','|') for a in args):raise ValueError('shell compound compile unsupported')
            if args.count('-c')!=1 or args.count('-o')!=1:raise ValueError('not a unique compile/output command')
            ci=args.index('-c');oi=args.index('-o')
            if ci+1>=len(args) or oi+1>=len(args):raise ValueError('missing compile/output argument')
            if (base/args[ci+1]).resolve()!=expected:raise ValueError('file metadata does not match actual -c input')
            obj=(base/args[oi+1]).resolve()
            if not obj.is_relative_to(build_root):raise ValueError('object outside isolated build')
            if obj not in linked:raise ValueError('compiled interop object not selected by actual link')
            matches.append({'source':str(expected),'object':str(obj),'directory':str(base),'arguments':args})
        if len(matches)!=1:raise ValueError('expected exactly one compile and link selection: '+name)
        result.extend(matches)
    return result

def unique_plt_address(disassembly,symbol):
    labels=re.findall(r'^\s*([0-9a-fA-F]+) <'+re.escape(symbol)+r'@plt>:\s*$',disassembly,re.M)
    if len(labels)!=1:raise ValueError('missing or ambiguous exact PLT label')
    return int(labels[0],16)

def direct_bl_calls(reader,address,size,target,executable_ranges):
    if address%4 or size<4 or size%4 or target%4:raise ValueError('invalid direct-call extent')
    if not any(a<=address and address+size<=b for a,b in executable_ranges):raise ValueError('function not executable')
    if not any(a<=target<b for a,b in executable_ranges):raise ValueError('target not executable')
    raw=reader.at(address,size)
    if len(raw)!=size:raise ValueError('truncated function')
    calls=[]
    for i,word in enumerate(struct.unpack('<'+'I'*(size//4),raw)):
        if word&0xfc000000!=0x94000000:continue
        imm=word&0x03ffffff
        if imm&(1<<25):imm-=1<<26
        pc=address+i*4
        if pc+imm*4==target:calls.append(pc)
    if not calls:raise ValueError('no direct BL to bound target')
    return calls
