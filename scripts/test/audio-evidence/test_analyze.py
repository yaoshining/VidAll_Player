"""音频证据分析器回归：合成输入只验证检测器，不计作设备验收。"""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
import wave
import struct

spec = importlib.util.spec_from_file_location('audio_evidence', Path(__file__).with_name('analyze.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AudioEvidenceTest(unittest.TestCase):
    def check_signal(self, tones, *, silence=False, dropout=False, opposite=False, start=0, end=2):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'capture.wav'
            rate = 8000
            with wave.open(str(path), 'wb') as f:
                f.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
                data = bytearray()
                for i in range(rate * 2):
                    t = i / rate
                    value = sum(amplitude * math.sin(2 * math.pi * hz * t) for hz, amplitude in tones)
                    if dropout and 0.8 <= t < 1.4:
                        value = 0
                    sample = round(value * 32767)
                    data.extend(struct.pack('<hh', sample, -sample if opposite else sample))
                f.writeframes(data)
            segment = {'name':'续播', 'start':start, 'end':end, 'toneHz':None if silence else 440, 'forbiddenHz':880}
            return module.analyze(path, [segment])

    def test_expected_tone(self):
        self.assertTrue(self.check_signal([(440, .2)])['signalPassed'])
    def test_opposite_stereo_phase_does_not_cancel(self):
        self.assertTrue(self.check_signal([(440, .2)], opposite=True)['signalPassed'])
    def test_silent_video_fails(self):
        self.assertFalse(self.check_signal([])['signalPassed'])
    def test_old_audio_alone_fails(self):
        self.assertFalse(self.check_signal([(880, .2)])['signalPassed'])
    def test_old_and_new_mixing_fails(self):
        self.assertFalse(self.check_signal([(440, .2), (880, .08)])['signalPassed'])
    def test_dropout_fails(self):
        self.assertFalse(self.check_signal([(440, .2)], dropout=True)['signalPassed'])
    def test_release_silence(self):
        self.assertTrue(self.check_signal([], silence=True)['signalPassed'])
        self.assertFalse(self.check_signal([(440, .2)], silence=True)['signalPassed'])
    def test_near_silent_tone_fails(self):
        self.assertFalse(self.check_signal([(440, .0001)])['signalPassed'])
    def test_incomplete_capture_rejected(self):
        with self.assertRaises(ValueError):self.check_signal([(440, .2)], end=3)
        with self.assertRaises(ValueError):self.check_signal([(440, .2)], start=-1)
    def test_no_segments_is_not_success(self):
        with self.assertRaises(ValueError):module.analyze(Path('/nonexistent'), [])

if __name__ == '__main__':unittest.main()
