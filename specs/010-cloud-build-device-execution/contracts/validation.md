
## Round7安装身份格式与证据边界（2026-10-27）

Round6已真实签名且通过verify-app/profile/SID/精确派生.pages.info及原载荷/最终摘要门禁，专属结果SHA c50820241f1f02619db5f148397db17261fa175785634266f36ef0c9e9ac249c；仍未安装/播放，临时signed HAP按批准删除。旧阶段的材料/签名待验描述为当时快照，不代表当前签名状态；设备功能仍待验。

Round7只读系统包证据发现`包名:\nJSON`与`applicationInfo.fingerprint`。真实函数RED为51项中的3errors+1failure；最小修复后51项通过，controller28/executor31匹配回归通过。仅package_identity生产函数变化：标题必须精确专用bundle，无任意搜索JSON；指纹仅64hex或32组规范冒号，两来源存在必须一致，出现的嵌套bundleName/versionCode与根身份一致；原包名/版本/批准cert与生命周期门禁保留。收紧：实测新格式及任何显式生命周期字段必须为完整正整数对；旧纯JSON无生命周期仍返回installationLifecycleVerified=false，不可用于归属未确认的恢复卸载。测试为真实函数和实测脱敏结构，不是实际安装证明。

短测最终report保留方式拟为用户终端结束后仅提取固定最终JSON，禁止录制包含密码的整TTY；原始events临时文件删除，不声称独立原始事件复验。最终JSON缺失则待验，不能凭journal complete推出scenario通过。部署前保存旧journal脱敏快照/摘要，事务可以正常更新当前journal；身份/安装归属或连接不明时保持cleanup-unknown并停止，不盲卸载。

本轮证据位于持久signing-review-20261025/round7，旧封存不改；未部署、签名、安装、推送或新CI。新执行器需新摘要及精确批准。

## Round8当前结论与证据契约（2026-10-27）

上文Round7“未部署/签名/安装”是执行前历史状态。实际Round7已签名、完整验签与安装身份通过；collect拿到终态、应用释放保屏已确认，但最终事件验收拒绝，旧错误码不足且原始事件已删除，无法确定哪项功能/观测失败。cleanup_proof联合门禁失败的具体分项也不可恢复；事后设备无包/进程/Ability/窗口残留不追认原门禁通过。原journal SHA39adc1fc0409bd99aa0f4177faa6eaf2fc1c5b2c0fb2bc3fcdfa902ab6739119保持cleanup-unknown。

Round8本地真实函数TDD：第一次RED因KeyboardInterrupt穿透提前结束，后续完整RED与增量负例分别保留；GREEN executor43、imac58、controller28。独立nonce文件绑定本机已验approval/controller、unsigned与真实验签摘要，PID由固定适配器独立读取。每次event读取先保存固定形状安全快照，解析失败留坏行长度/hash；未知任意文本不持久化。每条清理命令返回或异常即保存摘要与固定语义分项，后续超时不抹掉前项。独立最终记录明确安装、签名、场景与清理各自状态；中断和证据写失败不能变成passed，证据故障不阻止原归属门禁下必要收尾。所有记录600/状态目录700、唯一nonce、拒symlink/重用/外部改写，大小有界。

本地替身及共享真实SmokeSession宿主轨迹测试不能冒充新真机结果。没有新部署、真实签名、安装、播放、CI或推送。旧失败封存不改；完整终端TTY不保存。磁盘不可写/SIGKILL仅依赖先前原子快照，后续需保持待核而非推定通过。对账仅为待精确批准方案，尚无可执行对账代码。

## 执行器累计修复当前状态

截至本次本地提交准备：专用手动材料签名/完整验签和Round7安装身份通过；短测终态事件验收拒绝、原清理联合门禁未确认，后验无设备残留。旧journal cleanup-unknown及历史失败保留，原始事件缺失不能追认根因。Round8诊断129项和最终根审通过，新控制器尚未设备运行/发布；旧账本对账尚未实现/批准。本提交包含自568a68以来执行器必需恢复/修复文本，保留产品/八库/API/旧锁，现有云端workflow不变；准确执行与证据边界见`../../scripts/test/device-execution/REPAIR-SUMMARY.json`（从仓库根查看）。旧段落中的待办按各阶段日期解释，以上为当前状态。
