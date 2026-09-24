"""OHCodec 配套运行库门禁回归测试；伪造 nm 输出以隔离交叉工具链。"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('check', pathlib.Path(__file__).parents[1] / 'scripts/check-ohcodec-runtime.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.codec, self.util, self.mpv = [root / name for name in ('codec', 'util', 'mpv')]
        self.codec.write_bytes(b'h264_ohcodec\0hevc_ohcodec\0')
        self.util.write_bytes(b'')
        self.mpv.write_bytes(b'OHCodec Surface hwdec requires compatible GL or Vulkan.')

    def inspect(self, util='000 T av_ohcodec_release_buffer\n', codec=''):
        with patch.object(check.subprocess, 'check_output', side_effect=lambda args, **kw: util if args[-1] == str(self.util) else codec):
            return check.inspect_pair(self.codec, self.util, self.mpv, 'nm')

    def test_export_in_either_library(self):
        self.assertEqual(self.inspect(), [])
        self.assertEqual(self.inspect('', '000 T av_ohcodec_release_buffer\n'), [])

    def test_versioned_export(self):
        self.assertEqual(self.inspect('000 T av_ohcodec_release_buffer@@LIBAVUTIL_60\n'), [])

    def test_similar_symbol_must_not_pass(self):
        self.assertTrue(self.inspect('000 T av_ohcodec_release_buffer_invalid\n'))

    def test_missing_export(self):
        self.assertTrue(self.inspect(''))

    def test_each_decoder_required(self):
        for decoder in (b'h264_ohcodec\0', b'hevc_ohcodec\0'):
            self.codec.write_bytes(decoder)
            self.assertEqual(len(self.inspect()), 1)

    def test_missing_bridge(self):
        self.mpv.write_bytes(b'')
        self.assertTrue(self.inspect())

    def test_missing_file_fails_closed(self):
        self.codec.unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_nm_failure_fails_closed(self):
        with patch.object(check.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'nm')):
            with self.assertRaises(subprocess.CalledProcessError):
                check.inspect_pair(self.codec, self.util, self.mpv, 'nm')


if __name__ == '__main__':
    unittest.main()
