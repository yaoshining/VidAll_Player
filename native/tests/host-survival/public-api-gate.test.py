"""正式及内部注入核心必须保持同一公开 ABI，拒绝缺失和泄漏。"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'native/tooling/normal-core'))
from public_api_gate import require_public_api

API = json.loads((ROOT / 'release/inputs/004-normal-core/provenance/host-recovery-static-validation.json').read_text())['api']


class PublicApiGateTest(unittest.TestCase):
    def test_current_normal_and_internal_diagnostic_keep_same_abi(self):
        # 注入函数是内部符号，不增加已废弃的公开 waiting 函数。
        for label in ['normal', 'internal-global-probe']:
            with self.subTest(label=label):
                actual = set(API['publicSymbols'])
                extension = require_public_api(actual, API['preservedBaselineSymbols'])
                self.assertEqual(extension, set(API['extensionSymbols']))
                self.assertEqual(len(actual), 64)

    def test_every_existing_or_recovery_export_is_required(self):
        for symbol in API['publicSymbols']:
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                require_public_api(set(API['publicSymbols']) - {symbol}, API['preservedBaselineSymbols'])

    def test_extra_and_internal_symbols_are_rejected(self):
        for symbol in ['mpv_ohcodec_handoff_test_waiting', 'mpv_unexpected',
                       'mp_host_audio_begin', 'mp_ohcodec_terminal_enter_context',
                       'host_probe_enter']:
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                require_public_api(set(API['publicSymbols']) | {symbol}, API['preservedBaselineSymbols'])

    def test_baseline_inventory_is_not_relaxed(self):
        baseline = API['preservedBaselineSymbols']
        for invalid in [baseline[:-1], baseline + ['mpv_unknown'], baseline[:-1] + [baseline[0]]]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                require_public_api(set(API['publicSymbols']), invalid)


if __name__ == '__main__':
    unittest.main()
