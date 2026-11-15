"""系统焦点交接独立判定：完整窗口、10ms联合频率拟合；不改旧片混音门槛。"""
from startup_timing import onset

def measure_focus_stop(pcm, rate, channels, start, end, old_hz, alarm_hz):
    if end - start < 1:
        raise ValueError('必须分析至少1秒的完整焦点保持窗口')
    old = onset(pcm, rate, channels, start, end, old_hz, alarm_hz)
    alarm = onset(pcm, rate, channels, start, end, alarm_hz, old_hz)
    step = old['resolutionSeconds']
    rows = []
    quiet_run = 0
    stopped = False
    reappeared = False
    longest = gap = 0
    for a, b in zip(old['windows'], alarm['windows']):
        audible = a['toneDbFS'] > -55
        expected = b['toneDbFS'] >= -45
        if audible and stopped:
            reappeared = True
        quiet_run = 0 if audible else quiet_run + 1
        if quiet_run >= 3:
            stopped = True
        passed = not audible and expected
        gap = 0 if passed else gap + step
        longest = max(longest, gap)
        rows.append(dict(start=a['start'], oldDbFS=a['toneDbFS'], alarmDbFS=b['toneDbFS'], passed=passed))
    duration = end - start
    # 不足10ms的尾块不计成功，避免丢掉尾块虚增覆盖率。
    coverage = min(1.0, sum(r['passed'] for r in rows) * step / duration)
    return dict(passed=coverage >= .95 and longest <= .3 and stopped and not reappeared,
                coverage=coverage, oldAudioSeconds=sum(r['oldDbFS'] > -55 for r in rows) * step,
                longestFailureSeconds=longest, reappeared=reappeared,
                resolutionSeconds=step, windows=rows, deviceAccepted=False,
                limits=['只判系统暂停交接；不替代跨视频旧音严格门槛',
                        '保留95%覆盖率及300ms连续失败上限；旧音停止后再次出现即失败',
                        '录制和平台时间映射不证明物理扬声器无延迟'])
