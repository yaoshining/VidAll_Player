# 正常核心接入宿主门禁

本目录只验证宿主契约。Ubuntu CI 成功不代表 HarmonyOS 目标编译、真机播放、物理 HDR 或正式发布验收，`formalArtifactAllowed=false` 保持。

## 运行

```sh
npm ci --prefix scripts/test/normal-core --ignore-scripts --no-audit --no-fund
python3 -B scripts/test/normal-core/run.py --out /tmp/vidall-normal-core-evidence
```

输出目录必须不存在，防止覆盖旧证据。需要 Python 3、Node、`clang++` 和支持 ARM64 ELF 的 `llvm-nm`。Linux 默认从 PATH 读取 `llvm-nm`；macOS 可显式传入 `LLVM_NM`，未传入时使用现有 DevEco SDK 工具。TypeScript 精确锁定 5.6.3 和 npm 完整性摘要；`TYPESCRIPT_PATH` 可显式指定，门禁仍要求实际加载的版本等于锁定版本。

## 验证范围

- 8 库、公开头、资源、来源封存身份、真实编译宏绑定、必要导出 ABI 与 16 项篡改/遗漏测试。CI 验证提交内封存资料与二进制，不重建 producer，也不伪称能访问并重验原机器的外部源码路径。
- 真实 ETS 运行时/PlayerSession/桥接函数的 15 个场景，以及现有诊断会话、诊断探针契约、原生字段转换回归。NAPI 是替身，诊断探针契约测试不是设备执行。
- 真实 `process_runtime.cpp` 的 13 个配置场景，包括同配置幂等、不同配置拒绝、ABI/注册/启用/SMB 失败后锁存、缺目录、目录被普通文件/符号链接替换、损坏配置以及资源失败。失败不得继续创建播放器。
- 真实 native 创建/释放/清理入口；平台与底层 Session 使用已有明确标注的计数替身。
- 真实 NativeSession 父级函数与 `std::thread`、最终引用析构的 10 个场景；6 个去屏障/提前退出/取消 deadline 反例必须被拒绝。完整 RenderLoop 与平台 API 不在真实函数提取范围内。deadline 验证从首次终局锁存计时，不能仅凭退出码 86 通过。

## 失败与上传边界

统一入口和所有子 runner 失败均返回非零；预期失败的变异必须退出 1，随后结构化门禁必须确认具体失败原因，编译错误或空测试集合不算变异成功。编译告警、原始失败输出、超时前部分日志保存在 `work/`。任何实际执行失败都会令总门禁失败，不改写为通过。

`public/` 仅从固定结果和日志白名单生成，包含库输入清单/产品源码的 SHA，不包含库、HAP、生成的宿主可执行文件、SDK、签名、凭据、媒体或原始来源锁。日志中的本机路径替换为占位符。上传前独立检查 UTF-8、JSON、扩展名、符号链接和路径；边界检查失败不上传。7 个上传门禁测试覆盖正常文本及拒绝路径。

专用工作流 `.github/workflows/normal-core.yml` 在 `codex/004-normal-core-integration` 推送时以及手动触发时执行。已有 HarmonyOS 工作流不变。推送仍须先获得用户对精确提交 SHA 的批准。

## HAR 元数据规范化

`normalize-har.py normalize 输入.har 新输出.har` 固定 tar 的 uid/gid/所有者名/mtime/成员顺序，以及 gzip 时间戳/文件名；原始 HAR 和既有输出均不可覆盖。仅接受普通文件和目录，不解包到磁盘。所有路径、类型、权限、文件长度和 SHA 必须在处理前后相同；危险路径、规范路径碰撞、链接、特殊成员全部拒绝。除指定元数据外的 PAX 信息保留。

`normalize-har.py compare 左.har 右.har --report 新报告.json` 同时要求逐成员一致和完整归档 SHA 一致，任一差异返回非零。13 项独立测试验证元数据/顺序变化稳定、原始文件不变、内容变更改变哈希并令比较失败，以及危险输入和既有输出保护。规范化不会修复内容差异，也不提升正式发布状态。

该步骤不属于产品编译器或运行时修改，只负责生成独立的可重复归档。消费者仍必须实际构建消费规范化 HAR；本脚本通过不能替代这一验证。
