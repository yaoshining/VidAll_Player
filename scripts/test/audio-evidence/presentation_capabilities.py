#!/usr/bin/env python3
"""只判断实际呈现查询的候选能力；符号或扩展存在均不等于已经实测上屏。"""
import argparse,json
from pathlib import Path

def summarize(report):
 devices=report.get('devices',[])
 if not report.get('querySucceeded') or not devices or any(not d.get('extensionQuerySucceeded') for d in devices):vulkan='unknown'
 else:vulkan='candidate' if any(set(d.get('extensions',[])) & {'VK_GOOGLE_display_timing','VK_EXT_present_timing'} for d in devices) else 'unsupported'
 egl=report.get('eglReadOnly',{})
 if not egl.get('querySucceeded'):egl_status='unknown'
 elif 'EGL_ANDROID_get_frame_timestamps' not in egl.get('extensions','').split():egl_status='unsupported'
 elif not egl.get('frameTimestampsFunction') or not egl.get('frameSupportedFunction'):egl_status='unavailable-entrypoint'
 else:egl_status='candidate'
 return dict(vulkanStatus=vulkan,eglStatus=egl_status,actualPresentationMeasured=False,syncAccepted=False,
  nextRequirement='候选能力仍需窗口级支持、唯一帧ID和非零实际呈现时间；不可用时需要平台时间线或外部音画同钟采集。')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('events',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 records=[json.loads(x) for x in a.events.read_text().splitlines() if x.strip()]
 caps=[json.loads(x['value']) for x in records if x['event']=='presentation-capabilities']
 if not caps:raise ValueError('没有实际设备能力记录')
 a.out.write_text(json.dumps(summarize(caps[-1]),ensure_ascii=False,indent=2)+'\n')
