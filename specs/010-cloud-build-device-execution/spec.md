# 010：GitHub 云端构建与 iMac 真机执行分工

## 场景与边界

所有 Player 构建 CI 迁入 GitHub 官方云端；iMac 仅为真机专用执行节点。复用现有本地分支/checkout（基线894f0feb），先规格/覆盖映射审查，再真实TDD及最小实现；代码推送、runner标签/注册、环境/签名/远端配置须各自精确预览。现有仅授权894f/f28aa的变量与Secret不自动授权本轮新代码。

旧SDK/归档锁、产品API22/min15、八个核心库保持，TV只读、候选不换、不重跑长播。默认构建路线是明确选择现有deveco26 target的云端流程，不把旧default在新SDK下混入新版libc++的路径说成已通过；不直接改产品default target或签名文件。

## 验收要求

- R1 全部self-hosted构建职责有逐项去向及证据。新默认云端组合必须保留47宿主checks、锁定私有SDK来源、HAR、公共API编译负例、独立consumer九库/API、清理与actual merge绑定；旧normal自动目标门禁退役但旧锁和历史失败保留。
- R2 旧test-player独有的完整CMake/CTest14项、两个诊断JS、ArkTS/Hypium测试模块必须有新的云端覆盖。新组合已有的诊断JS/C++不得被误算成覆盖所有旧native测试。缺签名不跳过无签名编译；built必须绑定实际命令和产物，不能仅由signing_ready推导。
- R3 unsigned编译、signed可安装包和设备执行分开声明。当前Hypium实际加载用例/旧demo尚未适配normal运行初始化和真实异步事件，不把编译成功当运行通过；纯解析负例仍有效。需要实际设备执行的新入口须独立初始化、terminal接管、应用保屏/释放、确定性夹具和完成证据。
- R4 FFmpeg/OHCodec/mpv等producer源码重建职责必须交给明确的云端producer契约。#7/#8历史目标构建成功与#9宿主矩阵不等于当前004八库全组合重建；在完整来源/补丁/工具链/artifact匹配闭环前，不删除旧验证后声称全部迁移完成。
- R5 iMac仅手动、受审控制器执行：固定run/attempt/artifactID/ZIP与HAP摘要、源head/merge、workflow、签名身份/有效期/bundle/设备profile。拒任意URL、shell命令、PR脚本或当前分支下载执行；不在iMac编译，不复用通用deveco标签接构建。受控本地签名是独立可选动作，须精确工具/材料授权及unsigned→signed有效载荷不变验证。
- R6 真机专用标签、跨本测试流程的设备互斥、精确设备选择；离线/认证失败=待验，不假通过。仅应用保屏，无系统设置改动；只结束本次独立测试应用/本次资源，不重启全局HDC或触碰TV应用。
- R7 云端设备包与普通unsigned consumer分开：前者必须含受控短媒体及摘要，缺媒体/签名不能安装。优先评估iMac固定工具的受控签名（不编译），避免私钥迁入云端；签名材料/专用bundle profile与工具尚待批准，签名前后必须核有效载荷一致。也不预先排除获批云端签名，但不得默默选择。缺材料授权/包契约时不部署、不注册runner、不提前开启设备workflow。
- R8 每阶段真实RED先于实现，覆盖缺检查/skip冒绿/错来源/错包/权限和离线边界；精确提交clean重放、artifact与清理证据后才请求推送。新required check选择与远端规则设置另批。

本阶段与项目宪章的适用性：CI/执行控制变更不新增播放器UI/API；遥控器/物理HDR/声画与原API兼容真机验收仍待验。设备相关命令遵循deveco-cli优先，若仅固定HDC安装/测试能力可用，须记录其能力限制与精确工具SHA，不通过CLI run触发构建。
