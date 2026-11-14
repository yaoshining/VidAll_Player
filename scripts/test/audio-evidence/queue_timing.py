"""分解有界回调探针；位置0不当作已经播放，重复平台采样去重但拒绝回退。"""
import re,statistics
from startup_timing import frame_origin

def summarize(log):
 groups={}
 for line in log.splitlines():
  if 'AUDIO_QUEUE_TRACE ' not in line and 'AUDIO_START_TRACE ' not in line:continue
  r={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)}
  if 'token' not in r:raise ValueError('探针缺少token')
  g=groups.setdefault(r['token'],dict(queue=[],platform=[]))
  g['queue' if 'AUDIO_QUEUE_TRACE ' in line else 'platform'].append(r)
 results=[]
 for token,g in groups.items():
  q=g['queue'];p=g['platform']
  required=['i','rate','enter','leave','samples','written','queued','pos','stamp','end','nonzero']
  if not q or any(any(k not in r for k in required) for r in q):raise ValueError('回调证据不完整')
  rate=q[0]['rate']
  if rate<=0 or any(r['rate']!=rate or r['leave']<r['enter'] or r['samples']<=0 for r in q):raise ValueError('回调时钟/格式错误')
  if [r['i'] for r in q]!=list(range(len(q))):raise ValueError('回调丢失或重复')
  unique=[]
  for r in p:
   if r.get('valid')!=1 or r.get('pos',0)<=0:continue
   item=dict(position=r['pos'],timestampNs=r['platform'])
   if unique and item==unique[-1]:continue
   unique.append(item)
  origin=frame_origin(unique,rate)
  first=next((r for r in p if r.get('pcm',0)>0),None)
  if not first:raise ValueError('缺少PCM原点映射')
  mono_minus_mpv=first['mono']-first['mpv']
  first_pcm=first['pcm']+mono_minus_mpv
  zero=[r for r in q if r['pos']==0 and r['stamp']>0]
  results.append(dict(token=token,callbacks=len(q),callbackPeriodMs=statistics.median(r['samples'] for r in q)/rate*1000,
   firstCallbackWorkMs=(q[0]['leave']-q[0]['enter'])/1e6,maxCallbackWorkMs=max(r['leave']-r['enter'] for r in q)/1e6,
   pcmToPlatformOriginMs=(origin['originSeconds']-first_pcm/1e9)*1000,platformOrigin=origin,
   zeroPositionExtrapolationMaxMs=max(((r['written']-r['queued'])/rate*1000 for r in zero),default=0),
   maxEstimatedQueuedMs=max(r['queued'] for r in q)/rate*1000,physicalAccepted=False))
 if not results:raise ValueError('没有回调证据')
 return results
if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 a.out.write_text(json.dumps(summarize(a.log.read_text()),ensure_ascii=False,indent=2)+'\n')
