#!/usr/bin/env python3
"""独立时间码与音频平台帧时间戳；保留原始门槛，不替代物理输出验收。"""
import argparse,json,math,statistics,subprocess,hashlib,sys
from array import array
from pathlib import Path
from analyze import tone_power,db

def decode_code(levels):
 if len(levels)!=16 or any(70<x<185 for x in levels):return None
 bits=[int(x>=185) for x in levels]
 if bits[:3]!=[1,1,0] or sum(bits)%2:return None
 return sum(bit<<(11-i) for i,bit in enumerate(bits[3:15]))

def audio_origin(samples):
 if len(samples)<8:raise ValueError('校准时间戳不足')
 origins=[];last_frame=0;last_ts=0
 for x in samples:
  f,t=x['framePos'],x['timestamp']/1e9;before=x['beforeMonoNs']/1e9;after=x['afterMonoNs']/1e9
  if not all(math.isfinite(v) for v in [f,t,before,after]) or f<=last_frame or t<=last_ts or f>x['writtenFrames'] or after<before or after-before>.2 or abs(t-(before+after)/2)>2:raise ValueError('平台时间戳无效或时基不匹配')
  origins.append(t-f/48000);last_frame=f;last_ts=t
 if max(origins)-min(origins)>.04:raise ValueError('平台帧时间映射不稳定')
 return statistics.median(origins)

def classify(raw,delay,uncertainty):
 if not all(math.isfinite(x) for x in [raw,delay,uncertainty]) or not 0<=uncertainty<=.08:return 'inconclusive'
 if abs(raw-delay)+uncertainty<=.08 and abs(delay)>.08:return 'capture-delay-supported'
 if abs(raw-delay)-uncertainty>.08:return 'output-offset-remains'
 return 'inconclusive'

def run(cmd):return subprocess.check_output(cmd)

def first_audio_pts(capture):
 # AAC首包可能只有预滚动信息；读取一秒内实际解码帧，不能把空首包当无音轨。
 frames=json.loads(run(['ffprobe','-v','error','-select_streams','a:0','-read_intervals','%+1','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(capture)])).get('frames',[])
 if not frames:raise ValueError('音轨起始区间没有可解码帧')
 origin=float(frames[0]['best_effort_timestamp_time'])
 if not math.isfinite(origin):raise ValueError('音轨起始时间无效')
 return origin

def measure(capture,events,row):
 probe=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(capture)]))
 video=next(x for x in probe['streams'] if x['codec_type']=='video');width=video['width']
 if not 1<=row<video['height']-2:raise ValueError('时间码行超出画面')
 ft=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(capture)]))['frames'];times=[float(x['best_effort_timestamp_time']) for x in ft]
 pixels=run(['ffmpeg','-v','error','-i',str(capture),'-vf',f'crop={width}:2:0:{row},scale={width}:1,format=gray','-fps_mode','passthrough','-f','rawvideo','-'])
 if len(pixels)!=width*len(times):raise ValueError('视频帧数不一致')
 es=[json.loads(l) for l in events.read_text().splitlines() if l.strip()];starts=[i for i,e in enumerate(es) if e['event']=='capture-started'];es=es[starts[-1]:]
 markers={};audios={};plans={}
 for e in es:
  if e['event']=='anchor-visual':
   value=json.loads(e['value']);seq=value['sequence']
   if seq in markers:raise ValueError('时间码重复')
   markers[seq]=value
  elif e['event']=='anchor-audio-timestamp':
   value=json.loads(e['value']);audios.setdefault(value['label'],[]).append(value)
  elif e['event']=='anchor-audio-plan':
   value=json.loads(e['value']);plans[value['label']]=value
 observed={};previous=None
 for i,t in enumerate(times):
  levels=[statistics.median(pixels[i*width+int((cell+.35)*width/16):i*width+int((cell+.65)*width/16)]) for cell in range(16)]
  seq=decode_code(levels)
  if seq is None:continue
  if seq not in markers:raise ValueError('录制时间码不存在对应事件')
  if previous is not None and seq<previous:raise ValueError('时间码倒退')
  observed.setdefault(seq,t);previous=seq
 if len(observed)<20:raise ValueError('可读视觉锚点不足')
 offsets=[];wall_offsets=[]
 for seq,t in observed.items():
  e=markers[seq];offsets.append((e['beforeMonoNs']+e['afterMonoNs'])/2e9-t);wall_offsets.append((e['beforeMonoNs']+e['afterMonoNs'])/2e9-e['wallMs']/1000)
 if max(wall_offsets)-min(wall_offsets)>.02:raise ValueError('墙钟跳变')
 # 不丢弃异常码，不用仅中位数遮蔽长尾调度；不确定度包含全范围和一帧。
 offset=statistics.median(offsets);uncertainty=max(abs(x-offset) for x in offsets)+1/30
 origin=first_audio_pts(capture)
 pcm=array('h',run(['ffmpeg','-v','error','-i',str(capture),'-map','0:a:0','-ac','1','-ar','16000','-f','s16le','-']));
 if sys.byteorder!='little':pcm.byteswap()
 beeps=[];was=False
 for n in range(0,len(pcm)-159,160):
  on=db(tone_power(pcm[n:n+160],16000,2200))>-25
  if on and not was:beeps.append(origin+n/16000)
  was=on
 results=[]
 for label in ['before','after']:
  base=audio_origin(audios.get(label,[]));plan=plans[label];predicted=[base+f/48000 for f in plan['pulseFrames']]
  matches=[b for b in beeps if predicted[0]-.5<=b+offset<=predicted[-1]+.5]
  if len(matches)!=len(predicted):raise ValueError('校准音脉冲缺失或多余')
  delays=[b+offset-p for b,p in zip(matches,predicted)]
  if max(delays)-min(delays)>.04:raise ValueError('校准音捕获延迟不稳定')
  results.append(dict(label=label,platformOrigin=base,observedBeepPts=matches,predictedMonotonic=predicted,delaysMs=[d*1000 for d in delays],medianDelayMs=statistics.median(delays)*1000))
 stable=abs(results[0]['medianDelayMs']-results[1]['medianDelayMs'])<=40 and uncertainty<=.08
 return dict(calibrationValid=stable,deviceAccepted=False,physicalAccepted=False,sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),visualRow=row,visualMarkers=len(observed),monotonicMinusVideoPtsSeconds=offset,monotonicMinusWallSeconds=statistics.median(wall_offsets),uncertaintyMs=uncertainty*1000,audioCalibrations=results,limitations=['视觉码记录提交时刻，包含显示合成不确定度','平台输出位置不替代物理扬声器','原始音画门槛单独保存，不自动改判通过'])

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('events',type=Path);p.add_argument('--row',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 try:r=measure(a.capture,a.events,a.row)
 except (ValueError,KeyError,IndexError,StopIteration) as e:r=dict(calibrationValid=False,deviceAccepted=False,error=str(e))
 a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');return 0 if r['calibrationValid'] else 1
if __name__=='__main__':sys.exit(main())
