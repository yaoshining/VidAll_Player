# 验证入口

1. 设置 `SPECIFY_FEATURE_DIRECTORY` 为本目录，再执行 `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`。
2. 按 tasks.md 先运行新增回归确认红测，再实现并复跑，记录命令和结果到 evidence.md。
3. 原生兼容选择须覆盖 GPU 存在/缺失、配置失败、既有硬解以及隔离名额上限；ArkTS 测试使用真实 PlayerSession/bridge，仅替换平台 NAPI。
4. 原生真实 Initialize 测试：`python3 native/tests/ohcodec-fence/initialize.test.py`。
5. 完整宿主门禁：`python3 scripts/test/normal-core/run.py --out <新的证据目录>`。设备、构建与 CI 分别记录，不升级证据等级。
