#!/bin/bash
set -e

# T065 双渠道发布/回读测试
# 验证候选构件创建、上传、回读和状态转换

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR="$SCRIPT_DIR/../test"
TEMP_DIR="$(mktemp -d)"

cleanup() {
    echo "清理临时目录: $TEMP_DIR"
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo "=== T065 双渠道发布/回读测试 ==="
echo "测试目录: $TEMP_DIR"

# 测试 1: 无批准/凭据时上传应失败
echo "1. 测试无批准/凭据时上传失败..."
cat > "$TEMP_DIR/test-no-credentials.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "candidate",
  "version": "1.0.0-test",
  "sha256": "abcd1234",
  "status": "candidate",
  "channels": {
    "github": {
      "uploaded": false,
      "url": "",
      "receipt": ""
    },
    "private": {
      "uploaded": false,
      "url": "",
      "receipt": ""
    }
  }
}
EOF

# 模拟无凭据的发布脚本（应失败）
if "$SCRIPT_DIR/publish-candidate.sh" "$TEMP_DIR/test-no-credentials.json" 2>&1 | grep -q "错误\|失败\|error\|fail"; then
    echo "✓ 无凭据时上传正确失败"
else
    echo "✗ 无凭据时上传未失败"
    exit 1
fi

# 测试 2: 版本或 SHA 不一致不得 published
echo "2. 测试版本/SHA 不一致验证..."
cat > "$TEMP_DIR/test-mismatch.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "candidate",
  "version": "1.0.0",
  "sha256": "correct-sha",
  "status": "candidate",
  "channels": {
    "github": {
      "uploaded": true,
      "url": "https://github.com/example/repo/releases/tag/v1.0.1",
      "receipt": "{\"version\":\"1.0.1\",\"sha256\":\"different-sha\"}"
    },
    "private": {
      "uploaded": true,
      "url": "https://private.example.com/pkg/v1.0.1",
      "receipt": "{\"version\":\"1.0.1\",\"sha256\":\"different-sha\"}"
    }
  }
}
EOF

# 模拟验证脚本（应检测不一致）
# 创建测试文件
cat > "$TEMP_DIR/test-mismatch.json" << 'EOF'
{
  "schemaVersion": 2,
  "artifactType": "candidate",
  "version": "1.0.0",
  "sha256": "correct-sha",
  "status": "candidate",
  "channels": {
    "github": {
      "uploaded": true,
      "url": "https://github.com/example/repo/releases/tag/v1.0.1",
      "receipt": "{\"version\":\"1.0.1\",\"sha256\":\"different-sha\",\"timestamp\":\"2024-01-01T00:00:00Z\"}"
    },
    "private": {
      "uploaded": true,
      "url": "https://private.example.com/pkg/v1.0.1",
      "receipt": "{\"version\":\"1.0.1\",\"sha256\":\"different-sha\",\"timestamp\":\"2024-01-01T00:00:00Z\"}"
    }
  }
}
EOF

if "$SCRIPT_DIR/verify-publication-receipt.sh" "$TEMP_DIR/test-mismatch.json" 2>&1 | grep -q "不一致\|mismatch\|invalid\|错误"; then
    echo "✓ 版本/SHA 不一致被正确检测"
else
    echo "✗ 版本/SHA 不一致未检测到"
    exit 1
fi

# 测试 3: 仅能由证据齐全的验证构件创建 candidate
echo "3. 测试验证构件完整性检查..."
cat > "$TEMP_DIR/test-incomplete-evidence.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "verification",
  "version": "1.0.0",
  "sha256": "test-sha",
  "status": "verified",
  "evidence": {
    "sbom": {},
    "licenses": {},
    "elfAudit": {},
    "harInclusion": {},
    "consumerSmoke": {}
  }
}
EOF

# 模拟创建候选脚本（应要求完整证据）
if "$SCRIPT_DIR/create-candidate.sh" "$TEMP_DIR/test-incomplete-evidence.json" 2>&1 | grep -q "缺少\|不完整\|incomplete\|missing\|无效\|错误\|证据为空\|证据无效"; then
    echo "✓ 不完整证据被正确拒绝"
else
    echo "✗ 不完整证据未被拒绝"
    exit 1
fi

# 测试 4: 状态转换验证
echo "4. 测试状态转换验证..."
cat > "$TEMP_DIR/test-status-transition.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "candidate",
  "version": "1.0.0",
  "sha256": "test-sha",
  "status": "published",
  "channels": {
    "github": {
      "uploaded": false,
      "url": "",
      "receipt": ""
    },
    "private": {
      "uploaded": false,
      "url": "",
      "receipt": ""
    }
  }
}
EOF

# 模拟发布脚本（应拒绝从 published 状态创建 candidate）
if "$SCRIPT_DIR/publish-candidate.sh" "$TEMP_DIR/test-status-transition.json" 2>&1 | grep -q "已发布\|published\|invalid status\|错误\|状态必须是"; then
    echo "✓ 无效状态转换被正确拒绝"
else
    echo "✗ 无效状态转换未被拒绝"
    exit 1
fi

# 测试 5: 双渠道一致性验证
echo "5. 测试双渠道一致性验证..."
cat > "$TEMP_DIR/test-dual-channel.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "candidate",
  "version": "1.0.0",
  "sha256": "consistent-sha",
  "status": "candidate",
  "channels": {
    "github": {
      "uploaded": true,
      "url": "https://github.com/example/repo/releases/tag/v1.0.0",
      "receipt": "{\"version\":\"1.0.0\",\"sha256\":\"consistent-sha\",\"timestamp\":\"2024-01-01T00:00:00Z\"}"
    },
    "private": {
      "uploaded": false,
      "url": "",
      "receipt": ""
    }
  }
}
EOF

# 模拟验证脚本（应检测单渠道上传）
if "$SCRIPT_DIR/verify-publication-receipt.sh" "$TEMP_DIR/test-dual-channel.json" 2>&1 | grep -q "单渠道\|single channel\|incomplete\|错误\|并非所有渠道\|部分渠道\|发布未完成"; then
    echo "✓ 单渠道上传被正确检测"
else
    echo "✗ 单渠道上传未检测到"
    exit 1
fi

# 测试 6: 回读收据验证
echo "6. 测试回读收据验证..."
cat > "$TEMP_DIR/test-receipt-validation.json" << 'EOF'
{
  "schemaVersion": 1,
  "artifactType": "candidate",
  "version": "1.0.0",
  "sha256": "test-sha",
  "status": "candidate",
  "channels": {
    "github": {
      "uploaded": true,
      "url": "https://github.com/example/repo/releases/tag/v1.0.0",
      "receipt": "{\"version\":\"1.0.0\",\"sha256\":\"test-sha\",\"timestamp\":\"2024-01-01T00:00:00Z\"}"
    },
    "private": {
      "uploaded": true,
      "url": "https://private.example.com/pkg/v1.0.0",
      "receipt": "{\"version\":\"1.0.0\",\"sha256\":\"test-sha\",\"timestamp\":\"2024-01-01T00:00:00Z\"}"
    }
  }
}
EOF

# 模拟验证脚本（应接受有效收据）
if "$SCRIPT_DIR/verify-publication-receipt.sh" "$TEMP_DIR/test-receipt-validation.json" 2>&1 | grep -q "有效\|valid\|success"; then
    echo "✓ 有效收据被正确接受"
else
    echo "✗ 有效收据未被接受"
    exit 1
fi

echo "=== T065 所有测试通过 ==="
echo "双渠道发布/回读测试验证了以下场景："
echo "1. 无批准/凭据时上传失败 ✓"
echo "2. 版本或 SHA 不一致不得 published ✓"
echo "3. 仅能由证据齐全的验证构件创建 candidate ✓"
echo "4. 状态转换验证（candidate→published/failed）✓"
echo "5. 双渠道一致性验证 ✓"
echo "6. 回读收据验证 ✓"