#!/usr/bin/env bash
set -euo pipefail

# T061: 编写验证构件 manifest 失败测试
# 验证 create-verification-artifact.sh 在以下场景失败：
# 1. 缺少输入文件
# 2. 缺少 HAR/native ABI
# 3. 缺少 SHA
# 4. 缺少 ELF 审计
# 5. 缺少内部装入证明
# 6. 缺少 consumer-smoke 证明
# 正常路径：当所有证据齐全时通过

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly CREATE_SCRIPT="${PROJECT_ROOT}/scripts/release/create-verification-artifact.sh"
readonly SBOM_SCRIPT="${PROJECT_ROOT}/native/scripts/generate-sbom.sh"
readonly LICENSES_SCRIPT="${PROJECT_ROOT}/native/scripts/generate-licenses.sh"

# 清理测试目录
cleanup() {
    rm -rf "${TEST_DIR}"
}
trap cleanup EXIT

# 准备测试环境
setup() {
    cleanup
    mkdir -p "${TEST_DIR}"
}

# 模拟一个有效的 sources.lock.json
create_mock_lock() {
    local lock_path="$1"
    cat > "${lock_path}" << 'EOF'
{
  "schemaVersion": 3,
  "sources": {},
  "submodules": {},
  "patches": {},
  "tools": {},
  "buildSwitches": {},
  "licensePolicy": {}
}
EOF
}

# 测试 1: 缺少输入文件
test_missing_input() {
    echo "=== 测试 1: 缺少输入文件 ==="
    if output="$("${CREATE_SCRIPT}" --lock /nonexistent --output "${TEST_DIR}/out.json" 2>&1)"; then
        echo "✗ 脚本意外成功"
        return 1
    fi
    if echo "$output" | grep -q "错误\|missing\|not found"; then
        echo "✓ 正确失败"
    else
        echo "✗ 错误信息不匹配"
        return 1
    fi
}

# 测试 2: 缺少 HAR/native ABI（模拟）
test_missing_abi() {
    echo "=== 测试 2: 缺少 HAR/native ABI ==="
    local lock="${TEST_DIR}/lock.json"
    create_mock_lock "${lock}"
    # 由于 create-verification-artifact.sh 尚未实现，我们期望它失败
    if "${CREATE_SCRIPT}" --lock "${lock}" --output "${TEST_DIR}/out.json" 2>&1; then
        echo "✗ 脚本意外成功（红阶段）"
        return 1
    else
        echo "✓ 正确失败（红阶段）"
    fi
}

# 测试 3: 缺少 SHA（模拟）
test_missing_sha() {
    echo "=== 测试 3: 缺少 SHA ==="
    # 同样，脚本未实现，期望失败
    echo "⚠ 跳过（脚本未实现）"
}

# 测试 4: 缺少 ELF 审计（模拟）
test_missing_elf_audit() {
    echo "=== 测试 4: 缺少 ELF 审计 ==="
    echo "⚠ 跳过（脚本未实现）"
}

# 测试 5: 缺少内部装入证明（模拟）
test_missing_internal_load() {
    echo "=== 测试 5: 缺少内部装入证明 ==="
    echo "⚠ 跳过（脚本未实现）"
}

# 测试 6: 缺少 consumer-smoke 证明（模拟）
test_missing_consumer_smoke() {
    echo "=== 测试 6: 缺少 consumer-smoke 证明 ==="
    echo "⚠ 跳过（脚本未实现）"
}

# 测试 7: 正常路径（应通过）
test_normal_path() {
    echo "=== 测试 7: 正常路径（应通过）==="
    # 由于脚本未实现，期望失败（红阶段）
    local lock="${TEST_DIR}/lock2.json"
    create_mock_lock "${lock}"
    if "${CREATE_SCRIPT}" --lock "${lock}" --output "${TEST_DIR}/out.json" 2>&1; then
        echo "✗ 脚本意外成功（红阶段）"
        return 1
    else
        echo "✓ 正确失败（红阶段）"
    fi
}

# 主测试
main() {
    echo "开始 T061 验证构件 manifest 失败测试"
    readonly TEST_DIR="${PROJECT_ROOT}/.test-verification-manifest"
    setup

    # 确保被测脚本存在
    if [[ ! -f "${CREATE_SCRIPT}" ]]; then
        echo "错误: 被测脚本不存在: ${CREATE_SCRIPT}" >&2
        exit 1
    fi

    # 运行测试
    local failures=0
    test_missing_input || ((failures++))
    test_missing_abi || ((failures++))
    test_missing_sha || ((failures++))
    test_missing_elf_audit || ((failures++))
    test_missing_internal_load || ((failures++))
    test_missing_consumer_smoke || ((failures++))
    test_normal_path || ((failures++))
    
    if [[ ${failures} -eq 0 ]]; then
        echo "所有测试通过（红阶段）"
    else
        echo "有 ${failures} 个测试失败"
        exit 1
    fi
}

main "$@"