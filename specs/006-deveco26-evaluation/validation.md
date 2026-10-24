# 验证证据与验收状态

## 已完成的本地结果

- 本地target-06：在只读挂载的官方DevEco26及已验证npm CLI闭包上完成单次clean与HAR构建；固定八库入包摘要全部一致。compileSdk=26.0.0.105，target=60002022，min=50003015。
- HAR、bridge及源码绑定见evidence/local-target-06.json。真实build.ninja含-nostdlib++和固定libc++绝对输入，无HAR后处理。静态C++导入在固定库中有提供方；平台实际行为仍未验收。
- 真实CMake/目标Clang回归覆盖默认OFF、正确固定库、错误架构、错误STL、错误hash、OHOS头ABI命名空间。
- 新契约覆盖工具混装、完整GET/Range、截断/hash、API漂移、故障留证、受限生成目录清理、真实链接身份；工作流结构变异逐步拒绝缺少always/cleanup/assessment/runtime。
- 既有正常核心宿主47项通过；全工作流经锁定actionlint1.7.12及作用域负例校验。
- 原始失败均保留：测试接口初始不存在（不冒充12项语义RED）、调试版本行、CLI缺依赖、子进程Node路径、SDK runtime混入、通用头命名空间错误、clean保留metadata、daemon占用挂载及无效本地收尾；本地日志摘要索引见evidence/local-log-index.json。

## 精确提交与官方云端结果

最终实现提交 `610dd1f6e83fa844a7096de20ce591b72e48e9da` 已完成新的独立checkout真实全流程重放、独立审查和用户精确批准。新增有界cleanup测试21项；实际每步退出码生成汇总，旧手工填通过的无效汇总不作为证据。

官方 [run40110834301](https://github.com/yaoshining/VidAll_Player/actions/runs/40110834301)（push事件、同一精确head）success；实际Hosted镜像macos-26-arm64，系统26.6.2。41项契约、21项准备/清理、6项CMake/目标Clang及13项结构变异通过。官方完整归档冷下载/校验、CLI npm闭包、single clean/HAR、固定八库/实际链接/API/源码前后与清理均通过。现场准备500.755秒，资源数据只为快照而非连续峰值。

artifact12566429056，ZIP233289字节，SHA256 `01bf591e8dec7cc14c80e0a13c70c8d55e19c5feaba21d7333356455c751e179` 与GitHub digest一致，33项索引全字节核验。核心选择项已保存在[持久证据目录](evidence/ci-40110834301/README.md)，逐项来源/hash见其evidence-index；不是完整ZIP，也不含HAR本体。临时下载Secret已删除并由独立通道确认不存在。

云端记录HAR `ea898f2f735e88ba49fdda5e7e4a4231db4d292d9117c8d0c9590bb6b7e6b8d6`、bridge `175a239fd049d265f6cae07d69813c3001113e7de4dc7338924581606d1a7d7a`。其摘要与本地精确重放不同，未单独归因，不宣称跨主机可重复构建。旧default在新SDK下仍有runtime打包差异，未将新target成功描述为旧default通过。

## 未完成且保持待验

- 稳定长期下载来源/受支持的续签或获授权私有缓存；一次官方冷准备通过不构成永久无人值守来源。
- #82实际PR merge/新profile组合接线与consumer实际消费本次HAR的构建、运行；GitHub当前规则未启用，未来强制配置单独审批。见[最小方案](integration-plan.md)。
- consumer运行时、实际低API设备、物理HDR/主观声画及既有未验项；本轮不真机、不长播、不签名发布。

本轮文档收尾未改旧门禁、workflow、脚本、旧锁或旧封存；不合并、不替换候选、不改TV或默认SDK。文档新SHA仍待精确预览和推送批准。`formalArtifactAllowed=false` 保持。
