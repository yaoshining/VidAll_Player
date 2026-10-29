# 最小正常核心接入实施报告

状态：产品实现与本地目标/短真机验证完成，等待独立审查、精确本地提交与用户推送批准。formalArtifactAllowed=false。TV、原 Player 工作树和旧候选未替换。

## 基线和范围
起点 951343145e076277be99f7b459ec614d5a64f8b8，独立分支 codex/004-normal-core-integration。TV 当前 HAR 的 ABC、全部公开声明和运行库身份已绑定；未修改基线的单次重建 27/30 成员一致、sourceMaps语义一致。旧 bridge 历史身份匹配，但新宿主重建不字节一致，native .text 也有差异，不能仅归因于 debug/build ID；该已知差异保留，不追旧哈希。

本轮新 HAR 绑定 Phase30 A/Phase31 正常八库，加 Player bridge 共九库。来源锁、SBOM、许可证和资源索引在 release/inputs/004-normal-core。只有运行资源 smb.conf 外置，Samba大小写表内嵌。未引入诊断字体、禁音或禁字幕配置。

## 实现
- 根入口 initializePlayerRuntime、getPlayerRuntimeStatus、onPlayerTerminal。显式受控退出策略和必需1–10秒截止；同配置幂等、不同配置拒绝，失败锁存。
- 真实 native 先准备私有运行目录及验证 smb.conf，调用 SMB/terminal 公共扩展，再允许 Player 创建。
- NAPI 创建/命令/释放迁至异步工作；UI参数解析、worker持有对象、UI返回结果。终局检查在锁/队列之前，缓存诊断明确标记；晚完成不能重写状态/Surface/媒体源。
- native独立截止线程与完整对象最后引用保护；UNSAFE不能绕过父级析构继续释放。宿主须提示并受控退出，不能复用终局进程。
- TV未来必须新增启动/终局接管并原子去掉旧六库，不能与新HAR混装；详见 docs/normal-core-integration.md。原entry示例未迁移，不属于本轮消费证据。

## 验证与身份
证据均在本目录 evidence，私有完整日志/构建产物在 /private/tmp/phase32-player-integration-20261023/evidence。
- host统一门禁共47条 checks（含工具/编译步骤，不等于47个测试用例），含输入16项、实际ETS/NAPI/父级函数、runtime配置失败、截止计时与去屏障/提前退出/缺deadline反例、HAR规范化；最后一轮见 evidence/host/summary.json。旧原生CTest 14/14。
- 真实父级测试只覆盖所列实际 Release/DestroyRenderer/析构/cleanup及标准线程和引用；完整RenderLoop和平台实现是明确边界。保留 red-01真实缺陷、red-02误命名为GREEN及计时测试错误历史。
- 两次clean原始HAR哈希不同，但39文件完全相同，只有tar时间戳差异。规范化后完整SHA e8fa9afb6c0594d44ac380eb41fe7dff48ea3bc4ba82f279c0ae2e78a4127af4；39文件+14目录的内容/路径/权限完整保留。消费者已实际使用该规范化HAR。
- API24电视正常：两次首帧、零错误、暂停960→960ms、恢复1680ms、seek到20040→20600ms、Vulkan+OHCodec、正常释放/重开与keepScreen=false。
- 指定NAS真实公开Basic鉴权入口：83.33→958.33ms、OHCodec、累计三次首帧且零错误，结束保屏false。只测短场景，不再要求60分钟。
- 独立terminal链接接缝：八核心库不变，5秒触发测试记录，首次通知→状态error→保屏false→host-exit-request；有效查询证明进程/Ability/窗口消失。未独立区分宿主kill和native截止，非真实GPU故障。

## 失败保留与未验收
首轮load Promise后立即play违反既有事件时序，改夹具等待preparing；TV原有适配同样等待prepared，不改变SDK状态语义。15秒seek不位于夹具关键帧，改为既有absolute-percent语义的20秒关键帧，实际位置及推进仍严格验证。SMB早期诊断不可用、HDC普通传递exit0但权限失败、ArkTS构建错误、归档解析/Connected制表符门禁错误均保留，不改写成功。

未验收：低API目标真机、物理HDR/主观声画、真实GPU永不返回及完整平台并发故障。目标/兼容API和默认SDK没有升级。Linux远端host CI尚未运行；专用normal-core.yml仅在精确批准提交推送到本分支或manual触发，已有HarmonyOS工作流不变。本地精确提交及 clean 重放结果在提交外 preview 提供；没有推送、候选替换或正式发布批准。

## 保护边界与提交交付

独立审查者复用历史保护基线检查通过，见 evidence/boundary-final.json。原 Player/TV 的 HEAD、分支、tracked status、index 均匹配，12 个保护产物与 7 个保留文件匹配；producer binary diff 不变、staged 为空，index 既有 stat 差异没有重置。原始私有设备日志不提交；evidence 中的 *.log.txt 和 normalized-consumer-events.txt 是抽取的 P32 应用事件文本。原始日志 hash 与公开摘录 hash 分别记录，不能相互替代。

提交纳入八个新输入核心动态库及来源/许可证文本，不纳入 HAR/HAP、SDK、签名、凭据或媒体。未替换旧候选。精确提交的父提交、变更文件数、实际 blob 字节和八库 SHA 由提交外 PREVIEW.md / manifest.json 给出；批准仅针对该 SHA。

目标源码补充快照见 evidence/target-source-snapshot.json：实际 compile_commands 的三个产品 C++ 编译单元、objects 与 stripped bridge 身份一致；该文件是构建后的关联快照，不冒称构建前封存。模板 PNG 图标也纳入独立 consumer 提交，不含测试音视频。
