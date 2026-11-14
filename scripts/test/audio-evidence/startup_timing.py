"""以10ms分辨率独立定位测试音起点；不改完整音频门槛，不证明物理输出。"""
import math
import statistics
from analyze import db

def _weights(rate,count,frequencies):
    columns=[[math.sin(2*math.pi*f*i/rate) for i in range(count)] for f in frequencies]
    columns += [[math.cos(2*math.pi*f*i/rate) for i in range(count)] for f in frequencies]
    columns.append([1.0]*count)
    size=len(columns)
    # 联合拟合新旧音与DC，避免短窗中不同频率的泄漏被误认为声音开始。
    matrix=[[sum(a*b for a,b in zip(x,y)) for y in columns]+[float(i==j) for j in range(size)] for i,x in enumerate(columns)]
    for i in range(size):
        pivot=max(range(i,size),key=lambda j:abs(matrix[j][i]))
        matrix[i],matrix[pivot]=matrix[pivot],matrix[i]
        scale=matrix[i][i]
        if abs(scale)<1e-9:raise ValueError('频率基不可分辨')
        matrix[i]=[v/scale for v in matrix[i]]
        for j in range(size):
            if j==i:continue
            scale=matrix[j][i]
            matrix[j]=[a-scale*b for a,b in zip(matrix[j],matrix[i])]
    return [[sum(matrix[j][size+k]*columns[k][i] for k in range(size)) for i in range(count)] for j in [0,len(frequencies)]]

def onset(pcm,rate,channels,start,end,hz,other):
    if channels not in (1,2) or rate<8000 or len(pcm)%channels or not all(math.isfinite(v) for v in [start,end,hz,other]) or not 0<=start<end<=len(pcm)/channels/rate or end-start>30 or not 0<hz<rate/2 or not 0<other<rate/2 or hz==other:
        raise ValueError('起音窗口或格式无效；最多分析30秒')
    count=round(rate*.01);first,last=round(start*rate),round(end*rate)
    weights=_weights(rate,count,[hz,other]);windows=[]
    for offset in range(first,last-count+1,count):
        power=0
        for ch in range(channels):
            samples=pcm[offset*channels+ch:(offset+count)*channels:channels]
            a,b=[sum(x*w for x,w in zip(samples,weight))/32768 for weight in weights]
            power+=(a*a+b*b)/2/channels
        windows.append(dict(start=offset/rate,toneDbFS=db(power)))
    detected=None
    for i in range(len(windows)-2):
        if all(w['toneDbFS']>=-45 for w in windows[i:i+3]):detected=windows[i]['start'];break
    return dict(firstOnsetSeconds=detected,resolutionSeconds=count/rate,requiredConsecutiveWindows=3,windows=windows,deviceAccepted=False)

def frame_origin(rows,rate):
    if rate<=0 or len(rows)<3:raise ValueError('至少三个前进的平台帧样本')
    origins=[];last_pos=last_ts=-1
    for r in rows:
        pos,ts=r['position'],r['timestampNs']
        if not all(math.isfinite(x) for x in [pos,ts]) or pos<=0 or ts<=0 or pos<=last_pos or ts<=last_ts:raise ValueError('平台位置/时间无效或不前进')
        origins.append(ts/1e9-pos/rate);last_pos,last_ts=pos,ts
    spread=max(origins)-min(origins)
    if spread>.04:raise ValueError('平台起点映射不稳定')
    return dict(originSeconds=statistics.median(origins),minOriginSeconds=min(origins),maxOriginSeconds=max(origins),spreadMs=spread*1000,samples=len(origins))


def decompose(wav, anchor, gate, log):
    """拆分同次录制与平台时序；保持原完整窗口的判定。"""
    import re,wave
    from array import array
    if not anchor.get('calibrationValid'):
        raise ValueError('独立校准未通过')
    first_window=gate['eventWindows'][0]
    with wave.open(str(wav)) as capture:
        if capture.getsampwidth()!=2:raise ValueError('只接受16bit PCM')
        rate,channels=capture.getframerate(),capture.getnchannels()
        pcm=array('h',capture.readframes(capture.getnframes()))
    import sys
    if sys.byteorder!='little':pcm.byteswap()
    start=first_window['start']
    sound=onset(pcm,rate,channels,start,start+1,880,440)
    if sound['firstOnsetSeconds'] is None:raise ValueError('首秒没有稳定测试音')
    rows=[]
    for match in re.finditer(r'AUDIO_START_TRACE token=257 mono=(\d+) mpv=(\d+) pos=(\d+) platform=(\d+) valid=1 cb=(\d+) ret=(\d+) pcm=(\d+)',log):
        if int(match[3])>0:rows.append(dict(position=int(match[3]),timestampNs=int(match[4])))
    origin=frame_origin(rows,rate)
    match=re.search(r'AUDIO_START_TRACE token=257 mono=(\d+) mpv=(\d+).*?pcm=([1-9]\d*)',log)
    if not match:raise ValueError('缺少首个PCM单调时钟')
    pcm_mono=(int(match[1])-int(match[2])+int(match[3]))/1e9
    def event(pattern):
        found=re.search(r'(?m)^([\d.]+).*'+pattern,log)
        if not found:raise ValueError('缺少事件 '+pattern)
        return float(found[1])
    shift=gate['alignment']['wallToAudioPtsSeconds']
    wall_mono=anchor['monotonicMinusWallSeconds']
    onset_wall=sound['firstOnsetSeconds']-shift
    return dict(recordedOnset=sound['firstOnsetSeconds'],firstFrameToOnsetMs=(sound['firstOnsetSeconds']-start)*1000,
        onsetResolutionMs=10,platformFrameOrigin=origin,calibrationVisualUncertaintyMs=anchor['uncertaintyMs'],
        platformFirstFrameToRecordedOnsetMs=(onset_wall+wall_mono-origin['originSeconds'])*1000,
        firstPCMToPlatformFirstFrameMs=(origin['originSeconds']-pcm_mono)*1000,
        videoReadyToPlatformFirstFrameMs=(origin['originSeconds']-(event('first video frame after restart shown')+wall_mono))*1000,
        eventToVideoReadyMs=(event('first video frame after restart shown')-event('P17 firstFrame 1'))*1000,
        originalGatePassed=gate['signalPassed'],deviceAccepted=False,physicalAccepted=False)

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['wav','anchor','gate','log']:parser.add_argument(name,type=Path)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    result=decompose(args.wav,json.loads(args.anchor.read_text()),json.loads(args.gate.read_text()),args.log.read_text())
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
