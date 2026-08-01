#!/bin/bash
set -e

# T066 双渠道发布脚本
# 处理 GitHub Release 和私有 ohpm 源的上传

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
    echo "用法: $0 <候选构件manifest路径>"
    echo "环境变量:"
    echo "  GITHUB_TOKEN: GitHub API token (发布到 GitHub Release)"
    echo "  PRIVATE_REGISTRY_TOKEN: 私有 ohpm 源 token"
    echo "  DRY_RUN: 设置为任意值进行干跑测试"
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

# 验证候选构件
if ! python3 -c "
import json, sys
try:
    with open('$CANDIDATE_MANIFEST', 'r') as f:
        data = json.load(f)
    
    if data.get('artifactType') != 'candidate':
        print('错误：artifactType 必须是 \"candidate\"', file=sys.stderr)
        sys.exit(1)
    
    if data.get('status') != 'candidate':
        print('错误：候选构件状态必须是 \"candidate\"', file=sys.stderr)
        sys.exit(1)
    
    required_fields = ['version', 'sha256', 'channels']
    for field in required_fields:
        if field not in data:
            print(f'错误：候选构件缺少必需字段: {field}', file=sys.stderr)
            sys.exit(1)
    
    print('候选构件验证通过')
except Exception as e:
    print(f'错误：候选构件验证失败: {e}', file=sys.stderr)
    sys.exit(1)
"; then
    exit 1
fi

# 检查凭据
if [ -z "$GITHUB_TOKEN" ] && [ -z "$PRIVATE_REGISTRY_TOKEN" ]; then
    echo "错误：需要至少一个渠道的凭据" >&2
    echo "请设置 GITHUB_TOKEN 或 PRIVATE_REGISTRY_TOKEN 环境变量" >&2
    exit 1
fi

# 读取候选构件信息
VERSION=$(python3 -c "import json; print(json.load(open('$CANDIDATE_MANIFEST'))['version'])")
SHA256=$(python3 -c "import json; print(json.load(open('$CANDIDATE_MANIFEST'))['sha256'])")

echo "=== 双渠道发布候选构件 ==="
echo "版本: $VERSION"
echo "SHA256: $SHA256"
echo "干跑测试: ${DRY_RUN:+是}${DRY_RUN:-否}"

# GitHub Release 发布（模拟）
if [ -n "$GITHUB_TOKEN" ]; then
    echo "发布到 GitHub Release..."
    if [ -n "$DRY_RUN" ]; then
        echo "[干跑] 将创建 GitHub Release: v$VERSION"
        echo "[干跑] 将上传构件并生成收据"
        GITHUB_RECEIPT="{\"version\":\"$VERSION\",\"sha256\":\"$SHA256\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"url\":\"https://github.com/yaoshining/VidAll_Player/releases/tag/v$VERSION\"}"
    else
        echo "错误：GitHub Release 发布需要实际实现" >&2
        echo "请实现 GitHub API 集成" >&2
        GITHUB_RECEIPT=""
    fi
else
    echo "跳过 GitHub Release (无 GITHUB_TOKEN)"
    GITHUB_RECEIPT=""
fi

# 私有 ohpm 源发布（模拟）
if [ -n "$PRIVATE_REGISTRY_TOKEN" ]; then
    echo "发布到私有 ohpm 源..."
    if [ -n "$DRY_RUN" ]; then
        echo "[干跑] 将上传到私有 ohpm 源"
        echo "[干跑] 将生成发布收据"
        PRIVATE_RECEIPT="{\"version\":\"$VERSION\",\"sha256\":\"$SHA256\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"url\":\"https://private.ohpm.example.com/@vidall/player/v$VERSION\"}"
    else
        echo "错误：私有 ohpm 源发布需要实际实现" >&2
        echo "请实现 ohpm 发布集成" >&2
        PRIVATE_RECEIPT=""
    fi
else
    echo "跳过私有 ohpm 源 (无 PRIVATE_REGISTRY_TOKEN)"
    PRIVATE_RECEIPT=""
fi

# 更新候选构件状态
if [ -n "$DRY_RUN" ]; then
    echo "=== 干跑测试完成 ==="
    echo "GitHub 收据: ${GITHUB_RECEIPT:-(无)}"
    echo "私有源收据: ${PRIVATE_RECEIPT:-(无)}"
    echo "注意：实际发布需要实现 GitHub API 和 ohpm 发布集成"
else
    # 实际实现中，这里会更新候选构件文件
    echo "错误：发布功能需要实际实现" >&2
    echo "请实现 GitHub API 和 ohpm 发布集成" >&2
    exit 1
fi

echo "发布流程完成（干跑模式）"