"""宿主运行时接口属于 SMB 沙箱配置，不得随软件解码一起关闭。"""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'gate', Path(__file__).parents[1] / 'scripts/check-ffmpeg-host-runtime.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class HostRuntimeSdkTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.header = self.root / 'include/libavformat/ohcodec_smb_runtime.h'
        self.header.parent.mkdir(parents=True)
        self.header.write_text('/* SDK 配套头文件；实际签名另由交叉链接验证。 */')
        self.library = self.root / 'lib/libavformat.so.62'
        self.library.parent.mkdir()
        self.elf = bytearray(64)
        self.elf[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', self.elf, 16, 3, 62)
        self.library.write_bytes(self.elf)

    def inspect(self, symbols='00000010 T ohcodec_smb_runtime_configure_v1\n'):
        with patch.object(gate.subprocess, 'check_output', return_value=symbols):
            return gate.inspect_sdk(self.root, 'nm', 'x86_64')

    def test_software_sdk_needs_no_codec_extension(self):
        self.assertTrue(self.inspect()['passed'])

    def test_versioned_export(self):
        self.assertTrue(self.inspect('10 T ohcodec_smb_runtime_configure_v1@@LIBAVFORMAT_62\n')['passed'])

    def test_missing_export_blocks_even_when_smb_protocol_exists(self):
        self.assertIn('缺少动态导出', '\n'.join(self.inspect('10 T avformat_open_input\n')['errors']))

    def test_similar_symbol_and_undefined_import_do_not_pass(self):
        for symbols in ['10 T ohcodec_smb_runtime_configure_v10\n', ' U ohcodec_smb_runtime_configure_v1\n']:
            with self.subTest(symbols=symbols):
                self.assertFalse(self.inspect(symbols)['passed'])

    def test_missing_header_blocks(self):
        self.header.unlink()
        self.assertFalse(self.inspect()['passed'])

    def test_arm64_library_cannot_pass_as_x86(self):
        struct.pack_into('<H', self.elf, 18, 183)
        self.library.write_bytes(self.elf)
        self.assertFalse(self.inspect()['passed'])

    def test_executable_and_truncated_file_rejected(self):
        for payload in [b'ELF', self.elf[:16] + b'\x02\x00' + self.elf[18:]]:
            self.library.write_bytes(payload)
            self.assertFalse(self.inspect()['passed'])

    def test_missing_library_blocks(self):
        self.library.unlink()
        self.assertFalse(self.inspect()['passed'])

    def test_tool_failure_blocks(self):
        with patch.object(gate.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'nm')):
            self.assertFalse(gate.inspect_sdk(self.root, 'nm', 'x86_64')['passed'])


if __name__ == '__main__':
    unittest.main()
