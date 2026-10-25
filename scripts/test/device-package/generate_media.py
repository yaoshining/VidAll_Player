#!/usr/bin/env python3
"""一次性生成无外部输入的30秒合成媒体；云端只校验锁定文件，不安装编码器。"""
import argparse,hashlib,json,subprocess
from pathlib import Path
PARAMETERS=['-f','lavfi','-i','testsrc2=size=320x180:rate=15:duration=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=30','-map_metadata','-1','-c:v','libx264','-preset','medium','-crf','32','-pix_fmt','yuv420p','-threads','1','-g','30','-c:a','aac','-b:a','48k','-t','30','-movflags','+faststart']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def generate(ffmpeg,dest):
 if dest.exists():raise ValueError('拒绝覆盖已有媒体')
 dest.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin',*PARAMETERS,str(dest)],check=True,timeout=120)
 return {'path':'resources/rawfile/test_video.mp4','bytes':dest.stat().st_size,'sha256':sha(dest),'generatorSHA256':sha(Path(__file__)),'parameters':PARAMETERS,'origin':'generated-synthetic'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ffmpeg',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--lock',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();r=generate(a.ffmpeg,a.out);a.lock.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');a.evidence.write_text(json.dumps({'media':r,'ffmpegSHA256':sha(a.ffmpeg),'ffmpegVersion':subprocess.check_output([str(a.ffmpeg),'-version'],text=True).splitlines()[0]},ensure_ascii=False,indent=2)+'\n')
