# 验证证据与验收状态

## 已完成的本地结果

- 本地target-06：在只读挂载的官方DevEco26及已验证npm CLI闭包上完成单次clean与HAR构建；固定八库入包摘要全部一致。compileSdk=26.0.0.105，target=60002022，min=50003015。
- HAR、bridge及源码绑定见evidence/local-target-06.json。真实build.ninja含-nostdlib++和固定libc++绝对输入，无HAR后处理。静态C++导入在固定库中有提供方；平台实际行为仍未验收。
- 真实CMake/目标Clang回归覆盖默认OFF、正确固定库、错误架构、错误STL、错误hash、OHOS头ABI命名空间。
- 新契约覆盖工具混装、完整GET/Range、截断/hash、API漂移、故障留证、受限生成目录清理、真实链接身份；工作流结构变异逐步拒绝缺少always/cleanup/assessment/runtime。
- 既有正常核心宿主47项通过；全工作流经锁定actionlint1.7.12及作用域负例校验。
- 原始失败均保留：测试接口初始不存在（不冒充12项语义RED）、调试版本行、CLI缺依赖、子进程Node路径、SDK runtime混入、通用头命名空间错误、clean保留metadata、daemon占用挂载及无效本地收尾；本地日志摘要索引见evidence/local-log-index.json。

## 最终精确提交重放

提交预览保存在独立临时目录的preview/PREVIEW.md；它在最终提交后绑定独立clean checkout的实际HEAD/tree、完整测试及HAR结果，不将上面的实现中间提交冒称最终SHA验证。未取得最终重放结果不得请求推送批准。

## 未完成且保持待验

- GitHub官方macos-26的实际下载、磁盘/内存峰值、目标构建及artifact回读：尚未推送，须批准精确SHA。
- 长期无人值守来源：短期签名URL不是稳定下载机制。首跑须另批准临时repository secret DEVECO26_ARCHIVE_URL 的注入与测试后移除，不在源码/日志内保存签名query。
- consumer构建与运行时、实际低API设备、物理HDR/主观声画及其他既有未验项目；本轮不进行真机，也不重跑60分钟长播。

不更新旧PR82 required，不合并、不替换候选、不改TV或默认SDK。

精确重放中的一次npm ECONNRESET及一次stop后卸载竞态均保留为失败；有界重放允许复用同源、已核npm缓存，仍执行npm ci完整性校验。这不证明云端冷缓存下载成功。本地资源仅快照，不冒充连续峰值。
