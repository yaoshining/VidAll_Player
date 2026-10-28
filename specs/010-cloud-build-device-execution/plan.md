# 分阶段最小实施计划

## 当前验收矩阵（2026-10-28，Round16 后）

| 范围 | 当前结果 | 未覆盖边界 |
|---|---|---|
| 云端宿主/目标构建 | b16d490a、实际merge d688e99c、run40570621495 attempt2通过；HAR/consumer/Hypium编译/unsigned设备包已独立核验 | 不覆盖本轮未提交的reconciliation分支；Hypium不等于真机运行 |
| Round16本地修复 | 对账器34、imac79、executor47；真实RED及两语义变异通过、根审通过 | 精确新提交推送及对应新CI待批准 |
| 独立真机链 | Round16签名/完整验签/安装、35.364秒短测、保屏false、卸载后六查询43/43与材料清理通过 | 仅既有专用短场景，不扩产品/物理HDR/未确认声画/旧未覆盖故障 |
| 窗口修复 | 前置三次44/43拒绝并保留，卸载后一次新43/43严格通过 | 非旧42/41原样重现，系统漏行对象仍未知，旧失败不改写 |
| GitHub手动真机工作流 | 尚未实现、尚未配置或启用 | 交互密码、默认分支入口和iMac执行权限需后续独立方案/批准 |

旧SDK锁、产品API、八库、TV和候选不变；formalArtifactAllowed=false。以下早期“当前/待验”文字是对应日期或阶段的历史记录，当前验收以本矩阵及Round16证据为准，不能据旧阶段状态否认已完成范围，也不能将本轮成功外推为全部验收。

2026-10-26 小范围适配：真实电视的 `bm get -u` 提示在 `is` 与冒号之间有空格，`hdc list targets -v` 为附带 `localhost hdc` 的五列。先用脱敏原格式驱动真实函数复现，再只允许提示处空格/制表符、旧三列或实测五列；同目标重复/冲突、未知尾列、错误输出均拒绝。不改UDID前缀、字符/长度、单值与外部批准摘要约束。此修改属于基于 `568a68d` 的新执行器修订，不继承该基线的执行审批；云端 artifact `12592874084` 和 HAP `bda840a7…` 继续作为独立冻结输入。2026-10-27 当前已生成手动专用材料，公开证书/profile及单电视授权已核；后续两轮已获批的用户TTY签名证明手动私钥解锁及alias可用；Round2有效载荷门禁失败，设备从未安装。

## A：云端默认构建与无签名编译（先实施的本地范围）

复用当前工作流的可信来源与actual事件SHA绑定；明确默认调用vidall_player@deveco26，不改产品target/API。保留旧锁/脚本作为历史证据，退役旧normal自动self-hosted目标及其旧AND结果的自动触发；不能把新结果命名伪装成旧锁构建通过。新组合统一显式AND，包括完整宿主、目标HAR、消费者、Hypium编译、清理；旧工作流契约测试须按新职责更新，先RED。

旧test-player独有完整CTest迁入云端host（可独立job/step，避免仅重复已有诊断）；其ArkTS/Hypium编译在同一已核macos-26 SDK会话中新增临时工程。复制精确entry主/测试资源和9suite，输入改为本次HAR，保持API22/15与编译model；临时配置明确unsigned、禁用本机签名发现，产品仓文件不改。旧libentry桥是否为有效依赖要由源import/真实编译证明，不能盲移除；若构建需该桥则单独记录旧桥与九库检查范围，不能混称正常核心九库。

真实运行devecocli编译entry@ohosTest，校验实际测试模块元数据、module名、测试runner/suite汇入、依赖解析与源hash、签名状态、输出唯一性及cleanup。若无签名SDK能力不足，保留实际失败，采用经官方任务定义证明的无签名编译阶段并明确“只编译未打包”；不得以skip或stub编译代替。test_module_built只有实际成功产物才真，compilePassed与signedInstallable分别记录。

拟改文件：normal-core.yml、deveco26-pr82-gates.yml、test-player.yml；新scripts/test/cloud-build/（覆盖门禁/unsigned Hypium helper及测试），deveco26-gates必要汇总/工作流测试；原normal-workflow/signing测试仅改职责相关断言。旧bootstrap/锁/产品源码八库不动。build-libmpv迁移在B前置未闭环时不擅自删。

## B：producer源码构建职责交接（根审计后定实施边界）

明确FFmpeg/OHCodec/mpv/libplacebo/静态依赖精确源码、补丁、SDK、功能/ELF/许可证验证及run/artifact摘要；生产端云端构建负责生成，Player只绑定已批准输入并做集成核验。保留Player源脚本/来源历史及全部可移植契约。#7/#8真实目标历史、#9宿主结果与当前004输入分别列出，不合并成一个虚构全绿来源。

最小方案供根审查：明确退役Player两条历史生产入口、保留脚本/旧锁/宿主来源与许可证契约；新增硬门禁只允许当前004精确八库及manifest基线，任何核心更新必须另交producer精确源码/补丁/工具/实际目标制品与功能证据，未具备则直接拒绝。当前组合不重建、不改库；这属于生产职责明确交接，不声称#9已完成新全量目标。若根不接受该阶段边界，则B保持阻塞，不能通过简单skip冒称全部构建迁云。必要producer代码变更另行精确预览，当前不越仓修改。

## C：云端设备包与iMac手动执行（本地实现，尚未启用）

普通consumer缺少实际媒体，只能保留编译用途。新增独立device-package staging，复用normal-core-consumer公共初始化/terminal主体，在固定rawfile/test_video.mp4注入短合成媒体；云端绑定生成器/参数/媒体SHA和HAP来源，缺媒体失败关闭。不得使用私人NAS影片、签名或未批准二进制代替fixture。

先确定专用测试bundle、测试集、profile设备白名单、证书指纹/有效期及签名工具锁。最小优先方案是iMac受控签名既有云端unsigned包，绝不调用编译工具；核unsigned→signed原成员/九库/媒体/API不变，仅允许同锁官方预处理精确派生.pages.info，签名完成后核profile/证书/设备授权。不扫描或自动复用旧开发签名。手动材料曾按两次精确批准临时迁移，结束后iMac副本均已删除；原材料保留在本机；新profile已限定probe bundle与单电视。云端签名是另一个后续选项，本轮不自行配置任一方式。

云端仅交付审定run/attempt对应unsigned HAP和文本manifest；固定workflow/源head/merge/来源锁/工具/九库/API/HAP与媒体SHA。signed包和可能含设备profile的材料不进入公开Player Actions artifact；存储/签名权限与保留期精确预览另批。已有公共文本artifact不等于可装包。

iMac仅专用label（拟vidall-device-imac，不创建），默认分支手动dispatch与独立环境review，no PR/push自动触发。可信控制器固定已审版本及工具SHA，输入只接受数字run/artifactID、完整commit/hash、固定bundle/测试模式；禁止任意URL/路径/脚本、禁止checkout PR内容后执行。即使包来自受审PR，控制器仍来自独立固定受信任版本；不运行包内脚本。下载/校验可在云端先做，iMac再核ZIP/HAP，签名阶段显式受控；任何时候不调用build/ohpm/npm/CMake。

设备资源用专用并发组且cancel-in-progress=false，额外本机互斥避免跨workflow争用。固定serial/HDC身份；offline/未授权/缺签名输出待验，不宣称成功。新入口执行初始化/terminal/应用保屏，结束核本进程/窗口/保屏释放；只清理本次文件/端口映射，不改系统或全局HDC。normal/Hypium/diagnostics场景分别白名单，不直接运行旧假网络/旧同步事件播放用例。当前可先做无凭据的artifact控制器契约/未就绪判定TDD，不安装设备或签名。

## 验证与停止点

2026-10-25 后续实施授权：优先单bundle短测，先本地受控事务，之后再接手动CI。主实施负责device-execution与本规格；协作实施负责新增device-smoke fixture和device-package构建，互不覆盖旧入口/产品。当前iMac实际为DevEco26/HDC3.2.0f，新HDC SHA ae849a571227166700f543f24ee2f16ef4124a66f2cb6ee7b48c8c06f4aeafb4，CLI已移至NVM路径；新增观察性质device-tools锁，不更新旧编译锁。这是2026-10-25历史观察。2026-10-27已只读确认电视连接、专用bundle未安装、手动证书/profile有效；真实签名/设备短测仍待验。

短测新增暂停恢复、成功seek、关闭重开与120秒总限时；nonce/HAP/库/PID与真实事件绑定。全事务锁覆盖准备到cleanup，清理失败/断连写持久journal；下一会话先拒绝，不能以释放文件锁等同清理成功。签名前后所有原ZIP成员字节相等，唯一允许新增项为官方同参数精确派生的.pages.info，官方verify-app与profile/证书/设备范围匹配必须独立通过。第一轮不实现Hypium双包，不自动配置签名材料、环境/label或推送/上传；完成本地TDD/构建/独立审查后统一精确预览。

TDD先真实旧工作流缺覆盖/签名决定built等RED；实现后测试官方runner限定、旧目标退役不丢检查、Hypium缺模块/错HAR/API/旧缓存/编译失败/缺签名、汇总缺证/skip拒绝。设备控制器在C获准后用实际函数mock平台：错run/head/来源/签名/包摘要/设备离线/超时/并发/清理失败均拒绝或待验，不能用job绿色冒充真机通过。

本地完成后根审查、冻结精确提交、一次必要clean真实构建重放与清理、推送预览；云端环境允许ref/批准SHA更新不沿用f28aa，另批。签名、runner标签和正式required/ruleset切换单独阶段批准。当前已完成本地实现/TDD，等待根审与冻结同源构建；真实签名、设备输出schema、短测与远端启用仍待验。

## 2026-10-27 执行前真实输出适配

在本地提交 `1ad19aa` 上新增未提交最小补丁：包清单唯一首行允许实测 `ID: 100:`；窗口仅接受旧三列或实测25列以及其固定分隔/Focus/SingleHand统计结构。完整核行数、总数、字段类型、窗口ID唯一、目标PID，错误stderr、缺头/多头/缺行/未知行均失败关闭。先真实脱敏格式RED再GREEN，38项imac、23项controller、19项executor通过；iMac固定Python3.9.6仅内存导入与真实只读解析通过，不冒充完整iMac测试或签名执行。

新预览复用已核云端artifact12592874084/HAP bda840a7…，无需重新构建。固定Python绝对路径与二进制摘要在启动前另核，不改五项工具锁schema或安装工具。密钥容器仅按用户授权核SHA/stat；alias vidallDeviceProbe来自用户回忆，解锁时不匹配立即停止、不猜别名。签名/传输/执行和清理须精确预览获批；不沿用568a68的CI为新适配器背书。

## 首次执行后的有界修复

2026-10-27 用户已在官方TTY完成sign-app，后续ContractError未带原因，且原清理已删除signed/verify输出。保留“签名命令成功、后续校验未完成、未安装”的证据边界。部署副本已清除，journal/nonce保留。仅本地补固定错误码/阶段诊断，不改变签名/校验/安装/清理决定；不重签以猜原因，下一轮单独精确预览。

## Round2：仅签名及完整验签

新增 `--sign-verify-only` 与独立 `purpose=sign-verify-local` / `mode=sign-verify-only`，两项设备写入许可必须false；不能用该审批进入execute/recover。只读核设备身份和probe不存在，官方交互签名、verify-app/profile、实际Signer SID、全payload核对；不安装、启动、采样或force-stop/uninstall。第二层命令白名单拒设备写入。共享设备锁与消耗nonce账本，但写独立sign-verify-<nonce>.json，旧journal只读不覆盖。

固定错误码/阶段/受限整数exitCode与signed包摘要大小在删除临时输出前持久化；不保存原stderr/profile/TTY。根以同锁官方JAR复现出outCertChain拒绝.pem、要求.cer；先回归RED再仅改cert-chain.cer，仍按PEM证书链内容核对，不放宽证书或payload验证。下一轮只给精确预览，不沿用旧nonce/审批，不重建冻结云HAP。

### Round3：官方派生 `.pages.info` 的精确校验（实施中）

Round2 实际签名后在成员集合门禁失败；签名输出已清理，不能断言实际差异只有 `.pages.info`。同锁官方 JAR 无私钥预处理复现确认：冻结 unsigned 的 19 个原成员不变，新增 6680 字节 `.pages.info`，SHA256 为 `4364749b8c09d61a99ffa507ca0acd5f794c2d2bfc388243c54a15d4b9f09738`。本轮先 RED，再实现固定 helper 从批准 unsigned 独立派生；签名与派生统一 alignment=4、signCode=1。原成员仍逐字节一致，只允许这一精确派生成员；unsigned 已含该成员、重复/歧义路径、额外增删改或派生失败全部拒绝。失败记录仅有界长度/摘要，未知名称只存名称摘要，不存原始内容。新代码及 helper 待独立审查和新执行批准，不沿用旧批准，不签名、安装或播放。

## Round4：公开CLI参数契约最小修复

Round3真实调用在sign-app前置参数解析失败：内部signParams支持键a，不代表公开CLI接受-a。根真实CmdUtil.convert2Params已复现11011005；只去-a4保留signCode1可解析。此前仅验证内部bytecode与stub参数，是测试遗漏。先把实际prepare_signed生成的argv送锁定官方解析层RED，再仅删除-a4；同JAR checkSignAlignment缺a时默认4，继续与ExpectedPages alignment4一致。不得绕过公开CLI或改调用内部签名API，不关闭signCode，不放宽派生和原成员校验。

原临时checkout消失后，已在持久recovery目录按既有原git tree、补丁与真实会话源码编辑恢复；17/17文件逐字节匹配Round3索引，原102项重新通过后才开始此修复。冻结Round3草稿和旧审批保持不变。Round4需新nonce、新controller摘要及精确预览；当前不部署、签名、安装或播放。

## Round7执行前schema差异（2026-10-27）

目标系统包只读实证bm dump输出带精确包名标题，指纹为applicationInfo.fingerprint；当前parser要求纯JSON/signatureInfo导致已证失败。仅本地TDD修解析，产品/HAP/工具不变。完整场景结果仍仅由现有终端最终JSON白名单提取，禁止录制密码TTY；缺最终JSON则待验。执行前保存旧journal脱敏快照，执行后允许当前journal正常更新。120秒是场景时限，签名/查询/清理另有界；不承诺整事务120秒。

## Round8诊断修复边界

Round7已验签与安装成功，collect已收到终态并回传应用保屏释放证据；后续validate_events拒绝最终事件序列，但旧报告只有unclassified错误，具体失败项因原始events删除而无法确定。cleanup前置归属/命令未抛异常，但cleanup_proof联合门禁false，具体分项不可恢复；事后无残留不改原cleanup-unknown。最小本地方案：固定nonce文件原子保存有界白名单事件/读取状态、准确固定错误码、各cleanup命令摘要与语义分项、最终结果；禁任意value/异常文本/全TTY，SIGKILL仅保证此前快照。旧journal锁下新鲜身份对账另行方案和批准，当前不实施。

Round8本地实现：独立smoke-<nonce>.json绑定已验证的approval/controller SHA、bundle、unsigned HAP，启动后绑定可信PID/startTicks及时间。每次读取事件即重建固定事件/字段和APP错误枚举；未知名称/值仅摘要，损坏JSON保留之前可解析行及坏行长度/hash。每条cleanup命令立即保存退出/超时和输出长度/hash、对应语义布尔及归属进展，最终结果与TTY独立。签名/安装通过不因后续场景失败丢失，完整验签成功去除旧nextRequired静态提示。异常中断明确interrupted；证据写失败独立于原归属门禁下的必要清理，并使结果失败。磁盘完全不可写或SIGKILL仅能保留已成功原子写入的快照，不能承诺捕获未来动作。

旧cleanup-unknown不通过更换state目录绕开。本轮仅提出下一次精确批准前置：锁下新鲜全项只读核对、原journal按39adc…精确字节归档、追加cleanup-only对账记录，之后才更新可变事务头；不得把Round7场景改为通过。当前未实现/执行对账命令，未部署、签名、安装、播放或推送。

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

## Round12：EOF 交付与严格窗口收尾（本地实施中）

Round10 f2288b69已按精确批准推送，run40536674072 attempt2云端组合通过；Round11新HAP签名/完整验签/安装通过，但40.804s记录DIAGNOSTIC_UNAVAILABLE，无EOF。首帧/暂停恢复/seek/重开已有证据；窗口严格门禁实际42总数/41行失败。旧封存和cleanup-unknown不改。

已确认产品已有completed类型但正常MPV END_FILE未交付到公开状态；仅补正常EOF的精确媒体身份事件链，不改变公开API/诊断新鲜度。loadfile reply_userdata及返回playlist_entry_id绑定epoch/generation，旧reply/EOF、stop/quit/redirect/error、terminal/release拒绝；EventLoop不取lifecycleMutex以免与Release join死锁。fixture采样期间EOF竞态只允许同cycle有效近尾诊断与真实completed事件组合，不用诊断失效或时间推测完成。

窗口不放宽现有解析。仅计数不完整且已观察行无目标的情况允许最多3次、总5秒重新查询；每次连接/包生命周期/进程/Ability仍严格核对，非计数错误或目标存在立即失败。每次快照/守卫结果先持久化，最终必须完整严格快照才能确认；永久42/41仍失败。原失败的系统快照成因尚不确定。

先真实函数RED/GREEN及交错/取消/错误边界，再真实ArkTS/native目标构建。无推送/远端配置/签名/设备执行，本地精确预览交根审；TV/候选/八库/SDK不变。

Round12验证边界：已证正常EOF事件交付存在源码缺口；旧Round11未保留MPV结束reason，不能断言当次失败完全由这一缺口造成。正常EOF仅在loadfile reply_userdata和playlist_entry_id闭合后投递，reply晚到END_FILE不补判成功；同URI重载仍以独立entry区分。buffering使用既有completed状态合法边，公开类型与诊断新鲜度不变。窗口上游实现存在总数包括被过滤session的机制线索，但尚未证实目标TV版本相同或当次具体原因；严格42/41原输出仍不通过，不做总数容错。

本轮本地同源码HAR与独立unsigned HAP已实际构建，未签名、未设备执行。窗口三轮各项白名单命令摘要/结构证据均持久化（32条总上限内），最终检查仍调用原始window_pids，其AST与本轮基线一致。新增重采资格不会改写原输出或接受不完整快照；最后一次慢返回超过5秒同样拒绝。源码/日志/输入清单及清理记录置于Round12隔离证据，旧封存不回写。


## Round14 最小实现顺序

先以真实 FixedDevice.cleanup 和 SmokeEvidence 建立旧源码 RED，再调整终态采样。卸载前最后一次安装生命周期复核，明确卸载成功后一次六查询；不复用旧窗口/PID/Ability。前置窗口硬失败单独锁存，证据写失败保持失败；旧完整性解析逐字冻结。证据 phase 只接受 pre-uninstall/post-uninstall 固定枚举；旧 history32 上限不变。最坏实际29条（旧路径实际24条，替换末尾2条为6条，再加1次身份复核），所有中间失败保留。

匹配验证为 imac/executor/controller/reconciliation 与真实官方签名 CLI 参数契约回归（仅解析、不签名）；pages helper 源码/输入不变，本轮不重复其官方派生测试；增加复用旧窗口、擦除硬失败、漏最终期限、漏卸载前归属四类变异。产品/库/fixture/HAR/HAP不改，无需目标重编。根审通过后整理精确提交，推送和再次设备执行另给预览；本轮无远端动作。

## Round16：最小签名前对账补充

先真实 ReadOnlyDevice.snapshot/reconcile 测试复现无 PID 阻塞，再仅修改 reconciliation 对精确未安装签名失败的判别和旧 PID 条件检查；window_pids 必须无条件完整调用。保留正 PID 原路径及全部归档/CAS。当前只交设计和 RED，审查后实施，禁止部署新执行器或复用旧 nonce。
