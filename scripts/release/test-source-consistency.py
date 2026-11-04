#!/usr/bin/env python3
"""来源核对回归：声明相符不能代替二进制和完整闭包证明。"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('audit-source-consistency.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SourceConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'LICENSE').write_text('许可原文')
        self.record = {'path': 'LICENSE', 'sha256': hashlib.sha256((self.root / 'LICENSE').read_bytes()).hexdigest()}
        self.lock = {'sources': {'mpv': {'commit': 'a' * 40, 'tag': '1', 'repository': 'https://example.test/mpv', 'license': 'MIT'}}}
        self.cdx = {'components': [{'name': 'mpv', 'version': '1', 'licenses': [{'license': {'id': 'MIT'}}], 'externalReferences': [{'type': 'vcs', 'url': 'https://example.test/mpv@' + 'a' * 40}]}]}
        self.spdx = {'packages': [{'name': 'mpv', 'versionInfo': '1', 'downloadLocation': 'https://example.test/mpv', 'licenseDeclared': 'MIT', 'externalRefs': [{'referenceType': 'git', 'referenceLocator': 'a' * 40}]}]}
        self.observed = {'closureComplete': True, 'sourceRebuildVerified': True, 'binaryBindingVerified': True, 'components': [{'name': 'mpv', 'commit': 'a' * 40, 'dirty': False, 'evidenceLevel': 'source-rebuild-verified', 'licenseFiles': ['LICENSE']}], 'materials': [self.record]}

    def test_duplicate_material_is_ambiguous(self):
        self.observed['materials'].append(dict(self.record))
        self.assertIn('duplicate-material', self.codes())

    def test_empty_dependency_set_is_not_evidence(self):
        result = audit.audit({'sources': {}}, {'components': []}, {'packages': []},
                             {**self.observed, 'components': [], 'materials': []}, self.root)
        self.assertEqual(result['status'], 'blocked')

    def run_audit(self):
        return audit.audit(self.lock, self.cdx, self.spdx, self.observed, self.root)

    def codes(self):
        return {x['code'] for x in self.run_audit()['issues']}

    def test_complete_matching_input_passes(self):
        self.assertEqual(self.run_audit()['status'], 'passed')

    def test_actual_commit_mismatch_is_not_hidden_by_matching_sboms(self):
        self.observed['components'][0]['commit'] = 'b' * 40
        self.assertIn('observed-commit-mismatch', self.codes())

    def test_missing_component_and_extra_transitive_are_reported(self):
        self.observed['components'][0]['name'] = 'transitive'
        self.assertTrue({'locked-component-unverified', 'observed-component-unlocked'} <= self.codes())

    def test_declared_sboms_are_checked_independently(self):
        self.cdx['components'][0]['version'] = 'wrong'
        self.spdx['packages'][0]['licenseDeclared'] = 'wrong'
        self.assertTrue({'cdx-lock-mismatch', 'spdx-lock-mismatch'} <= self.codes())

    def test_deleted_sbom_component_fails(self):
        self.cdx['components'] = []
        self.assertIn('cdx-component-set-mismatch', self.codes())

    def test_duplicate_observation_is_rejected(self):
        self.observed['components'].append(copy.deepcopy(self.observed['components'][0]))
        self.assertIn('duplicate-component', self.codes())

    def test_unknown_commit_does_not_pass(self):
        self.observed['components'][0]['commit'] = None
        self.assertIn('observed-revision-unverified', self.codes())

    def test_cached_tree_and_dirty_patch_do_not_prove_rebuild(self):
        self.observed.update(sourceRebuildVerified=False, closureComplete=False)
        self.observed['components'][0].update(dirty=True, evidenceLevel='cached-build-record')
        self.assertTrue({'source-rebuild-unverified', 'closure-incomplete', 'dirty-source-not-in-lock', 'source-binding-unverified'} <= self.codes())

    def test_missing_or_modified_license_is_rejected(self):
        (self.root / 'LICENSE').write_text('变更')
        self.assertIn('material-integrity-failed', self.codes())
        (self.root / 'LICENSE').unlink()
        self.assertIn('material-integrity-failed', self.codes())

    def test_license_reference_must_be_indexed(self):
        self.observed['materials'] = []
        self.assertIn('license-material-missing', self.codes())

    def test_traversal_cannot_supply_evidence(self):
        self.record['path'] = '../LICENSE'
        self.assertIn('material-integrity-failed', self.codes())

    def test_no_binary_binding_fails(self):
        self.observed['binaryBindingVerified'] = False
        self.assertIn('binary-binding-unverified', self.codes())

    def test_tool_version_mismatch_fails(self):
        self.observed['toolVersionObservation'] = {'status': 'mismatch'}
        self.assertIn('tool-version-mismatch', self.codes())

    def test_observed_sboms_match_versions_and_revision(self):
        self.observed['components'][0]['version'] = '1'
        cdx = {'components': [{'name': 'mpv', 'version': '1', 'properties': [{'name': 'vidall:source-commit', 'value': 'a' * 40}]}]}
        spdx = {'packages': [{'name': 'mpv', 'versionInfo': '1', 'licenseConcluded': 'NOASSERTION'}]}
        self.assertEqual(audit.check_observed_sboms(self.observed, cdx, spdx), [])
        cdx['components'][0]['version'] = '2'
        self.assertTrue(audit.check_observed_sboms(self.observed, cdx, spdx))

    def test_observed_sboms_cannot_claim_license_review_or_drop_components(self):
        self.observed['components'][0]['version'] = '1'
        cdx = {'components': []}
        spdx = {'packages': [{'name': 'mpv', 'versionInfo': '1', 'licenseConcluded': 'MIT'}]}
        codes = {i['code'] for i in audit.check_observed_sboms(self.observed, cdx, spdx)}
        self.assertTrue({'observed-cdx-mismatch', 'observed-spdx-mismatch'} <= codes)


if __name__ == '__main__':
    unittest.main()
