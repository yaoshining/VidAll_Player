import unittest
from report import summarize

class ReportTests(unittest.TestCase):
    def test_success_and_failure(self):
        steps = {'target': {'outcome': 'success'}, 'consumer': {'outcome': 'failure'}}
        reports = {'consumer': {'commands': [{'name': 'consumer-build', 'exit': 1, 'args': ['private-value']}]}}
        report = summarize(steps, reports)
        self.assertEqual(report['consumer'], {'outcome': 'failure', 'failedCommands': [{'name': 'consumer-build', 'exit': 1}]})
        self.assertEqual(report['target']['outcome'], 'success')
        self.assertEqual(report['cleanup']['outcome'], 'unknown')
        self.assertNotIn('private-value', str(report))

    def test_archive_outcome(self):
        for outcome in ('skipped', 'success', 'failure'):
            with self.subTest(outcome=outcome):
                self.assertEqual(summarize({'archive': {'outcome': outcome}}, {})['archive']['outcome'], outcome)

    def test_x86_stage_and_command(self):
        reports = {'target': {'commands': [{'name': 'x86-input-audit', 'exit': 1}]}}
        result = summarize({'x86-contracts': {'outcome': 'success'}, 'target': {'outcome': 'failure'}}, reports)
        self.assertEqual(result['x86-contracts']['outcome'], 'success')
        self.assertEqual(result['target']['failedCommands'], [{'name': 'x86-input-audit', 'exit': 1}])

    def test_omit_unknown_data(self):
        reports = {'target': {'error': 'private', 'commands': [{'name':'private','exit':1}]}}
        self.assertEqual(summarize({}, reports)['target'], {'outcome':'unknown', 'failedCommands':[]})

if __name__ == '__main__':
    unittest.main()
