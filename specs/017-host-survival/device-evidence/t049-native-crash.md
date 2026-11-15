# T049：HarmonyOS 7 平板当前音频诊断包的原生崩溃（未通过）

2026-11-13 云平板复验，使用已上传的「Spec017录制阶段诊断 1.0.49」。本记录是浏览器 HiLog 可见结果的摘记，不是完整崩溃报告，不包含尚未取得的调用栈。

## 包身份与范围

- HAP SHA-256：`9ef0e1f7bfc3889d217256329a84bd19c0f6009f59816952c464710ed5b7d8e8`。
- 原始 CI HAR 源提交：`62e4e3f8d9648f60713e03d182b2e0f45d923118`。
- 原始 CI HAR SHA-256：`a419c1545680d48ab22983472a8c8ca3311a58bf5904cebdabfde2394e40b704`；实际运行器为 iMac 自托管，不是云端 Mac。
- 实际测试报告：MatePad Air WKI-W10，HarmonyOS 7.0.0.111，ARM64，2800×1840，深圳三；2026-11-13 22:59:53 至 23:19:56。虽然操作时意图选择 6.1.0.112，实际报告与之不符；本轮不能归入 API24 或 API19 TV 验收。报告仅含设备与安装记录，无崩溃附件。
- `bm dump` 确认安装版本 `1.0.49` / `1000049`，包名 `com.yaoshining.vidallplayer`。

## 实际观察

浏览器 HiLog 按应用包名过滤，本轮 PID 为 `3162`：

1. 23:09:15，系统内录 STARTED（事件时间戳 `1794582555352`）。
2. 坏片播放失败，释放后出现 `bad-media-returned`。
3. 正常视频 session2/load1 请求播放，出现 playing、firstFrame1、audible-window-start1。
4. 23:09:16，foundation AppMS 记录 `PROCESS_KILL`，`pid=3162`、`processName=com.yaoshining.vidallplayer`、`reason=Cpp Crash`、`FOREGROUND=1`；平板回到桌面。

本次尚未进入 Alarm 竞争阶段，不能把崩溃归因于音频打断，也不能把 firstFrame / audible-window-start 当成实际可听声音。已观察到退出主进程，故当前验收失败。尚无调用栈，不能判断属于 Player、FFmpeg 或平台。

## 收证限制与后续

- 云端 Shell 读取 `/data/log/faultlog/faultlogger` 返回 Permission denied，未绕过权限。
- 进程退出后的 AudioPolicyService dump 无焦点项，不能据此断言存活期间未登记焦点。
- HiLog 导出接口未返回文件并最终超时，未获得可校验的完整日志附件；随后页面已返回机型选择，本轮 20 分钟免费会话结束，余额 288 分钟。
- 前两次内录授权确认过迟触发 STARTED 等待超时，不算有效播放回归；上述 PID3162 为录制确实启动后的失败。
- 下一步先通过云调试报告取得崩溃栈，定位后补可复现回归，再修改负责层。若定位 FFmpeg，先告知用户，由 ohos_ijkplayer 处理。

T045/T046 及四项交付清单保持未完成；不提前创建 PR。

## API24 独立复验（1.0.52）

新会话设备详情已确认 WKI-W10 6.1.0.112(C00E110R5P1)、API24。PID20348：内录STARTED时间1794585098020；23:51:43 Alarm启动，23:51:49停止（276396样本）并报SYSTEM_PAUSE_MISSING。随后Player released、录制Stop/Release返回，capture-closed=1794585109559。本次没有观察到原生崩溃，不与上文API26混为同次结果。新的导出按钮已通过系统保存选择器成功将spec017-capture.mp4保存到平板“个人”目录，但文件尚未取回本机、未解析音轨，声音仍未通过。

第二次API24运行PID26631的系统AudioInterruptService可见forceType=0、hintType=2（PAUSE）策略；它不能证明Player回调已收到。片段见[t049-system-focus.txt](t049-system-focus.txt)，前次失败流程见[t049-api24-focus.txt](t049-api24-focus.txt)。云Shell读取个人存储被拒绝，文件尚未取回；已释放设备，未保留占用。
