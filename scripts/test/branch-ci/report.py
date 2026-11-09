"""从步骤结果和构建记录生成可公开的白名单摘要。"""
import argparse
import json
import os
from pathlib import Path

STAGES = ('checkout', 'init', 'context', 'runtime', 'archive', 'target', 'negative', 'consumer', 'hypium', 'cleanup', 'har')
RESULT_FILES = {'target': 'evaluation-result.json', 'negative': 'consumer-negative-result.json',
                'consumer': 'consumer-result.json', 'hypium': 'hypium-result.json'}
COMMANDS = {'cli-version', 'node-version', 'clean', 'input-audit', 'har-build', 'bridge-undefined',
            'bridge-dynamic', 'consumer-negative-clean', 'consumer-negative-build', 'consumer-clean',
            'consumer-build', 'hypium-clean', 'hypium-build'}
OUTCOMES = {'success', 'failure', 'cancelled', 'skipped'}

def summarize(steps, reports):
    summary = {}
    for stage in STAGES:
        outcome = steps.get(stage, {}).get('outcome')
        row = {'outcome': outcome if outcome in OUTCOMES else 'unknown', 'failedCommands': []}
        if outcome == 'failure':
            for command in reports.get(stage, {}).get('commands', []):
                name, code = command.get('name'), command.get('exit')
                if name in COMMANDS and type(code) is int and code != 0:
                    row['failedCommands'].append({'name': name, 'exit': code})
        summary[stage] = row
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    reports = {}
    if os.environ.get('CI_OUT'):
        work = Path(os.environ['CI_OUT']) / 'work'
        for stage, filename in RESULT_FILES.items():
            try:
                reports[stage] = json.loads((work / filename).read_text())
            except (FileNotFoundError, ValueError):
                continue
    args.output.mkdir(parents=True, exist_ok=True)
    summary = summarize(json.loads(os.environ['CI_STEPS']), reports)
    (args.output/'stages.json').write_text(json.dumps(summary, indent=2)+'\n')
