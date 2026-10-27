#!/usr/bin/env python3
"""真实生产argv进入同锁官方CLI解析层；只解析参数，不签名或读取真实材料。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import imac as M

JAR_SHA='a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d'
JAVA_SOURCE='''import com.ohos.hapsigntoolcmd.CmdUtil;
public class ParseSignArguments {
 public static void main(String[] args) {
  try { CmdUtil.convert2Params(args); System.out.println("{\\"accepted\\":true}"); }
  catch(Exception e) { System.out.println("{\\"accepted\\":false,\\"code\\":\\"cli-param-rejected\\"}"); System.exit(2); }
 }
}'''
sha=lambda b:hashlib.sha256(b).hexdigest()
def capture_actual_arguments(root):
    unsigned=root/'unsigned.hap';unsigned.write_bytes(b'synthetic only')
    cfg={'certificateFile':str(root/'cert.cer'),'certificateDER_SHA256':sha(b'der'),'profileFile':str(root/'profile.p7b'),'profileSHA256':sha(b'profile'),'keystoreFile':str(root/'key.p12'),'keystoreSHA256':sha(b'not a key'),'passwordMode':'interactive-local','keyAlias':'synthetic'}
    Path(cfg['certificateFile']).write_bytes(b'not a certificate');Path(cfg['profileFile']).write_bytes(b'profile');Path(cfg['keystoreFile']).write_bytes(b'not a key');Path(cfg['keystoreFile']).chmod(0o600)
    device=M.FixedDevice({'java':'/not-executed/java','signTool':'/not-executed/sign.jar'},{'deviceSerial':'192.168.3.85:5555','nonce':'a'*32},cfg,root/'session',unsigned,1,expected_unsigned_sha=sha(unsigned.read_bytes()))
    device.device_id='SYNTHETIC';device.signed.write_bytes(b'not a signed package')
    with patch.object(M,'certificate_ders',return_value=[b'der']),patch.object(M.sys.stdin,'isatty',return_value=True),patch.object(M.sys.stdout,'isatty',return_value=True),patch.object(M.subprocess,'Popen') as popen,patch.object(M,'verify_signed',return_value={'signatureVerified':False,'unsignedHAP_SHA256':device.expected_unsigned_sha}):
        popen.return_value.wait.return_value=0
        device.prepare_signed()
        return popen.call_args.args[0][3:]

def main():
    p=argparse.ArgumentParser();p.add_argument('--jar',type=Path,required=True);p.add_argument('--java',type=Path,required=True);p.add_argument('--javac',type=Path,required=True);a=p.parse_args()
    assert not a.jar.is_symlink() and sha(a.jar.read_bytes())==JAR_SHA
    with tempfile.TemporaryDirectory(prefix='vidall-cli-contract-') as directory:
        root=Path(directory);source=root/'ParseSignArguments.java';source.write_text(JAVA_SOURCE)
        subprocess.run([str(a.javac),'--release','17','-cp',str(a.jar),'-d',str(root),str(source)],check=True,capture_output=True,timeout=30)
        command=capture_actual_arguments(root)
        assert command[0]=='sign-app' and command[command.index('-signCode')+1]=='1'
        def parse(args):
            r=subprocess.run([str(a.java),'-cp',str(root)+':'+str(a.jar),'ParseSignArguments',*args],capture_output=True,text=True,timeout=10)
            return {'exitCode':r.returncode,'accepted':r.returncode==0 and json.loads(r.stdout).get('accepted') is True}
        actual=parse(command)
        # 去掉内部a后的有效argv仅用于负例构造；生产正例仍直接采用真实prepare_signed。
        valid=list(command)
        if '-a' in valid:
            index=valid.index('-a');del valid[index:index+2]
        invalid_alignment=parse([*valid,'-a','4'])
        unknown=parse([*valid,'-notApproved','1'])
        result={'schemaVersion':1,'jarSHA256':JAR_SHA,'actualProductionArguments':actual,'invalidAlignmentOption':invalid_alignment,'unknownOption':unknown,'signCode':'1','signingInvoked':False,'realMaterialsRead':False,'temporaryFilesRemovedOnExit':True}
        print(json.dumps(result))
        assert actual['accepted'],'真实生产sign-app argv被官方CLI拒绝'
        assert not invalid_alignment['accepted'] and not unknown['accepted']
if __name__=='__main__':main()
