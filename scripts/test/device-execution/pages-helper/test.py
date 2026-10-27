#!/usr/bin/env python3
"""真实官方派生与失败关闭 CLI 测试；只用冻结 unsigned，无私钥。"""
import argparse, hashlib, io, json, os, subprocess, tempfile, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
HAP_SHA='bda840a7843dcad69241d06d907c8dce40479bdb969c9227b53c5f3bf21fa5b1'
PAGES_SHA='4364749b8c09d61a99ffa507ca0acd5f794c2d2bfc388243c54a15d4b9f09738'
def sha(b):return hashlib.sha256(b).hexdigest()
def main(a):
    a.out.mkdir(parents=True,exist_ok=False)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='vidall-pages-test-') as td:
        root=Path(td); classes=root/'classes';classes.mkdir()
        subprocess.run([str(a.javac),'--release','17','-cp',str(a.jar),'-d',str(classes),str(HERE/'ExpectedPages.java')],check=True,capture_output=True)
        with zipfile.ZipFile(a.artifact) as z:
            names=[n for n in z.namelist() if n.endswith('/device-unsigned.hap') or n=='device-unsigned.hap']
            assert len(names)==1; data=z.read(names[0])
        assert sha(data)==HAP_SHA
        hap=root/'unsigned.hap';hap.write_bytes(data)
        def invoke(name,input=hap,digest=HAP_SHA,output=None,jar=None,positive=False):
            output=output or root/(name+'.pages')
            before=output.read_bytes() if output.is_file() else None
            r=subprocess.run([str(a.java),'-cp',str(classes)+':'+str(jar or a.jar),'ExpectedPages',str(input),digest,str(output)],capture_output=True,text=True,timeout=45)
            try:
                v=json.loads(r.stdout)
                if positive:
                    assert r.returncode==0 and r.stderr==''
                    assert v==dict(schemaVersion=1,derived=True,unsignedHAP_SHA256=HAP_SHA,alignment=4,signCode=1,pagesSHA256=PAGES_SHA,pagesBytes=6680)
                    assert sha(output.read_bytes())==PAGES_SHA and (output.stat().st_mode&0o777)==0o600
                else:
                    assert r.returncode!=0 and r.stderr=='' and v=={'schemaVersion':1,'derived':False}
                    assert (output.read_bytes() if output.is_file() else None)==before
                rows.append({'name':name,'passed':True})
            except Exception:
                rows.append({'name':name,'passed':False,'returncode':r.returncode,'stdout':r.stdout[:300]})
        invoke('frozen-official-bitmap',positive=True)
        invoke('wrong-unsigned-sha',digest='0'*64)
        link=root/'input-link.hap';link.symlink_to(hap);invoke('symlink-input',input=link)
        for name,entries in [('existing-pages',[('.pages.info',b'x')]),('duplicate',[('module.json',b'a'),('module.json',b'b')]),('dot-path',[('./module.json',b'a')]),('parent-path',[('a/../module.json',b'a')]),('absolute-path',[('/module.json',b'a')]),('backslash-path',[('a\\module.json',b'a')]),('empty-part',[('a//module.json',b'a')])]:
            import warnings
            stream=io.BytesIO(data)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(stream,'a') as z:
                    for key,value in entries:z.writestr(key,value)
            f=root/(name+'.hap');f.write_bytes(stream.getvalue());invoke(name,input=f,digest=sha(f.read_bytes()))
        bad=root/'invalid.hap';bad.write_bytes(b'not zip');invoke('invalid-zip',input=bad,digest=sha(bad.read_bytes()))
        existing=root/'exists';existing.write_bytes(b'keep');invoke('existing-output',output=existing)
        outlink=root/'outlink';outlink.symlink_to(existing);invoke('output-symlink',output=outlink)
        wrongjar=root/'wrong.jar';wrongjar.write_bytes(a.jar.read_bytes()+b'changed');invoke('runtime-jar-mismatch',jar=wrongjar)
        # 删除路径/重复成员门禁的同型变异必须被真实 HAP 负例杀死。
        source=(HERE/'ExpectedPages.java').read_text()
        mutant=root/'ExpectedPages.java';mutant.write_text(source.replace('validateMembers(snapshot);','// mutation: skipped member guard'))
        subprocess.run([str(a.javac),'--release','17','-cp',str(a.jar),'-d',str(classes),str(mutant)],check=True,capture_output=True)
        bad=root/'dot-path.hap';output=root/'mutant.pages'
        r=subprocess.run([str(a.java),'-cp',str(classes)+':'+str(a.jar),'ExpectedPages',str(bad),sha(bad.read_bytes()),str(output)],capture_output=True,text=True,timeout=45)
        rows.append({'name':'member-guard-removal-mutant-rejected-by-test','passed':r.returncode==0 and json.loads(r.stdout).get('derived') is True})
        assert not list(root.glob('.vidall-pages-*'))
    result={'cases':rows,'passed':sum(r['passed'] for r in rows),'failed':sum(not r['passed'] for r in rows),'signingPerformed':False,'deviceVerified':False}
    (a.out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return int(result['failed']!=0)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['jar','javac','java','artifact','out']:p.add_argument('--'+n,type=Path,required=True)
    raise SystemExit(main(p.parse_args()))
