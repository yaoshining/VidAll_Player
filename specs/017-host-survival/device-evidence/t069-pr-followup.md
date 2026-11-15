# T069：PR94审查与iMac CI跟进

2026-11-15，用户授权先提交main PR，API19 TV/x86_64缺口显著披露。PR为https://github.com/yaoshining/VidAll_Player/pull/94，源分支codex/host-survival-contract。第4项未完成，不自动合并。

## 首轮CI失败及修复

27ba36c/26a09bb的原生契约与组合宿主契约均在producer-input锁校验失败，未运行的后续步骤不算通过。锁仍指向早期Spec017 libmpv ee78bf...，而生产候选56ebd3f与T068验收包已使用405ce871...。本地原test_current_frozen先失败；核对实际输入审计及T066 CI九库后，只更新七个已变化的mpv清单/源码/编译绑定哈希和当前候选说明。六个FFmpeg库、C++库及FFmpeg来源记录完全不变。

追加CI/libmpv身份、设备来源和非实验编译标记回归；三个锁定/篡改测试通过。保留精确哈希锁、越界/符号链接拒绝、tracked源码快照、formalArtifactAllowed=false及producerLatestNormalFullCloudRebuildVerified=false。不以刷新锁宣称新上游云端源码构建或API19/x86_64资格，不关闭未完成验收。

## 审查服务的实际限制

- Codex在PR创建时返回code review usage limit，未完成审查；不自动购买额度或重复请求。
- CodeRabbit跳过：583个可审查文件，超过100文件限制。
- Bugbot跳过：58,109行/3,813,742字符超过可审查限制。
- 不能将SKIPPED、零条审查意见或路由检查成功称为代码审查通过。保留全部生产测试与失败证据，不通过隐藏源文件、删除测试或伪造通过绕过审查。
- 如服务限制持续，应将实现/对应测试与历史证据分层组织后再请求审查；本轮不擅自删除证据或更换main目标以伪装完成。

## 当前状态

首个27ba36c分支iMac CI43700897420已构建HAR/独立消费者/Hypium成功；不是后续最终head通过。最终head的PR合并预览CI、原HAR/九库核验与审查状态继续跟进。API19正式入口、完整x86_64产物、API26历史独立复验和物理同步仍按PR正文披露；#93非阻塞未解决。

Todoist子项：提交PR 6j2cRxqXR7rG9RQG已完成；CI 6j2cRxrwQpXHm5wp、审查6j2cRxw9HPpRP8xG未完成；根任务6j295Q7jffjHC3qp开放。负责会话修复 issue #89 / local / 01a1bccc-e2cc-7a13-8cd6-31aae7079fb0。
