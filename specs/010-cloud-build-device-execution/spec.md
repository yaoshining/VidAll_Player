# 010：GitHub 云端构建与 iMac 真机执行分工

## 场景与边界

所有 Player 构建 CI 迁入 GitHub 官方云端；iMac 仅为真机专用执行节点。复用现有本地分支/checkout（基线894f0feb），先规格/覆盖映射审查，再真实TDD及最小实现；代码推送、runner标签/注册、环境/签名/远端配置须各自精确预览。现有仅授权894f/f28aa的变量与Secret不自动授权本轮新代码。

旧SDK/归档锁、产品API22/min15、八个核心库保持，TV只读、候选不换、不重跑长播。默认构建路线是明确选择现有deveco26 target的云端流程，不把旧default在新SDK下混入新版libc++的路径说成已通过；不直接改产品default target或签名文件。

## 验收要求

- R1 全部self-hosted构建职责有逐项去向及证据。新默认云端组合必须保留47宿主checks、锁定私有SDK来源、HAR、公共API编译负例、独立consumer九库/API、清理与actual merge绑定；旧normal自动目标门禁退役但旧锁和历史失败保留。
- R2 旧test-player独有的完整CMake/CTest14项、两个诊断JS、ArkTS/Hypium测试模块必须有新的云端覆盖。新组合已有的诊断JS/C++不得被误算成覆盖所有旧native测试。缺签名不跳过无签名编译；built必须绑定实际命令和产物，不能仅由signing_ready推导。
- R3 unsigned编译、signed可安装包和设备执行分开声明。当前Hypium实际加载用例/旧demo尚未适配normal运行初始化和真实异步事件，不把编译成功当运行通过；纯解析负例仍有效。需要实际设备执行的新入口须独立初始化、terminal接管、应用保屏/释放、确定性夹具和完成证据。
- R4 FFmpeg/OHCodec/mpv等producer源码重建职责必须交给明确的云端producer契约。#7/#8历史目标构建成功与#9宿主矩阵不等于当前004八库全组合重建；在完整来源/补丁/工具链/artifact匹配闭环前，不删除旧验证后声称全部迁移完成。
- R5 iMac仅手动、受审控制器执行：固定run/attempt/artifactID/ZIP与HAP摘要、源head/merge、workflow、签名身份/有效期/bundle/设备profile。拒任意URL、shell命令、PR脚本或当前分支下载执行；不在iMac编译，不复用通用deveco标签接构建。受控本地签名是独立可选动作，须精确工具/材料授权及unsigned→signed原成员不变及官方唯一精确派生.pages.info验证。
- R6 真机专用标签、跨本测试流程的设备互斥、精确设备选择；离线/认证失败=待验，不假通过。仅应用保屏，无系统设置改动；只结束本次独立测试应用/本次资源，不重启全局HDC或触碰TV应用。
- R7 云端设备包与普通unsigned consumer分开：前者必须含受控短媒体及摘要，缺媒体/签名不能安装。优先评估iMac固定工具的受控签名（不编译），避免私钥迁入云端；专用手动材料/profile与固定工具已获两次限定签名批准，官方sign-app成功；新轮次/新执行器必须重新精确审批。签名前后原有效载荷一致，仅允许官方同输入/参数的精确派生.pages.info。也不预先排除获批云端签名，但不得默默选择。缺材料授权/包契约时不部署、不注册runner、不提前开启设备workflow。
- R8 每阶段真实RED先于实现，覆盖缺检查/skip冒绿/错来源/错包/权限和离线边界；精确提交clean重放、artifact与清理证据后才请求推送。新required check选择与远端规则设置另批。
- R9 本轮先实现单bundle `com.yaoshining.vidalldeviceprobe` 的隔离短测：独立入口移除NAS、网络权限和备份能力，包内受控合成媒体、全新nonce日志；120秒内验证真实渲染/进度、暂停恢复、成功seek和关闭重开。失败catch不产生成功session-end，释放与应用保屏关闭独立finally执行。九套Hypium继续只编译，不借单entry契约宣称真机通过。
- R10 本地首次受控执行先于GitHub手动入口。固定已审控制器与独立device-tools锁；受测PR仅作为数据制品，不在持钥iMac执行其脚本。签名/验签/安装前需要外部精确审批绑定来源包、工具和专用签名配置；材料已就绪且签名命令成功，但完整payload门禁未过，设备仍未安装；任何材料/新审批缺失仍pending。工具锁仅记录观察值，不视为部署批准。
- R11 全事务持有同设备锁；进程/Ability/Window查询失败或断连不能推断已退出。异常清理不明时持久journal阻止后续安装；正常路径必须保屏false回读，强停路径仅能证明系统窗口资源释放，不能冒充应用自清理。只清本轮bundle/文件，不修改系统保屏、TV、候选或默认SDK。
- R12 当前短测身份限于已验签/全载荷不变的安装包、九库摘要、系统包元数据、本次PID/nonce；`installedPayloadVerified`与`runtimeMappedLibraryHashVerified`分开。后者保持false，不将source-identity回显冒充实际运行映射哈希，不扩产品API/native探针。

本阶段与项目宪章的适用性：CI/执行控制变更不新增播放器UI/API；遥控器/物理HDR/声画与原API兼容真机验收仍待验。设备相关命令遵循deveco-cli优先，若仅固定HDC安装/测试能力可用，须记录其能力限制与精确工具SHA，不通过CLI run触发构建。

## 执行器累计修复当前状态

截至本次本地提交准备：专用手动材料签名/完整验签和Round7安装身份通过；短测终态事件验收拒绝、原清理联合门禁未确认，后验无设备残留。旧journal cleanup-unknown及历史失败保留，原始事件缺失不能追认根因。Round8诊断129项和最终根审通过，新控制器尚未设备运行/发布；旧账本对账尚未实现/批准。本提交包含自568a68以来执行器必需恢复/修复文本，保留产品/八库/API/旧锁，现有云端workflow不变；准确执行与证据边界见`../../scripts/test/device-execution/REPAIR-SUMMARY.json`（从仓库根查看）。旧段落中的待办按各阶段日期解释，以上为当前状态。


## 2026-10-27 cleanup-only 对账补充（Round9已按精确批准执行）

独立 `reconciliation.py` 复用同一设备锁与只读解析，既有 controller/executor/imac 原字节不变。外部精确审批绑定脚本及依赖、工具/设备、旧 journal 与 nonce、原 nonce 账本及有效期。锁下新鲜核对专用包、进程、Ability、窗口和宿主活动均不存在后，先 O_EXCL 原字节归档和独立只读证据，再比较并原子更新可变事务头；任何前置失败不解除阻塞，账本永不改写。旧短测始终未通过，不将对账当作场景验收。

TDD 覆盖正常对账、摘要/nonce/设备/工具漂移、锁冲突、残留和未知状态、归档/证据/写头失败与中断。新短测使用 run 40498456949 attempt 2 的 artifact 12732547397/HAP 2cb2aa0f…；最新 HAP 独立派生 pages 与旧值相同不表示可沿用旧批准。Round9的对账及一次短测已取得独立精确批准并执行：对账成功，签名/验签/安装通过，场景及运行时窗口门禁未通过，原失败保留。未来远端写入及执行仍须新精确批准；手动 workflow 留到短测通过后另审。


## Round10：独立短测 stale 重新采样与窗口失败诊断

Round9 对账、签名/验签/安装已完成；短测在440ms首帧前以DIAGNOSTICS_STALE失败，原运行时窗口证据门禁失效。原失败、事件摘要、cleanup-unknown和8nonce不改；事后无残留不追认通过。

仅在独立fixture消费层捕获精确DIAGNOSTICS_STALE：初次计入最多50次请求、100ms间隔，重试预算5秒；在各await返回后核期限并拒绝晚到成功，不声称能取消平台中尚未返回的Promise；继续受原场景deadline/取消约束。每次await前后检查，terminal/released/同player或cycle已变优先失败，其他错误不重试，不修改产品API的新鲜度语义。先真实共享函数RED/GREEN，随后真实ArkTS unsigned编译；宿主替身不算设备通过。

窗口只补固定解析错误码和有界结构/计数/输出摘要持久化，不修改window_pids原接受条件，不忽略行或自动重试。未知原始窗口名/错误/其他应用数据不入证据。现有证据不足以确定Round9窗口失配原因，本轮不能宣称已修复该真实根因。

本轮仅本地实现/验证和精确提交预览；推送、配置、签名及再次设备执行分别待批准。手动workflow仍不接入。

Round10本地目标验证：DevEco26锁定工具与空signingConfigs独立工程实际clean/build通过。首次ArkTS拒绝未声明类型的throw已留失败日志，最小改为Error类型断言后通过；消费保留HAR ef9e196b…，不冒充当前提交同源云端HAP。现有host job仅新增独立reconciliation.test.py一条命令及工作流变异断言，无新增设备workflow、runner或权限。
