# SDK 选择证据修复记录

715d 的 push [39998312068](https://github.com/yaoshining/VidAll_Player/actions/runs/39998312068) 与 PR [39998322892](https://github.com/yaoshining/VidAll_Player/actions/runs/39998322892) 宿主通过、unsigned HAR 和组合结果失败。目标 `docs catalog` exit=0，只输出六个文档目录，无 ToolProvider 选择；不能据此声称 SDK 或工具 hash 不符。PR 失败 artifact 12521800000 的 ZIP 摘要与6个文本索引已复核；push 目标上传另有失败，均保留。

最小修复：在 clean 前保存源码和固定八库字节；复用唯一一次真实 clean 的官方 ToolProvider 输出，核验 API24/metadata/clang/nm/readelf 精确 hash 后绑定同一 Studio 执行 build。clean 先于 SDK 身份验证，仅影响隔离工程生成物。保留 clean 后旧 HAR/bridge/compile_commands 拒绝逻辑及构建后源码/包内九库/实际 compiler+sysroot 约束。没有放宽缺失输入或工具漂移门禁。

## TDD 分类

- [真实语义 RED](evidence/sdk-selection-repair/red-semantic.log)：旧 execute 调用 docs，实际 catalog 输出无选择，预期成功的完整 runner 失败；新执行链从 clean 获得同一 fixture 的选择后通过。命令按 argv 提供输出，真实 discover/sdk/HAR/编译命令/快照代码均执行。
- [接口与顺序 RED](evidence/sdk-selection-repair/red-interface-and-order.log)：参数变更 TypeError 只算接口 RED；无 clean 先行的执行顺序断言为语义 RED，不把 TypeError 当主要缺陷证明。
- [GREEN](evidence/sdk-selection-repair/green-contracts.log)：29项契约通过，其中完整 runner 覆盖正常、无选择、多选择、clean非零、SDK错hash；正常只clean一次且无catalog调用。首次GREEN中测试期望未解析macOS /var软链接路径造成断言失败，已将预期规范化；外部失败记录保留，不属于SDK漂移。
- [CLI/失败身份](evidence/sdk-selection-repair/cli-and-failure-identity.json)：本机1.3.4官方包源码只读核查clean/build共用ToolProvider，记录包hash，不纳入第三方源码。

新精确SHA真实本机HAR/宿主重放在仓库外预览绑定；本文冻结不提前宣称远端通过。远端 iMac 的实际 SDK 身份仍须批准后的CI核验。产品、八库、原Player/TV、候选、默认SDK/系统不改；不操作设备/长播；formalArtifactAllowed=false。真实GPU、低API、物理HDR等未验项目保持待验收。
