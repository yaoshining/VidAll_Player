#!/usr/bin/env python3
"""检测系统内录中的测试音及静音；信号通过不等于设备验收整体通过。"""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

WINDOW_SECONDS = 0.2
MIN_TONE_DBFS = -45
SILENCE_DBFS = -55
MAX_OLD_TO_NEW_POWER = 10 ** (-25 / 10)


def tone_power(samples, rate, hz):
    # 每声道独立计算，避免左右反相在混合时被误判为静音。
    coefficient = 2 * math.cos(2 * math.pi * hz / rate)
    previous = older = 0.0
    for sample in samples:
        current = sample / 32768.0 + coefficient * previous - older
        older, previous = previous, current
    power = previous * previous + older * older - coefficient * previous * older
    return max(0, 2 * power / (len(samples) ** 2))


def db(power):
    return 10 * math.log10(max(power, 1e-15))


def analyze(path, segments):
    if not segments:
        raise ValueError('必须提供与设备事件对应的验收区间')
    path = Path(path)
    with wave.open(str(path), 'rb') as capture:
        rate, channels, width, frames = capture.getframerate(), capture.getnchannels(), capture.getsampwidth(), capture.getnframes()
        if width != 2 or not 1 <= channels <= 2 or rate < 8000 or capture.getcomptype() != 'NONE':
            raise ValueError('仅接受8kHz以上、单/双声道的16bit PCM WAV')
        pcm = array('h', capture.readframes(frames))
    if sys.byteorder != 'little':
        pcm.byteswap()
    if len(pcm) != frames * channels:
        raise ValueError('录音数据截断')
    duration = frames / rate
    results = []
    for segment in segments:
        start, end = float(segment['start']), float(segment['end'])
        hz, forbidden = segment.get('toneHz'), segment.get('forbiddenHz')
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end > duration or end - start < 1:
            raise ValueError('区间必须在录音内且至少1秒，不能截取零散成功帧')
        for frequency in (hz, forbidden):
            if frequency is not None and (not math.isfinite(frequency) or not 0 < frequency < rate / 2):
                raise ValueError('测试频率超出采样范围')
        if hz is not None and hz == forbidden:
            raise ValueError('新旧测试音必须不同')
        first, last, window = round(start * rate), round(end * rate), round(WINDOW_SECONDS * rate)
        windows = []
        for offset in range(first, last, window):
            stop = min(last, offset + window)
            samples = [pcm[offset * channels + channel:stop * channels:channels] for channel in range(channels)]
            power = sum(sum((value / 32768.0) ** 2 for value in part) / len(part) for part in samples) / channels
            expected = sum(tone_power(part, rate, hz) for part in samples) / channels if hz else 0
            old = sum(tone_power(part, rate, forbidden) for part in samples) / channels if forbidden else 0
            mixed = hz is not None and forbidden is not None and old > max(expected * MAX_OLD_TO_NEW_POWER, 1e-10)
            passed = db(power) <= SILENCE_DBFS if hz is None else db(expected) >= MIN_TONE_DBFS and not mixed
            windows.append({'start':offset / rate, 'seconds':(stop - offset) / rate,
                            'rmsDbFS':db(power), 'expectedToneDbFS':db(expected),
                            'oldToneDbFS':db(old), 'mixed':mixed, 'passed':passed})
        total = sum(w['seconds'] for w in windows)
        good = sum(w['seconds'] for w in windows if w['passed'])
        gap = longest = 0
        for item in windows:
            gap = 0 if item['passed'] else gap + item['seconds']
            longest = max(longest, gap)
        passed = good / total >= .95 and longest <= .3 and not any(w['mixed'] for w in windows)
        results.append({'name':segment['name'], 'passed':passed, 'coverage':good / total,
                        'longestFailureSeconds':longest, 'windows':windows})
    return {'signalPassed':all(s['passed'] for s in results), 'deviceAccepted':False,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'sampleRate':rate,
            'channels':channels, 'durationSeconds':duration, 'segments':results,
            'limits':['只核对指定测试音，不证明自然音质或物理扬声器效果',
                      '包哈希、PID、内录来源、时间对齐及系统焦点事件须另行核对',
                      '合成音回归不计作设备验收']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    parser.add_argument('segments', type=Path, help='JSON区间数组，时间相对于录音开始')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.wav, json.loads(args.segments.read_text()))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return 0 if result['signalPassed'] else 1


if __name__ == '__main__':
    sys.exit(main())
