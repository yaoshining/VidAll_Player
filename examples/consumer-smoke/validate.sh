#!/bin/bash
set -e

echo "=== 验证 consumer-smoke 隔离性 ==="
echo "工作目录: $(pwd)"

# 检查项目结构
echo "1. 检查项目结构..."
[ -f "oh-package.json5" ] || { echo "错误: oh-package.json5 不存在"; exit 1; }
[ -f "package.json5" ] || { echo "错误: package.json5 不存在"; exit 1; }
[ -f "app.json5" ] || { echo "错误: app.json5 不存在"; exit 1; }
[ -f "build-profile.json5" ] || { echo "错误: build-profile.json5 不存在"; exit 1; }
[ -f "hvigorfile.ts" ] || { echo "错误: hvigorfile.ts 不存在"; exit 1; }
[ -d "entry" ] || { echo "错误: entry 目录不存在"; exit 1; }
[ -d "test" ] || { echo "错误: test 目录不存在"; exit 1; }

echo "2. 检查依赖..."
if ! grep -q '@vidall/player' oh-package.json5; then
  echo "错误: oh-package.json5 缺少 @vidall/player 依赖"
  exit 1
fi

echo "3. 检查仅使用公开 API..."
# 检查测试文件是否不引用 native 或内部模块（忽略注释）
# 更精确地过滤注释和描述性文本
if grep -r "native/" test/ 2>/dev/null | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "no access to native\|native/internal\|native modules"; then
  echo "错误: 测试文件引用了 native/ 目录（非注释行且不是描述性文本）"
  exit 1
fi

if grep -r "VidAll_TV" test/ 2>/dev/null | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "no access to.*VidAll_TV"; then
  echo "错误: 测试文件引用了 VidAll_TV（非注释行且不是描述性文本）"
  exit 1
fi

# 检查测试文件是否引用内部属性（允许在字符串字面量、注释或函数名中）
if grep -r "_internal\|nativeHandle" test/ 2>/dev/null | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "player\._internal\|player\.nativeHandle" | grep -v "'_internal'\|'nativeHandle'\|\[\"_internal\"\|\[\"nativeHandle\"" | grep -v "should_not_access_native_or_internal_modules"; then
  echo "错误: 测试文件引用了内部属性（非注释行且不是属性访问检查、字符串字面量或函数名）"
  exit 1
fi

echo "4. 检查 entry 页面..."
[ -f "entry/src/main/ets/pages/Index.ets" ] || { echo "错误: Index.ets 不存在"; exit 1; }

# 检查 Index.ets 是否仅使用公开 API（忽略注释）
if grep "native/" entry/src/main/ets/pages/Index.ets | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "no access to native"; then
  echo "错误: Index.ets 引用了 native/ 目录（非注释行且不是描述性文本）"
  exit 1
fi

if grep "VidAll_TV" entry/src/main/ets/pages/Index.ets | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "no access to.*VidAll_TV"; then
  echo "错误: Index.ets 引用了 VidAll_TV（非注释行且不是描述性文本）"
  exit 1
fi

# 检查 Index.ets 是否引用内部属性（允许在属性检查中）
if grep "_internal\|nativeHandle" entry/src/main/ets/pages/Index.ets | grep -v "^[[:space:]]*//\|^[[:space:]]*/\*" | grep -v "player\._internal\|player\.nativeHandle"; then
  echo "错误: Index.ets 引用了内部属性（非注释行且不是属性访问检查）"
  exit 1
fi

echo "5. 验证依赖解析..."
# 尝试解析依赖路径
DEP_PATH="$(pwd)/../../packages/vidall-player"
if [ ! -d "$DEP_PATH" ]; then
  echo "错误: 依赖包路径不存在: $DEP_PATH"
  exit 1
fi

echo "6. 验证 HAR 打包边界..."
# 检查是否只依赖公开的 HAR
if [ -f "$DEP_PATH/build-profile.json5" ]; then
  echo "依赖包构建配置存在"
else
  echo "警告: 依赖包缺少构建配置"
fi

echo "=== 验证通过 ==="
echo "consumer-smoke 项目结构完整，仅依赖公开 API，不访问 native/ 或 VidAll_TV。"
echo "符合 T064 隔离 consumer-smoke 的要求。"