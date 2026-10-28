# 任务与交付分段

## 当前验收矩阵（2026-10-28，Round16 后）

| 范围 | 当前结果 | 未覆盖边界 |
|---|---|---|
| 云端宿主/目标构建 | b16d490a、实际merge d688e99c、run40570621495 attempt2通过；HAR/consumer/Hypium编译/unsigned设备包已独立核验 | 不覆盖本轮未提交的reconciliation分支；Hypium不等于真机运行 |
| Round16本地修复 | 对账器34、imac79、executor47；真实RED及两语义变异通过、根审通过 | 精确新提交推送及对应新CI待批准 |
| 独立真机链 | Round16签名/完整验签/安装、35.364秒短测、保屏false、卸载后六查询43/43与材料清理通过 | 仅既有专用短场景，不扩产品/物理HDR/未确认声画/旧未覆盖故障 |
| 窗口修复 | 前置三次44/43拒绝并保留，卸载后一次新43/43严格通过 | 非旧42/41原样重现，系统漏行对象仍未知，旧失败不改写 |
| GitHub手动真机工作流 | 尚未实现、尚未配置或启用 | 交互密码、默认分支入口和iMac执行权限需后续独立方案/批准 |

旧SDK锁、产品API、八库、TV和候选不变；formalArtifactAllowed=false。以下早期“当前/待验”文字是对应日期或阶段的历史记录，当前验收以本矩阵及Round16证据为准，不能据旧阶段状态否认已完成范围，也不能将本轮成功外推为全部验收。

- [x] T001 只读盘点5个Player工作流、4条self-hosted job、独有CTest/Hypium/签名与设备入口。
- [x] T002 根审查覆盖映射、A/B/C边界及producer/iMac实测事实；明确A阶段可实施文件。
- [x] T003 A阶段真实RED：旧测试built语义、云端覆盖及默认路线缺口。
- [x] T004 A阶段本地实现与测试：完整host检查、DevEco26 HAR/consumer、无签名Hypium实际编译及失败关闭汇总；最终精确重放属T005。
- [x] T005 A阶段根审查、精确本地提交/clean重放/证据/清理与推送预览；冻结f0b878云端run40163756590 attempt2已通过，本轮新增C不包含在该结论内。
- [x] T006 B阶段核对既有producer云端证据与旧source独有覆盖，固定004交付；最新normal完整目标重建仍待验。
- [x] T007 B阶段本地退役历史self-hosted生产入口，完整来源/许可证/打包契约及固定交付组合保留；远端效果待新CI。
- [x] T008a C阶段最小方案与独立短测/可信控制器边界已审，获准本地实现。
- [ ] T008b 精确提交、二进制上传及本机配置预览/批准；尚未推送或配置。
- [x] T009a C阶段无凭据制品/载荷/互斥/未就绪控制器22项TDD（不执行签名/验签）。
- [x] T009b 官方verify-app/verify-profile/实际Signer SID与签名/安装适配器本地实现和宿主TDD。
- [ ] T009c 专用签名材料、真实验签及runner/环境/label配置获批后实施；本轮未配置。
- [x] T010a C阶段固定控制器的本地手动签名、完整验签、一次真机短测及应用保屏/卸载清理：Round16通过，旧失败保留。
- [ ] T010b GitHub手动触发真机workflow、专用runner/审批环境配置及端到端触发验证；当前未接入。
- [ ] T011 全部构建云端覆盖审计与正式required check选择，旧锁/产品API/八库/TV边界复核。
- [x] T012a 保留42d79云端原生契约失败及本地11脚本9过2失败；同步两处历史配方断言。
- [x] T012b 活动必经步骤/双平台/元数据/上传与历史SHA解析门禁，含注释、echo、忽略失败等27变异拒绝。
- [x] T012c 返修f0b878完整原生链/元数据/关联门禁重放、复审、批准推送及云端attempt2成功；host106/target46索引根核验完成，旧失败保留。
- [x] T013a 新device-smoke隔离入口与云端同源unsigned包真实RED/GREEN；无NAS/网络/备份，120秒短测覆盖暂停恢复/seek/重开；探索构建不作为冻结源码证据。
- [ ] T013b 冻结提交后真实clean HAR→unsigned HAP同源重放。
- [x] T014 独立device-tools观察锁、外部精确事务审批、签名/官方验签/载荷对比适配器TDD；真实材料/口令可用性明确pending。
- [x] T015 全事务互斥、nonce/PID/包身份结果判定、超时/断连cleanup持久journal真实函数TDD；输出替身不算目标设备schema验证。
- [x] T016 固定已审控制器真实签名/完整验签/安装/短测/清理闭环：Round16按精确授权通过；不扩大到未覆盖项目。
- [ ] T017 根独立审查、本地精确重放/边界与清理；代码、二进制上传、工具/签名/runner配置精确预览，尚未推送或启用。
- [x] T018 2026-10-26 实际设备 UDID 提示 `is :` 与 HDC 五列格式兼容，真实脱敏格式 RED/GREEN；前缀、单值、长度/字符、错误输出、重复/冲突目标与批准摘要继续严格核对。32项适配器测试通过，仅本地修复；本地实现与根审已完成；推送、新CI、执行器新身份批准及签名/实机执行仍待验，既有云端 HAP 身份不变。

- [x] T019 2026-10-27 执行前包清单末尾冒号、实际窗口25列与固定统计块适配；真实RED/GREEN、38+23+19项宿主检查及固定iMac Python3.9.6内存导入/真实只读解析。修改尚未提交、推送、部署或新CI验证。
- [x] T020 手动CSR/公开证书配对、官方profile验签、专用bundle/单电视摘要与normal APL/空ACL权限核对；p12仅容器SHA/stat，不证明解锁或实际签名。
- [ ] T021 审批精确材料传输/可信文件部署/交互签名与≤120秒短测/有界清理；当前仅预览，原本机材料保留，实机未验证项保持待验。

- [x] T022 首次获批签名尝试结果与副本清理留证：sign-app成功，后续ContractError原因未定；未安装，12份远端副本删除、journal/已消耗nonce保留。
- [x] T023 本地安全失败诊断TDD：只保存固定错误码/阶段，未知/敏感文本不输出；23+38+23测试通过，未部署或再次签名。
- [ ] T024 新控制器审查/精确预览及用户批准后，再验证signed HAP和短测；不得重用旧nonce或审批。

- [x] T025 Round2独立纯签名验签模式本地TDD：审批/CLI交叉绑定、设备只读命令护栏、专属结果和消耗nonce，明确不调用任何设备写入。
- [x] T026 官方outCertChain后缀契约真实证据+RED/GREEN；仅改.cer文件名，继续核PEM链/实际Signer/profile/payload。
- [x] T027 Round2精确批准后的临时部署、用户TTY签名和副本清理完成；verify-app/profile/SID通过后payload成员门禁失败，完整验签不通过。专属结果与已消费nonce保留，从未安装/播放。

- [x] T028 Round3先RED覆盖精确派生正例、错内容、原成员增删改、重复/歧义ZIP、派生失败与有界脱敏差异；只允许同锁官方JAR从批准unsigned独立生成.pages.info。
- [x] T029 Round3 helper本地构建、真实无私钥派生15项、控制器102项及根代码复审；13文件精确预览已准备，未执行。
- [ ] T030 新预览获用户批准后，仅签名与完整校验；不安装播放，新远端CI/实机验收仍待验。

- [x] T031 Round3真实CLI拒绝-a4结果封存及13副本清理；nonce/result/journal保留，未安装。
- [x] T032 原checkout消失后持久隔离恢复：原git tree及17文件摘要精确匹配，离线按锁恢复测试依赖，102项通过。
- [x] T033 实际prepare_signed argv进入同锁公开CmdUtil解析RED/GREEN，只删除-a4；生产argv接受、-a4和未知参数拒绝，imac43回归通过；保留signCode1及内部默认alignment4证据。
- [ ] T034 根审后Round4精确仅签名预览与用户批准；当前不部署或自动签名，设备项目仍待验。

- [x] T035 Round7实际bm dump包名标题与applicationInfo.fingerprint兼容：先实测脱敏形状RED，保留精确包/版本/指纹/生命周期与旧格式无歧义门禁，补安装清理真实函数链；本地51项适配器及28+31匹配回归通过；根审后才出新控制器审批。

## 2026-10-27 当前状态补记（保留上述分阶段历史）

- [x] T036 Round4官方口令不匹配、Round5提示超时/中断pending均原样保留并清理；Round6重新签名与完整校验passed，result SHA c5082024…，13副本及临时signed HAP已删除，6nonce/旧journal/结果保留。仅签名验签通过，T016/T021安装短测仍未完成；无可安装签名包留存。
- [x] T037 Round7已获精确批准并执行：签名/完整验签/安装身份通过，终态事件验收失败，原清理联合门禁未确认；事后只读无设备残留且13宿主副本清理，原journal cleanup-unknown保持。此勾选仅表示本轮执行与失败记录闭环，不表示短测验收通过。

- [x] T038 Round8本地失败证据闭环TDD（executor43/imac58/controller28通过；根审129项及最终固定枚举补丁已通过，远端执行未完成）：本nonce安全事件快照/精确固定错误码/逐项清理证据和独立最终结果在私有输出删除前原子持久化；异常中断不记passed。保留Round7失败原字节，对账另审，不远端写。

- [x] T039 Round8诊断根审及Round9对账方案/精确预览审查完成；用户批准后执行结果单列T043，设备短测仍未通过。

## 执行器累计修复提交收尾

- [x] T040 盘点568a68以来恢复的执行器/测试/helper/当前规格依赖，保留旧失败封存，整理自包含文本修复和脱敏汇总；不包含材料、凭据、原日志或二进制。
- [x] T041 e6c97c87精确本地提交/clean重放/秘密扫描及根审通过，经用户批准推送；新merge另获批准，run40498456949 attempt2 host/target/summary成功。真实helper/CLI专项保留本地重放边界，不冒称云端执行。


## 2026-10-27 cleanup-only 对账补充（Round9已按精确批准执行）

独立 `reconciliation.py` 复用同一设备锁与只读解析，既有 controller/executor/imac 原字节不变。外部精确审批绑定脚本及依赖、工具/设备、旧 journal 与 nonce、原 nonce 账本及有效期。锁下新鲜核对专用包、进程、Ability、窗口和宿主活动均不存在后，先 O_EXCL 原字节归档和独立只读证据，再比较并原子更新可变事务头；任何前置失败不解除阻塞，账本永不改写。旧短测始终未通过，不将对账当作场景验收。

TDD 覆盖正常对账、摘要/nonce/设备/工具漂移、锁冲突、残留和未知状态、归档/证据/写头失败与中断。新短测使用 run 40498456949 attempt 2 的 artifact 12732547397/HAP 2cb2aa0f…；最新 HAP 独立派生 pages 与旧值相同不表示可沿用旧批准。Round9的对账及一次短测已取得独立精确批准并执行：对账成功，签名/验签/安装通过，场景及运行时窗口门禁未通过，原失败保留。未来远端写入及执行仍须新精确批准；手动 workflow 留到短测通过后另审。

- [x] T042 独立 cleanup-only 对账本地真实RED/GREEN28项及旧执行器129项回归、根审代码检查完成；精确预览获批准后Round9对账已完成；保留原失败及原字节归档。
- [x] T043 Round9获批执行对账及新HAP一次短测：签名/验签/安装通过，440ms首帧前DIAGNOSTICS_STALE失败，运行时window-evidence-invalid未确认；事后无残留、临时材料清理完成。此勾选仅表示执行和失败留证完成，旧Round7/9失败不改写。


## Round10：独立短测 stale 重新采样与窗口失败诊断

Round9 对账、签名/验签/安装已完成；短测在440ms首帧前以DIAGNOSTICS_STALE失败，原运行时窗口证据门禁失效。原失败、事件摘要、cleanup-unknown和8nonce不改；事后无残留不追认通过。

仅在独立fixture消费层捕获精确DIAGNOSTICS_STALE：初次计入最多50次请求、100ms间隔，重试预算5秒；在各await返回后核期限并拒绝晚到成功，不声称能取消平台中尚未返回的Promise；继续受原场景deadline/取消约束。每次await前后检查，terminal/released/同player或cycle已变优先失败，其他错误不重试，不修改产品API的新鲜度语义。先真实共享函数RED/GREEN，随后真实ArkTS unsigned编译；宿主替身不算设备通过。

窗口只补固定解析错误码和有界结构/计数/输出摘要持久化，不修改window_pids原接受条件，不忽略行或自动重试。未知原始窗口名/错误/其他应用数据不入证据。现有证据不足以确定Round9窗口失配原因，本轮不能宣称已修复该真实根因。

本轮仅本地实现/验证和精确提交预览；推送、配置、签名及再次设备执行分别待批准。手动workflow仍不接入。

- [x] T044 stale有界重采样/取消与terminal真实函数TDD、窗口精确脱敏诊断TDD及根审完成；session25/platform11/imac60/executor45/controller28/reconciliation28通过。窗口真实失配根因仍待新鲜证据。
- [x] T045 真实ArkTS unsigned编译与16文本文件提交范围整理完成；精确提交clean回放及推送预览结果保存在仓外绑定最终SHA的 publication，未通过不得提出推送。
- [x] T046 精确提交f2288b69已获批准推送；run40536674072 attempt2组合CI通过。随后Round11已单独批准执行并保留失败；这不表示真机通过。

Round10本地目标验证：DevEco26锁定工具与空signingConfigs独立工程实际clean/build通过。首次ArkTS拒绝未声明类型的throw已留失败日志，最小改为Error类型断言后通过；消费保留HAR ef9e196b…，不冒充当前提交同源云端HAP。现有host job仅新增独立reconciliation.test.py一条命令及工作流变异断言，无新增设备workflow、runner或权限。

## Round12：EOF 交付与严格窗口收尾（本地实施中）

Round10 f2288b69已按精确批准推送，run40536674072 attempt2云端组合通过；Round11新HAP签名/完整验签/安装通过，但40.804s记录DIAGNOSTIC_UNAVAILABLE，无EOF。首帧/暂停恢复/seek/重开已有证据；窗口严格门禁实际42总数/41行失败。旧封存和cleanup-unknown不改。

已确认产品已有completed类型但正常MPV END_FILE未交付到公开状态；仅补正常EOF的精确媒体身份事件链，不改变公开API/诊断新鲜度。loadfile reply_userdata及返回playlist_entry_id绑定epoch/generation，旧reply/EOF、stop/quit/redirect/error、terminal/release拒绝；EventLoop不取lifecycleMutex以免与Release join死锁。fixture采样期间EOF竞态只允许同cycle有效近尾诊断与真实completed事件组合，不用诊断失效或时间推测完成。

窗口不放宽现有解析。仅计数不完整且已观察行无目标的情况允许最多3次、总5秒重新查询；每次连接/包生命周期/进程/Ability仍严格核对，非计数错误或目标存在立即失败。每次快照/守卫结果先持久化，最终必须完整严格快照才能确认；永久42/41仍失败。原失败的系统快照成因尚不确定。

先真实函数RED/GREEN及交错/取消/错误边界，再真实ArkTS/native目标构建。无推送/远端配置/签名/设备执行，本地精确预览交根审；TV/候选/八库/SDK不变。

- [x] T047 EOF身份交付与fixture竞态真实TDD、严格窗口有界采样证据闭环；根审匹配宿主回归通过，真实设备仍待验。
- [ ] T048 同源native/ETS HAR→独立unsigned HAP本地clean编译已通过，八核心/API与锁定输入不变；最终证据/提交范围等待根审。提交/推送/再次执行分别按授权推进，当前未执行。

Round12本地构建使用明确逐字节源码清单和空签名隔离副本：先构建当前native/ETS HAR，再由同一快照fixture消费该HAR。首次准备因评估器要求副本Git元数据失败，未到编译，已保留；仓外脚本以新副本无旧产物及源码清单替代该本地前置后，真实clean/build通过。未修改CI源码身份规则，不把未提交快照称为云端精确提交。两个专属daemon均已停止，重复产物待证据核验后精确清理。

新native测试编译实际Load/Stop/COMMAND_REPLY/END_FILE/DispatchCompletion，NAPI投递使用替身，Release仅核真实源码失效早于released/join顺序；删除三处生产接线的变异均被拒绝。不是设备强并发或真实TSFN验收。现有host job仅追加一条completion-event.test.py，配套工作流删除变异，无新job/权限/手动设备workflow。

## Round12 CI返修：父级真实切片依赖闭包

精确提交baf386e4已按用户批准推送PR82。run40556300632 attempt1中新EOF/执行器契约、原14CTest及producer检查通过；全量47链的父级切片在编译时缺少Release新增调用的InvalidateCompletion，parent-green及三组变异均exit2（不是预期语义失败），汇总失败。诊断40556300805、原生40556300830成功；target因新merge未授权仍跳过。旧失败artifact12756314709完整95文本索引已核，保留原始失败。

最小修复仅提取实际InvalidateCompletion到原parent-chain编译链、补对应mutex/epoch/entry/vector成员；normal-explicit-release从非空状态验证真实失效清空。没有空stub、删除旧断言或修改产品源码/核心库/工作流，也无需重建先前已验证HAR。完整normal-core/run.py 47项及原父级变异已通过；临时TU将失效函数置空或删除Release调用的两项变异都以FAIL/94被拒。首次推送前精确回放遗漏该完整47链是验证范围缺口，本次按原完整入口补齐，不以其他局部通过替代。

- [x] T049 CI失败定位、真实编译RED、实际函数依赖修复与47项GREEN、失效语义变异、根审代码检查完成。
- [ ] T050 本地精确返修提交/重放及新推送预览；用户批准新SHA后方可推送。新merge目标配置仍另批，设备/旧事务不操作。


## Round14：卸载后的严格最终快照（本地 TDD）

Round13 已核验签名、完整验签、安装与 EOF 短场景；事务仍为失败，三次卸载前窗口均为 42/41 且摘要相同。事后只读 41/41 不追认原事务成功。精确系统实现和被省略对象未知。当前可直接证明的执行器缺口是所有窗口样本在 uninstall 前，最终 cleanup_proof 复用此前证据。

- [x] T051 先增加真实 FixedDevice.cleanup/SmokeEvidence 回归：三次前置计数缺口后单次严格完整终态；正常前置也需新鲜终态；前置硬失败不得被健康终态掩盖；卸载前身份复核；终态 5 秒、六查询、失败/缺项/晚到拒绝及证据保留。
- [x] T052 最小实现并匹配回归/变异、独立审查；window_pids 逐字冻结，前置最多 3 次/5 秒不变，终态仅一次，history 上限 32 不变。
- [x] T053 b16d490a精确提交已获批推送，run40570621495 attempt2云端组合通过；Round16已按新执行授权验证卸载后终态。旧失败/归档/nonce保留，未接入手动workflow，未重跑长播。

终态完整快照发生在卸载后，依次重证连接、UDID、包不存在、原 PID 不存在、Ability 不存在及完整严格窗口。终态 5 秒单独计为清理时间，每个调用前后检查，不延长 120 秒播放预算。仅合法计数缺口且未观察到目标允许后验；断线/身份漂移/目标存在/坏行/timeout/证据写失败均不能转为成功。不改产品、八库、HAR/HAP、TV、候选或系统设置；本轮只做本地执行器修复。

## Round16：密码重试前的精确未启动事务对账

- [x] T054 真实函数 RED：official-sign-failed 未安装无 PID 应只读对账；未知/已启动/计数不完整/残留及 timeout 拒绝。
- [x] T055 最小 reconciliation 实现，34 项对账、79 项 imac、47 项 executor 通过；跳过窗口解析/放宽未知无 PID 两项语义变异被拒，旧原始失败/nonce/CAS保留。根审及Round16精确授权A/B执行已通过；本地新源码的精确提交/推送及对应CI仍待审批。
- [x] T056 Round16精确两段预览经用户批准，A保留签名前失败原字节、11旧nonce后推进头；B签名/完整验签/一次35.364秒短场景/卸载及终态窗口通过。卸载前三次44/43原失败保留，卸载后六查询43/43通过，history29。HOST临时15文件/launcher按批准清理；未提交推送，无新CI。

Round16 仅覆盖本轮独立短测与窗口清理修复；旧42/41、Round15官方签名失败及清理timeout不改写。电视OS内部漏行对象仍未知，formalArtifactAllowed=false，运行映射库哈希未验证、物理HDR/主观声画及其他旧未覆盖项仍待验。原材料和全部归档/nonce保留，只使用应用保屏，未改系统设置。证据保存在本地签名审查目录round16/RESULT.json及根审记录，本轮不得据此声称手动GitHub设备workflow已接入。

- [ ] T057 将Round16对账器修复与脱敏RED/GREEN/变异/实际清理证据整理为精确提交，独立clean重放及根审后请求推送；无新workflow/远端配置。
