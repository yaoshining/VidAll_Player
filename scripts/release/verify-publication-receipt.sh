#!/bin/bash
set -e

# T066 验证发布回读收据
# 检查双渠道一致性和状态转换

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
    echo "用法: $0 <候选构件manifest路径>"
    echo "检查双渠道发布的一致性和完整性"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

CANDIDATE_MANIFEST="$1"

if [ ! -f "$CANDIDATE_MANIFEST" ]; then
    echo "错误：候选构件manifest文件不存在: $CANDIDATE_MANIFEST" >&2
    exit 1
fi

# 验证收据
python3 -c "
import json, sys, hashlib, datetime

def validate_receipt(receipt_str, channel_name, expected_version, expected_sha256):
    '''验证单个渠道的收据'''
    if not receipt_str:
        return False, f'{channel_name}: 无收据'
    
    try:
        receipt = json.loads(receipt_str)
    except json.JSONDecodeError:
        return False, f'{channel_name}: 收据不是有效的 JSON'
    
    required_fields = ['version', 'sha256', 'timestamp']
    for field in required_fields:
        if field not in receipt:
            return False, f'{channel_name}: 收据缺少字段 {field}'
    
    if receipt['version'] != expected_version:
        return False, f'{channel_name}: 版本不一致 (期望: {expected_version}, 实际: {receipt[\"version\"]})'
    
    if receipt['sha256'] != expected_sha256:
        return False, f'{channel_name}: SHA256 不一致 (期望: {expected_sha256}, 实际: {receipt[\"sha256\"]})'
    
    # 验证时间戳格式
    try:
        datetime.datetime.fromisoformat(receipt['timestamp'].replace('Z', '+00:00'))
    except ValueError:
        return False, f'{channel_name}: 时间戳格式无效: {receipt[\"timestamp\"]}'
    
    return True, f'{channel_name}: 收据有效'

try:
    manifest_path = sys.argv[1]
    with open(manifest_path, 'r') as f:
        candidate = json.load(f)
    
    # 验证基本结构
    if candidate.get('artifactType') != 'candidate':
        print('错误：artifactType 必须是 \"candidate\"', file=sys.stderr)
        sys.exit(1)
    
    status = candidate.get('status', '')
    if status not in ['candidate', 'published', 'failed']:
        print(f'错误：无效状态: {status}', file=sys.stderr)
        sys.exit(1)
    
    version = candidate.get('version', '')
    sha256 = candidate.get('sha256', '')
    
    if not version or not sha256:
        print('错误：版本或 SHA256 缺失', file=sys.stderr)
        sys.exit(1)
    
    channels = candidate.get('channels', {})
    if not isinstance(channels, dict):
        print('错误：channels 必须是对象', file=sys.stderr)
        sys.exit(1)
    
    required_channels = ['github', 'private']
    for channel in required_channels:
        if channel not in channels:
            print(f'错误：缺少渠道: {channel}', file=sys.stderr)
            sys.exit(1)
    
    # 检查各渠道状态
    all_uploaded = True
    any_uploaded = False
    channel_results = []
    
    for channel_name in required_channels:
        channel = channels[channel_name]
        uploaded = channel.get('uploaded', False)
        url = channel.get('url', '')
        receipt = channel.get('receipt', '')
        
        if uploaded:
            any_uploaded = True
            if not url:
                print(f'错误：{channel_name} 已上传但缺少 URL', file=sys.stderr)
                sys.exit(1)
            
            valid, message = validate_receipt(receipt, channel_name, version, sha256)
            if not valid:
                print(f'错误：{message}', file=sys.stderr)
                sys.exit(1)
            channel_results.append(f'✓ {message}')
        else:
            all_uploaded = False
            if url or receipt:
                print(f'警告：{channel_name} 未上传但有 URL 或收据', file=sys.stderr)
            channel_results.append(f'⏸️ {channel_name}: 未上传')
    
    # 状态转换验证
    if status == 'candidate':
        if all_uploaded:
            print('警告：所有渠道已上传但状态仍为 candidate', file=sys.stderr)
            print('建议更新状态为 published', file=sys.stderr)
        elif not any_uploaded:
            print('状态: candidate (等待上传)')
        else:
            print('状态: candidate (部分渠道已上传)')
    
    elif status == 'published':
        if not all_uploaded:
            print('错误：状态为 published 但并非所有渠道都已上传', file=sys.stderr)
            sys.exit(1)
        print('状态: published (所有渠道已验证)')
    
    elif status == 'failed':
        print('状态: failed (发布失败)')
    
    # 输出渠道结果
    print('\n渠道状态:')
    for result in channel_results:
        print(f'  {result}')
    
    # 检查双渠道一致性
    if any_uploaded and not all_uploaded:
        print('\n警告：部分渠道已上传，部分未上传')
        print('建议：要么全部上传，要么全部不上传')
    
    if all_uploaded:
        print('\n✓ 双渠道发布验证通过')
        print(f'版本: {version}')
        print(f'SHA256: {sha256}')
        print('所有渠道收据一致')
    else:
        print('\n⏸️ 发布未完成')
        print('需要完成所有渠道的上传')
    
except Exception as e:
    print(f'错误：验证失败: {e}', file=sys.stderr)
    sys.exit(1)
" "$CANDIDATE_MANIFEST" || exit 1

echo "收据验证完成"