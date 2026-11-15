#!/usr/bin/env python3
"""比较原始采集媒体时间戳；不经过编码封装，不替代物理输出验收。"""
import argparse,hashlib,json,math,statistics,struct,sys
from array import array
from pathlib import Path
from av_sync import compare,rising_edges
from analyze import tone_power,db
HEADER=struct.Struct('<IIqq')

def decode(data,strict=True):
 if len(data)>64*1024*1024+8 or data[:8]!=b'VRAWC001':raise ValueError('原始文件格式或上限错误')
 records=[];last={1:0,2:0};pos=8
 while pos<len(data):
  if pos+HEADER.size>len(data):raise ValueError('原始记录头截断')
  kind,size,stamp,arrival=HEADER.unpack_from(data,pos);pos+=HEADER.size
  if kind not in last or size<=0 or size>1024*1024 or pos+size>len(data) or stamp<=0 or (strict and stamp<=last[kind]) or arrival<=0:raise ValueError('原始记录无效/截断/同轨时间倒退')
  if kind==1 and size!=160*90 or kind==2 and size%4:raise ValueError('帧/PCM格式错误')
  records.append(dict(kind=kind,timestamp=stamp,arrival=arrival,payload=data[pos:pos+size]));last[kind]=stamp;pos+=size
  if len(records)>12000:raise ValueError('记录超限')
 return records

def audio_continuity(rows):
 if not rows:raise ValueError('无原始音轨')
 frames=0;start=rows[0]['timestamp'];errors=[]
 for row in rows:
  errors.append((row['timestamp']-start)/1e9-frames/48000)
  frames+=len(row['payload'])//4
 worst=max(abs(e) for e in errors)
 if worst>.005:raise ValueError('音频时间戳断裂或漂移超过5ms：'+str(worst))
 return worst

def measure(path,events,roi):
 data=path.read_bytes();rows=decode(data);video=[x for x in rows if x['kind']==1];audio=[x for x in rows if x['kind']==2]
 if len(video)<3:raise ValueError('视频不足')
 continuity=audio_continuity(audio)
 x,y,w,h=roi
 if min(x,y)<0 or min(w,h)<=0 or x+w>160 or y+h>90:raise ValueError('ROI越界')
 vtimes=[r['timestamp']/1e9 for r in video];levels=[statistics.mean(r['payload'][j*160+i] for j in range(y,y+h) for i in range(x,x+w)) for r in video]
 if max(b-a for a,b in zip(vtimes,vtimes[1:]))>.1:raise ValueError('视频间断超过100ms')
 vp=rising_edges(vtimes,[v>180 for v in levels])
 pcm=array('h',b''.join(r['payload'] for r in audio))
 if sys.byteorder!='little':pcm.byteswap()
 mono=[(pcm[i]+pcm[i+1])/2 for i in range(0,len(pcm),2)]
 start=audio[0]['timestamp']/1e9;atimes=[];active=[]
 for n in range(0,len(mono)-479,480):
  atimes.append(start+n/48000);active.append(db(tone_power(mono[n:n+480],48000,880))>-25)
 ap=rising_edges(atimes,active)
 es=[json.loads(line) for line in events.read_text().splitlines() if line.strip()]
 starts=[e for e in es if e['event']=='raw-started'];closed=[e for e in es if e['event']=='raw-closed']
 if len(starts)!=1 or len(closed)!=1 or any(e['event'] in ('failed','capture-failed') for e in es):raise ValueError('事件不是完整单轮采集')
 status=json.loads(closed[0]['value'])
 if status['error']!=0 or status['records']!=len(rows):raise ValueError('原始采集报错/记录数不匹配')
 bounds=[next(e['monoNs']/1e9 for e in es if e['event']==name) for name in ('measure-start','measure-end')]
 if bounds[1]<=bounds[0] or bounds[0]<max(vtimes[0],start) or bounds[1]>min(vtimes[-1],atimes[-1]):raise ValueError('事件与采集不是同一时基或区间不完整')
 if any(abs(r['arrival']-r['timestamp'])>5e9 for r in rows):raise ValueError('采集时间戳时基未确认')
 r=compare([t for t in vp if bounds[0]<=t<bounds[1]],[t for t in ap if bounds[0]<=t<bounds[1]])
 r.update(sha256=hashlib.sha256(data).hexdigest(),physicalAccepted=False,roi=roi,interval=bounds,
  videoFrames=len(video),audioBuffers=len(audio),audioContinuityMaxMs=continuity*1000,
  offsetMedianMs=statistics.median(r['offsetsMs']) if r['offsetsMs'] else None,
  callbackArrivalAgeMs={str(k):{'median':statistics.median((a['arrival']-a['timestamp'])/1e6 for a in rows if a['kind']==k),'min':min((a['arrival']-a['timestamp'])/1e6 for a in rows if a['kind']==k),'max':max((a['arrival']-a['timestamp'])/1e6 for a in rows if a['kind']==k)} for k in (1,2)},
  limitations=['媒体时间戳而非回调抵达时刻；原始捕获仍可能包含系统合成和混音延迟','原始链与Recorder链差异不是物理输出同步证明','原80ms门槛保持，全部脉冲匹配，不挑选成功项'])
 return r
def audio_edges(rows,hz):
 points=[];was=False
 for row in rows:
  pcm=array('h',row['payload'])
  if sys.byteorder!='little':pcm.byteswap()
  mono=[(pcm[i]+pcm[i+1])/2 for i in range(0,len(pcm),2)]
  if len(mono)%480:raise ValueError('原始音频块不是10ms整数倍')
  for n in range(0,len(mono),480):
   on=db(tone_power(mono[n:n+480],48000,hz))>-25
   if on and not was:points.append(row['timestamp']/1e9+n/48000)
   was=on
 return points

def audit(path,events):
 from time_anchor import audio_origin
 data=path.read_bytes();rows=decode(data,strict=False);last={};issues=[]
 for r in rows:
  k=r['kind']
  if k in last and r['timestamp']<=last[k]['timestamp']:
   issues.append(dict(kind=k,timestamp=r['timestamp'],previous=last[k]['timestamp'],samePayload=r['payload']==last[k]['payload']))
  last[k]=r
 audio=[r for r in rows if r['kind']==2];es=[json.loads(l) for l in events.read_text().splitlines() if l.strip()]
 closed=[e for e in es if e['event']=='raw-closed']
 if len(closed)!=1 or sum(e['event']=='raw-started' for e in es)!=1 or any(e['event'] in ('failed','capture-failed') for e in es):raise ValueError('独立校准不是完整单轮')
 status=json.loads(closed[0]['value'])
 if status['error']!=0 or status['records']!=len(rows):raise ValueError('采集状态/记录数不匹配')
 pulses=audio_edges(audio,2200);cal=[]
 for label in ('before','after'):
  samples=[json.loads(e['value']) for e in es if e['event']=='anchor-audio-timestamp' and json.loads(e['value'])['label']==label]
  plan=next(json.loads(e['value']) for e in es if e['event']=='anchor-audio-plan' and json.loads(e['value'])['label']==label)
  origin=audio_origin(samples);predicted=[origin+f/48000 for f in plan['pulseFrames']]
  matched=[t for t in pulses if predicted[0]-.5<=t<=predicted[-1]+.5]
  if len(matched)!=len(predicted):raise ValueError('独立校准脉冲缺失/多余')
  deltas=[(a-b)*1000 for a,b in zip(matched,predicted)]
  cal.append(dict(label=label,observedMonotonic=matched,predictedMonotonic=predicted,offsetsMs=deltas,medianMs=statistics.median(deltas),rangeMs=max(deltas)-min(deltas)))
 return dict(sha256=hashlib.sha256(data).hexdigest(),deviceAccepted=False,physicalAccepted=False,syncAccepted=False,
  timestampAnomalies=issues,recordCount=len(rows),audioCalibrations=cal,
  calibrationPulseStable=all(c['rangeMs']<=40 for c in cal) and abs(cal[0]['medianMs']-cal[1]['medianMs'])<=40,
  callbackArrivalAgeMs={str(k):dict(median=statistics.median((r['arrival']-r['timestamp'])/1e6 for r in rows if r['kind']==k),minimum=min((r['arrival']-r['timestamp'])/1e6 for r in rows if r['kind']==k),maximum=max((r['arrival']-r['timestamp'])/1e6 for r in rows if r['kind']==k)) for k in (1,2)},
  limitations=['保留全部重复/倒退时间戳；此报告仅用于归因，不能代替严格时间轴或设备同步通过','逐缓冲区使用原始时间戳，不在不连续处拼接连续音轨','平台播放帧时钟不等于物理扬声器实测，官方源码不等于当前商业固件源码证明'])

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('events',type=Path);p.add_argument('--roi',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 try:r=measure(a.capture,a.events,list(map(int,a.roi.split(','))))
 except (ValueError,KeyError,StopIteration) as e:r={'signalPassed':False,'deviceAccepted':False,'error':str(e)}
 a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');sys.exit(0 if r['signalPassed'] else 1)
