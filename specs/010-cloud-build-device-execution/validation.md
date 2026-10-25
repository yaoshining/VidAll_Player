# 本地验证与未完成范围

## 已有证据

- 第一轮真实RED：原活动工作流仍有4条self-hosted任务；原状态脚本在构建失败情况下仍按签名存在报告built=true；原consumer staging不含Hypium。
- 新汇总RED：缺Hypium证明仍可成功，回归后拒绝。实际SDK拒绝临时ohosTest→product映射，先补禁止映射回归，再仅修临时staging。
- 检查点ec7c473：原14项CTest+2项诊断JS与完整47项正常核心宿主矩阵通过；固定producer交付与完整输入审计组合独立审查通过，包含真实许可证/头文件/资源变异拒绝。
- 首次HAR实际成功；修正staging后官方OhosTestCompileArkTS及PackageHap完成，实际entry_test unsigned HAP含565668字节ABC，九库与当次HAR相同、产品API22/15未变。首个配置拒绝日志原样保留；此探索结果不是最终冻结源码重放。
- C控制器22项合成制品/真实文件锁测试通过。全部为宿主契约，不是实际签名、验签或设备执行。
- actionlint检查实际全部工作流及真实上下文负例；最终精确提交重放结果由外部只读证据索引绑定，不回写冻结提交形成循环。
- 已冻结A阶段提交 `f0b878ad25cfb90ae376b1d8977b1b912289b453`、实际merge `a7c0768f839a6a39a9f6819d9b9ca9c173e97d2a` 的云端run `40163756590` attempt 2成功；根审下载核验host 106项、target 46项索引，HAR、同HAR消费者、九套Hypium无签名编译与清理通过。来源为外部 `ci-repair/configuration/SPEC010-REMOTE-CLOSEOUT.json` 与 configuration-root-review；attempt 1旧事件批准导致skip及42d79历史失败保留。该成功只属于冻结f0b878，不为本轮新增C实现背书。

## 发现的既有不一致

原894f0feb的签名validator与原profile配对仍报“模块vidall_player未应用到环境ci”：它逐target要求全部product，deveco26实验目标只用于default。失败早于本轮修改的workflow断言。原产品配置、签名材料和validator均未改，失败单列，不声称所有签名配置测试通过。本轮unsigned工程不依赖该历史签名路线。

## 仍待验收

- 本轮新增C实现的新精确提交、二进制上传及实际运行仍待精确预览批准；不得沿用f0b878的远端通过声明。
- producer最新normal完整组合目标云端重建；当前只消费固定既有八库。
- 本轮同冻结源码含媒体设备包重放、专用材料/口令可用性、真实受控签名及verify-app、实际设备短场景/离线/保屏清理；HDC执行适配器已本地实现，但设备输出schema尚待真机确认。
- iMac专用label/控制器部署，main工作流生效顺序与正式required规则选择；本轮未改远端设置。
- 原Hypium九套运行契约适配、物理HDR和主观声画。本轮不重跑长播、不更换候选、不修改TV。

本轮短测的身份范围为 `installedPayloadVerified`：官方验签、全ZIP有效载荷相等、九库摘要及安装成功/系统包元数据/PID/nonce绑定。`source-identity.json`是交付声明回读，不能证明运行映射逐字节哈希，`runtimeMappedLibraryHashVerified=false`保持；不为此扩大产品API/native或要求设备root。

## 本轮 C 本地 TDD 与审查修复

- controller 当前 23 项，包括 merge_group 正常及错来源/错 group SHA 拒绝；原 22 项历史证据不覆盖本次新增项。
- executor 19 项与 imac 28 项真实函数测试通过；平台命令为替身，正常事件直接取真实 SmokeSession 宿主输出，不是签名或真机证据。
- 已回归外部 unsigned SHA 在签名前/验签后/安装前的绑定，拒 unsigned 与 signed 一并替换；签名期间出现他人同 bundle、安装结果未知、恢复安装生命周期变化和 pre-stop PID 查询错误均禁止清理他人进程/包。
- 完整 CLI 依赖闭包锁定，事务入口完整核验，后续按真实被调用工具核验；采样不重复未执行的 CLI 闭包，保留 120 秒截止。工具观察不等于配置批准。
- 实际 signer helper 使用同锁官方 JAR 的 SignerInfo SID，拒仅附带获批证书的链；临时合成证书测试不能证明用户材料可签名。
- 初始拒绝骨架 RED 是新功能未实现（部分 errors），不称旧代码语义缺陷；ownership 旧行为重放为复审变异复现，原始记录保留。最终日志和逐文件摘要在外部 implementation/executor/GREEN-FINAL.json，避免在冻结源码内自引用。
