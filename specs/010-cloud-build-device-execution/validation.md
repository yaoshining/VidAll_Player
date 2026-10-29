# 本地验证与未完成范围

> 最终状态更新（2026-10-29）：合并、默认分支 CI 和仍待验收范围见[最终收尾索引](../CLOSEOUT-20261029.md)。下文保留历史时点原文；早期“未推送／未合并／待 CI”不再代表已完成过程的当前状态，旧失败和未验证项不改写。

## 当前验收矩阵（Round17 本地工作流实现）

| 范围 | 当前结果 | 未覆盖边界 |
|---|---|---|
| 云端宿主/目标构建 | e6bc29b4、实际merge 35ceb5f9、run40628969507 attempt2通过；三ZIP、115+53索引和unsigned HAP通过203项独立核验 | 不覆盖本轮新增手动工作流；Hypium不等于真机运行 |
| Round16本地修复 | 对账器34、imac79、executor47；真实RED及两语义变异通过、e6bc29b4已推送且对应云端CI通过 | 不覆盖新增手动入口的远端部署/运行 |
| 独立真机链 | Round16签名/完整验签/安装、35.364秒短测、保屏false、卸载后六查询43/43与材料清理通过 | 仅既有专用短场景，不扩产品/物理HDR/未确认声画/旧未覆盖故障 |
| 窗口修复 | 前置三次44/43拒绝并保留，卸载后一次新43/43严格通过 | 非旧42/41原样重现，系统漏行对象仍未知，旧失败不改写 |
| GitHub手动证据工作流 | prepare/collect本地实现及宿主测试通过；未推送、未配置或启用 | 不含签名/安装/播放；用户官方TTY执行保持独立，默认分支合并及固定可信入口部署另批 |

旧SDK锁、产品API、八库、TV和候选不变；formalArtifactAllowed=false。以下早期“当前/待验”文字是对应日期或阶段的历史记录，当前验收以本矩阵及Round16/17证据为准，不能据旧阶段状态否认已完成范围，也不能将本轮成功外推为全部验收。

## 2026-10-26 设备格式适配

普通HDC连接及只读UDID/profile名单核对已完成，电视在有效probe profile名单中；这不表示应用真机测试通过。真实提示 `is :` 与五列 `Connected localhost hdc` 导致冻结执行器拒绝，已添加脱敏格式回归和重复/冲突/未知尾列负例。新执行器是基于 `568a68d` 的本地修订，不继承旧精确执行审批，需重新审查与预览；已批准云端HAP输入不变。

历史自动材料口令不可用，已按 `scripts/test/device-execution/MANUAL-SIGNING.md` 生成新的手动专用材料。2026-10-27 已独立核公开证书与CSR匹配、官方profile验签通过、probe bundle、唯一电视授权摘要、normal APL及空ACL/permissions。p12仅容器SHA/stat，alias vidallDeviceProbe为用户回忆值；私钥解锁/签名配对仍待实际交互。未迁移、配置iMac、签名、安装或播放。

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

本轮短测的身份范围为 `installedPayloadVerified`：官方验签、原ZIP有效载荷相等及唯一精确派生.pages.info、九库摘要及安装成功/系统包元数据/PID/nonce绑定。`source-identity.json`是交付声明回读，不能证明运行映射逐字节哈希，`runtimeMappedLibraryHashVerified=false`保持；不为此扩大产品API/native或要求设备root。

## 本轮 C 本地 TDD 与审查修复

- controller 当前 23 项，包括 merge_group 正常及错来源/错 group SHA 拒绝；原 22 项历史证据不覆盖本次新增项。
- executor 19 项与 imac 28 项真实函数测试通过；平台命令为替身，正常事件直接取真实 SmokeSession 宿主输出，不是签名或真机证据。
- 已回归外部 unsigned SHA 在签名前/验签后/安装前的绑定，拒 unsigned 与 signed 一并替换；签名期间出现他人同 bundle、安装结果未知、恢复安装生命周期变化和 pre-stop PID 查询错误均禁止清理他人进程/包。
- 完整 CLI 依赖闭包锁定，事务入口完整核验，后续按真实被调用工具核验；采样不重复未执行的 CLI 闭包，保留 120 秒截止。工具观察不等于配置批准。
- 实际 signer helper 使用同锁官方 JAR 的 SignerInfo SID，拒仅附带获批证书的链；临时合成证书测试不能证明用户材料可签名。
- 初始拒绝骨架 RED 是新功能未实现（部分 errors），不称旧代码语义缺陷；ownership 旧行为重放为复审变异复现，原始记录保留。最终日志和逐文件摘要在外部 implementation/executor/GREEN-FINAL.json，避免在冻结源码内自引用。

## 2026-10-27 最新执行前补丁

`1ad19aa` 加当前未提交补丁：包清单唯一ID首行末尾冒号、窗口固定25列与中间分隔线、Focus/SingleHand附属统计严格解析，保留旧三列。缺头零计数、旧表尾未知行、重复/不完整/错误输出等负例拒绝。真实RED保留；imac38、controller23、executor19通过。固定iMac Python3.9.6内存导入三模块和当前包/窗口/Ability只读解析通过；未把这些检查等同签名、安装、退出或保屏清理。旧568a68远端CI与HAP保持冻结，新补丁尚无远端CI。

最新执行预览在外部 signing-review-20261025/MANUAL-EXECUTION-PREVIEW.md；原自动材料/空设备快照只作历史记录。待验仍包括实际口令/alias、官方signed HAP验签、安装元数据生命周期schema、短测、正常及异常清理。

## 2026-10-27 首次获批签名尝试与清理

审批 a3f6b3da… 对应12文件已临时部署并核验。用户前台手动执行，根读取终端确认官方 sign-app success；随后事务返回 ContractError 且未产生 signature 结果，无法确认具体验签失败点。未安装/启动probe，journal为complete、installed为空、cleanup为not-started/deviceMutation=none；nonce已消耗，不得重用。signed/verify临时输出已按原finally清理，不能猜测坏密码或用后续代码倒推原因。

iMac部署目录及12份副本已按批准清除，删除前无活动签名/执行进程，删除后probe包仍不存在；journal与nonce摘要保持，原本机材料未动。公开材料范围与官方sign命令成功，不等于signed HAP验签/有效载荷/安装或播放通过。

为下一次调查新增本地最小诊断：transaction仅持久固定白名单errorCode及阶段，verify-app/profile/实际SID/payload区分；任意错误原文/伪造阶段/平台敏感输出不进入JSON。真实RED3项失败，GREEN23项executor、38项imac、23项controller通过；未提交、部署或重新签名。未来再试须新nonce、控制器摘要及精确审批；本次批准不能覆盖新代码。

## Round2本地预览状态

旧失败的现场错误码未留存；但根已用同锁JAR独立复现确定阻塞：verify-app的outCertChain传.pem会在实际验签前被官方工具拒绝，.cer进入验签流程。文件名最小修复的自动回归先RED后GREEN；不借此宣称该真实signed HAP其余验签项已通过。

新增纯sign-verify模式允许两项安装/卸载权限均false，不安装/播放。executor29、imac40、controller23本地测试通过；现有同锁Java25.0.2及helper Java17字节码版本兼容，未证明新一轮HAP验签成功。材料容器/公开证书/profile、冻结云ZIP/HAP摘要重核一致；电视Connected、probe不存在、旧journal/消耗nonce保留且旧部署目录不存在。新代码与新nonce均需新精确执行批准，尚未提交、推送、配置、传输或签名。

## 2026-10-27 Round2 实际结果与 Round3 本地修复

Round2 官方交互sign-app成功；verify-app、verify-profile、证书/设备/有效期、实际Signer SID已依序通过，随后 `payload-compare/signed-payload-members` 失败。signed输出和临时部署已按批准清理，专属脱敏结果/nonce保留，未安装播放。真实差异成员未保留，因此不能声称本次实际signed仅多一个文件。

根以同锁JAR在冻结HAP做无私钥预处理：19个原成员全部相同，新增.pages.info 6680字节/SHA256 `4364749b8c09d61a99ffa507ca0acd5f794c2d2bfc388243c54a15d4b9f09738`。来源为外置 `round2/ROOT-OFFICIAL-UNSIGNED-PREPROCESS-REPRO.json`，不代表实际签名或本轮新代码通过。Round3新增独立派生helper与安全差异记录，先RED后GREEN；不关闭signCode、不忽略任意文件、不放宽签名者/证书/profile检查。新精确预览、签名完整链和设备验证继续待验。

Round3本地完成：controller28、executor31、imac43共102项通过，含签名后unsigned被替换时验签不执行；真实父级锁代码保持Round2不变。ExpectedPages helper15项使用锁定官方JAR通过，冻结HAP实际派生摘要与根复现相同；双目录编译class一致。新增Python用例已并入既有CI测试入口；新helper的远端CI仍未执行，不以本地结果代称云端通过。预览含13份文件，仅签名完整校验；审批未获前无部署/重签/设备写入。

## Round3运行结果与Round4修复

Round3实际结果failed/sign-app/official-sign-failed，对应用户终端11011005；未产生signedArtifact，未安装播放。nonce已消费，13份临时副本删除、旧journal/结果/账本保留。真实公开CmdUtil解析证明-a4不受信；去掉该对参数后解析通过。此前字节码内部键与stub参数测试不能覆盖公开CLI trustlist，已补真实生产argv解析测试。checkSignAlignment缺省写a=4，后续签名路径读取该值传入copyFileAndAlignment，证据来自同一固定JAR；helper/精确.pages.info要求未变。

恢复源码先17文件原hash匹配与原102项通过，再做真实RED/GREEN；新签名/设备操作仍需新精确批准，未因恢复或CLI解析成功冒称已执行。

## 执行器累计修复当前状态

截至本次本地提交准备：专用手动材料签名/完整验签和Round7安装身份通过；短测终态事件验收拒绝、原清理联合门禁未确认，后验无设备残留。旧journal cleanup-unknown及历史失败保留，原始事件缺失不能追认根因。Round8诊断129项和最终根审通过，新控制器尚未设备运行/发布；旧账本对账尚未实现/批准。本提交包含自568a68以来执行器必需恢复/修复文本，保留产品/八库/API/旧锁，现有云端workflow不变；准确执行与证据边界见`../../scripts/test/device-execution/REPAIR-SUMMARY.json`（从仓库根查看）。旧段落中的待办按各阶段日期解释，以上为当前状态。

## 2026-10-28 Round16 当前收尾

当前结果更新为：Round16专用短测签名、完整验签、安装、35.364秒/20事件、应用保屏false、卸载后严格六查询均通过。卸载前三次真实44/43计数缺口全部保留，卸载后新快照43/43通过；29条历史未截断。它覆盖同类计数缺口路径，不是旧42/41失败改写，也不证明电视系统漏行对象。此前段落是各阶段历史状态，不能继续作为本轮当前结论。

本轮唯一执行源码新增为对账器精确识别official-sign-failed/ContractError/install、初始三字段绑定和installed={}的未启动状态；不伪造PID，不放宽其他缺PID场景。真实RED先于最小实现，34项对账/79项imac/47项executor及两语义变异通过。Round15签名失败和清理timeout原记录、全部nonce保留；本轮临时材料已按批准清理。

精简脱敏证据与实际测试日志见 [Round16证据](evidence/round16/summary.json)。不包含签名材料、密码、一次性执行授权、私人路径或原始设备输出。formalArtifactAllowed=false，运行映射库哈希、物理HDR/未确认声画和其他未覆盖项目保持待验。手动GitHub真机workflow仍未实现/配置；本轮提交只收尾修复和证据，后续方案/配置/执行分别审查。

## Round17 手动准备与只读收证（本地、未启用）

新增 `device-evidence-manual.yml`，只允许 `workflow_dispatch`、固定仓库和默认分支。prepare 在云端核验精确 run/attempt、真实 merge/tree、artifact ID/摘要、manifest/HAP及无签名块，输出“等待本地执行”。该记录不授予签名或安装权限，也不生成执行批准。

collect 不 checkout PR、不读取 Secret、不访问电视，只通过固定已审部署路径和外部入口摘要读取已完成事务。已有进程/session/锁冲突、记录摘要变化、非 complete、清理失败或终态窗口不完整均拒绝。只上传固定脱敏 result.json；不会递归上传 state、原始设备输出、nonce、证书或Profile。它复核既有精确已审smoke摘要，不独立重放播放器事件，也不宣称本轮再次访问设备。

新增入口默认关闭。专用 `vidall-device-evidence` 标签、`device-evidence-read` 环境、可信入口/receipt部署、三个启用变量均尚未配置；不得将标签或路径写入代码等同部署已完成。workflow_dispatch必须先存在默认分支，合并仍须单独授权。官方TTY密码输入保持原机制，Actions不承担交互签名。

本轮TDD：新增入口缺失RED保留，Python 15项与真实YAML/9个变异通过，包括精确attempt、仓库/merge/摘要、真实ZIP额外块、CLI上下文、无令牌collect、锁/session、后验窗口、记录CAS和白名单。只运行宿主验证，无新构建/签名/安装/播放。旧库、API、SDK锁、TV/候选及人走屏灭开启状态不变。推送、配置及再次设备执行分别需要精确批准。

Round17精简证据见 [summary.json](evidence/round17/summary.json)。根审在真实本轮云端ZIP上离线重放prepare通过；另用旧Round16来源和真实已审记录离线重放collect摘要检查通过，两者不组合成新包设备验收。runner现况本轮不重新查询，配置草案保持待核/未部署。
