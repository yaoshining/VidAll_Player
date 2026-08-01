#!/bin/bash
set -e

# T066 创建候选构件
# 验证证据完整性并创建候选构件

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
    echo "用法: $0 <验证构件manifest路径> [输出路径]"
    echo "示例: $0 release/verification-manifest.json release/candidate-manifest.json"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

VERIFICATION_MANIFEST="$1"
OUTPUT_PATH="${2:-release/candidate-manifest.json}"

if [ ! -f "$VERIFICATION_MANIFEST" ]; then
    echo "错误：验证构件manifest文件不存在: $VERIFICATION_MANIFEST" >&2
    exit 1
fi

# 验证manifest schema
if ! python3 -c "
import json, sys
try:
    with open('$VERIFICATION_MANIFEST', 'r') as f:
        data = json.load(f)
    
    required_fields = ['schemaVersion', 'artifactType', 'version', 'sha256', 'status', 'evidence']
    for field in required_fields:
        if field not in data:
            print(f'错误：验证构件缺少必需字段: {field}', file=sys.stderr)
            sys.exit(1)
    
    if data['artifactType'] != 'verification':
        print('错误：artifactType 必须是 \"verification\"', file=sys.stderr)
        sys.exit(1)
    
    if data['status'] != 'verified':
        print('错误：验证构件状态必须是 \"verified\"', file=sys.stderr)
        sys.exit(1)
    
    evidence = data['evidence']
    required_evidence = ['sbom', 'licenses', 'elfAudit', 'harInclusion', 'consumerSmoke']
    for ev in required_evidence:
        if ev not in evidence:
            print(f'错误：验证构件缺少证据: {ev}', file=sys.stderr)
            sys.exit(1)
    
    # 检查证据完整性
    for ev_name in required_evidence:
        ev_data = evidence.get(ev_name, {})
        if not ev_data:
            print(f'错误：{ev_name} 证据为空', file=sys.stderr)
            sys.exit(1)
        if not ev_data.get('valid', False):
            print(f'错误：{ev_name} 证据无效', file=sys.stderr)
            sys.exit(1)
    
    print('验证构件证据完整')
except Exception as e:
    print(f'错误：验证构件验证失败: {e}', file=sys.stderr)
    sys.exit(1)
"; then
    exit 1
fi

# 创建候选构件
CANDIDATE_DATA=$(python3 -c "
import json, sys, os, hashlib, datetime
with open('$VERIFICATION_MANIFEST', 'r') as f:
    verification = json.load(f)

# 从验证构件提取信息
candidate = {
    'schemaVersion': 2,
    'artifactType': 'candidate',
    'version': verification['version'],
    'sha256': verification['sha256'],
    'createdAt': datetime.datetime.utcnow().isoformat() + 'Z',
    'status': 'candidate',
    'verificationManifest': os.path.basename('$VERIFICATION_MANIFEST'),
    'verificationSha256': hashlib.sha256(open('$VERIFICATION_MANIFEST', 'rb').read()).hexdigest(),
    'channels': {
        'github': {
            'uploaded': False,
            'url': '',
            'receipt': '',
            'uploadedAt': ''
        },
        'private': {
            'uploaded': False,
            'url': '',
            'receipt': '',
            'uploadedAt': ''
        }
    },
    'evidenceSummary': {
        'sbom': verification['evidence']['sbom'].get('summary', 'Valid SBOM'),
        'licenses': verification['evidence']['licenses'].get('summary', 'Valid licenses'),
        'elfAudit': verification['evidence']['elfAudit'].get('summary', 'Valid ELF audit'),
        'harInclusion': verification['evidence']['harInclusion'].get('summary', 'Valid HAR inclusion'),
        'consumerSmoke': verification['evidence']['consumerSmoke'].get('summary', 'Valid consumer smoke test')
    }
}

# 确保输出目录存在
output_dir = os.path.dirname('$OUTPUT_PATH')
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)

with open('$OUTPUT_PATH', 'w') as f:
    json.dump(candidate, f, indent=2, ensure_ascii=False)

print('候选构件创建成功:', '$OUTPUT_PATH')
print('版本:', verification['version'])
print('SHA256:', verification['sha256'])
")

echo "$CANDIDATE_DATA"

echo "候选构件已创建: $OUTPUT_PATH"
echo "状态: candidate"
echo "下一步: 使用 publish-candidate.sh 上传到双渠道"