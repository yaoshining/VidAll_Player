# T069：PR94审查与iMac CI跟进

2026-11-15，用户授权先提交main PR，API19 TV/x86_64缺口显著披露。PR为https://github.com/yaoshining/VidAll_Player/pull/94，源分支codex/host-survival-contract。第4项未完成，不自动合并。

## 首轮CI失败及修复

27ba36c/26a09bb的原生契约与组合宿主契约均在producer-input锁校验失败，未运行的后续步骤不算通过。锁仍指向早期Spec017 libmpv ee78bf...，而生产候选56ebd3f与T068验收包已使用405ce871...。本地原test_current_frozen先失败；核对实际输入审计及T066 CI九库后，只更新七个已变化的mpv清单/源码/编译绑定哈希和当前候选说明。六个FFmpeg库、C++库及FFmpeg来源记录完全不变。

追加CI/libmpv身份、设备来源和非实验编译标记回归；三个锁定/篡改测试通过。保留精确哈希锁、越界/符号链接拒绝、tracked源码快照、formalArtifactAllowed=false及producerLatestNormalFullCloudRebuildVerified=false。不以刷新锁宣称新上游云端源码构建或API19/x86_64资格，不关闭未完成验收。

## 审查服务的实际限制

第二轮760d9b0通过原生来源、双宿主元数据及诊断门禁；组合宿主检查43701366332暴露真实Release测试缺少`<string>`：Ubuntu的标准库不会间接声明`std::stoi`。补齐两个关闭测试的直接头文件依赖，保留七条真实Release路径的断言，不修改播放器行为。修复后重新运行相同关闭回归，最终跨平台结果以新提交CI为准。

760d9b0分支iMac运行43701361922成功，GitHub实际runner为`yaoshiningdeiMac`。原始HAR SHA-256为`bf601c27b478bbf97725c980582909476ba2d4bfbc311b95288f4f7016acc589`，仅ARM64九库，各库与T066/T068已验收产物完全一致。此处不将总体HAR字节一致、API19或x86_64资格推定为通过；后续提交仍需独立CI确认。

- Codex在PR创建时返回code review usage limit，未完成审查；不自动购买额度或重复请求。
- CodeRabbit跳过：583个可审查文件，超过100文件限制。
- Bugbot跳过：58,109行/3,813,742字符超过可审查限制。
- 不能将SKIPPED、零条审查意见或路由检查成功称为代码审查通过。保留全部生产测试与失败证据，不通过隐藏源文件、删除测试或伪造通过绕过审查。
- 如服务限制持续，应将实现/对应测试与历史证据分层组织后再请求审查；本轮不擅自删除证据或更换main目标以伪装完成。

## 当前状态

813f251的Ubuntu真实关闭回归通过；组合门禁43702073657另发现experimental-audio-adapter失败。原runner只写work目录JSON，公开日志为空；同一14场景在本机ASan/UBSan通过。先以失败日志回归复现缺诊断，再补输出场景名、退出码及原始失败文本，不跳过实验门禁、不关闭sanitizer。远端根因待新CI输出确认。

随后本机normal重复第16轮在直接PCM断言失败：回调设计为trylock失败立即填零，测试错误要求每次调用都有PCM。正向检查改为500ms内获取完整PCM，静音必须全零，帧数/内容仍严格比较；时钟夹具包含期间提交的静音帧。确定性锁竞争注入覆盖一次竞争后正常/时钟/暂停时钟及永久竞争必须失败；14场景ASan/UBSan与两项日志回归通过。仅修改测试，不改生产或实验适配器实现。

38c7726的Ubuntu运行43702558744全部102项实际测试通过，最终证据检查因host-checks.json仍只列94项失败。明确补录既有8个首帧/音频新增检查，保留全部旧项及负例退出码。新增回归逐项验证缺失拒绝，CI契约30项通过；对该原始102项summary重新执行严格判定为通过，不把本地重判冒充旧CI成功，新提交仍需重新通过CI。

首个27ba36c分支iMac CI43700897420已构建HAR/独立消费者/Hypium成功；不是后续最终head通过。最终head的PR合并预览CI、原HAR/九库核验与审查状态继续跟进。API19正式入口、完整x86_64产物、API26历史独立复验和物理同步仍按PR正文披露；#93非阻塞未解决。

bc85db8最终复核：分支iMac43703061372与合并预览43703067320均成功，真实runner均为yaoshiningdeiMac；原HAR及ARM64九库已核验，详见[t069-ci.json](t069-ci.json)。组合宿主43703067244、原生来源43703067367、诊断43703067271均成功。全量审查仍因额度/体积限制未执行；不能称PR可以合并。后续仅证据文档提交的最终检查在PR会话状态中继续逐head核对。

Todoist子项：提交PR 6j2cRxqXR7rG9RQG、CI 6j2cRxrwQpXHm5wp完成；审查6j2cRxw9HPpRP8xG未完成；根任务6j295Q7jffjHC3qp开放。负责会话修复 issue #89 / local / 01a1bccc-e2cc-7a13-8cd6-31aae7079fb0。
