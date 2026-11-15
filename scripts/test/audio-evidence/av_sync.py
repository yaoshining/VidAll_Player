#!/usr/bin/env python3
"""比较同轮实际系统内录中的闪光和短音；拒绝缺失，不自动判设备验收。"""
from array import array
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from analyze import tone_power, db


def rising_edges(times, active):
    if len(times) != len(active): raise ValueError('时间戳与采样数不一致')
    return [t for i,t in enumerate(times) if active[i] and (i == 0 or not active[i-1])]


def compare(video, audio):
    for points in (video,audio):
        if any(not math.isfinite(x) for x in points) or any(a >= b for a,b in zip(points,points[1:])):
            raise ValueError('时间戳必须有限且严格递增')
    complete = len(video) == len(audio) and len(video) >= 3
    offsets = [(a-v)*1000 for a,v in zip(audio,video)] if complete else []
    # 保留所有脉冲；不丢弃不匹配项，不以最近邻跨周期配对掩盖缺失。
    drift = statistics.median(offsets[-2:])-statistics.median(offsets[:2]) if complete else None
    passed = complete and max(abs(x) for x in offsets) <= 80 and abs(drift) <= 40
    return dict(signalPassed=bool(passed),deviceAccepted=False,videoPulses=video,audioPulses=audio,
                offsetsMs=offsets,driftMs=drift,thresholdMs=80,driftThresholdMs=40)


def run(command): return subprocess.run(command,check=True,capture_output=True).stdout


def measure(path, roi, windows):
    x,y,w,h=roi
    if min(x,y)<0 or min(w,h)<=0:raise ValueError('ROI无效')
    probe=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    videos=[s for s in probe['streams'] if s['codec_type']=='video']
    audios=[s for s in probe['streams'] if s['codec_type']=='audio']
    if len(videos)!=1 or len(audios)!=1:raise ValueError('要求一条真实视频轨及一条真实音轨')
    if x+w>videos[0]['width'] or y+h>videos[0]['height']:raise ValueError('ROI超出实际录制画面')
    frame_data=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
    times=[float(f['best_effort_timestamp_time']) for f in frame_data['frames']]
    pixels=run(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-vf',f'crop={w}:{h}:{x}:{y},scale=1:1:flags=area,format=gray','-fps_mode','passthrough','-f','rawvideo','-'])
    flashes=rising_edges(times,[p>180 for p in pixels])
    audio_frames=json.loads(run(['ffprobe','-v','error','-select_streams','a:0','-read_intervals','%+#5','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
    origin=float(audio_frames['frames'][0]['best_effort_timestamp_time'])
    pcm=array('h',run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ac','1','-ar','16000','-f','s16le','-']))
    if sys.byteorder!='little':pcm.byteswap()
    starts=[];active=[]
    for n in range(0,len(pcm)-159,160):
        starts.append(origin+n/16000);active.append(db(tone_power(pcm[n:n+160],16000,880))>-25)
    beeps=rising_edges(starts,active)
    results=[]
    for window in windows:
        start,end=window['start'],window['end']
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<=start or end>min(times[-1],starts[-1]):raise ValueError('区间必须位于实际音视频共同范围内')
        result=compare([v for v in flashes if start<=v<end],[a for a in beeps if start<=a<end])
        results.append(dict(name=window['name'],start=start,end=end,**result))
    if not results:raise ValueError('必须提供连续的事件区间')
    return dict(signalPassed=all(r['signalPassed'] for r in results),deviceAccepted=False,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),roi=roi,segments=results,
                limits=['系统内录链路的相对同步，不代表物理扬声器和显示面板','必须人工核对ROI仅含测试闪光区域，区间依据完整事件且不挑选成功脉冲','30fps与10ms音频窗口存在量化误差；首尾同向录制误差不能排除','仍须核对包、PID、实际解码路径与完整故障流程'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('windows',type=Path)
    p.add_argument('--roi',required=True,help='实际录制中的闪光区域 x,y,w,h');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=measure(a.capture,list(map(int,a.roi.split(','))),json.loads(a.windows.read_text()))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return 0 if result['signalPassed'] else 1
if __name__=='__main__':sys.exit(main())
