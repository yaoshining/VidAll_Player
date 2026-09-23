"""发布 prefix 元数据必须来自实际配置及 ELF，而非旧 artifact 的声明。"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('prefix', Path(__file__).parents[1] / 'scripts/finalize-ohcodec-prefix.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PrefixTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for d in ['prefix/lib', 'source', 'build/ffbuild']: (self.root/d).mkdir(parents=True)
        for name in module.LIBRARIES: (self.root/'prefix/lib'/name).write_bytes(b'elf')
        for name in ['COPYING.GPLv3','COPYING.LGPLv2.1']: (self.root/'source'/name).write_text('license')
        (self.root/'build/config.h').write_text('#define CONFIG_OHCODEC 1\n#define CONFIG_GNUTLS 1\n#define CONFIG_LIBSMBCLIENT 1\n')
        (self.root/'build/config_components.h').write_text('#define CONFIG_HTTPS_PROTOCOL 1\n#define CONFIG_TLS_PROTOCOL 1\n')
        (self.root/'build/ffbuild/config.log').write_text('# ./configure --enable-ohcodec --enable-protocol=https,tls\n')
        (self.root/'SOURCE.txt').write_text('ffmpeg_commit=140fd653aed8cad774f991ba083e2d01e86420c7\nbuilder_commit=1bab837e662ffa47ce51efd0720d3ed7c4988944\n')

    def run_finalize(self, elf='  Machine: AArch64\n'):
        with patch.object(module.subprocess, 'check_output', return_value=elf):
            module.finalize(self.root, Path('/ndk'))

    def test_valid_prefix(self):
        self.run_finalize()
        self.assertIn('https_protocol=enabled', (self.root/'prefix/VERSION').read_text())
        self.assertIn('lib/libavcodec.so.62', (self.root/'prefix/MANIFEST.tsv').read_text())
        self.assertTrue((self.root/'prefix/licenses/GPL-3.0-or-later.txt').is_file())

    def test_missing_tls_rejected(self):
        (self.root/'build/config_components.h').write_text('#define CONFIG_HTTPS_PROTOCOL 1\n#define CONFIG_TLS_PROTOCOL 0\n')
        with self.assertRaises(ValueError): self.run_finalize()
        self.assertFalse((self.root/'prefix/VERSION').exists())

    def test_missing_library_rejected(self):
        (self.root/'prefix/lib/libavutil.so.60').unlink()
        with self.assertRaises(FileNotFoundError): self.run_finalize()

    def test_wrong_arch_rejected(self):
        with self.assertRaises(ValueError): self.run_finalize('Machine: X86-64\n')

    def test_dynamic_smb_rejected(self):
        with self.assertRaises(ValueError): self.run_finalize('Machine: AArch64\n Shared library: [libsmbclient.so]\n')

if __name__ == '__main__': unittest.main()
