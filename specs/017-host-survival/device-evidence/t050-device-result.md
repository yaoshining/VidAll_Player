# T050：当前CI原包API24焦点复验仍失败

2026-11-14，实际设备WKI-W10 6.1.0.112(C00E110R5P1)、API24、ARM64。iMac CI源b13aa09，独立HAP1.0.53；原包及九库身份见[t050-ci-preparation.json](t050-ci-preparation.json)。

PID47542：00:16:07内录STARTED（1794586567862），坏片报NATIVE_PLAYBACK_FAILED后释放，bad-media-returned；新会话2/load1于00:16:08 playing/firstFrame，画面运动。原生日志有真实OHCodec mapper、Vulkan信号/释放与queue-wait-idle，不以copy或软解代替。

00:16:13 Alarm实际启动，系统AudioInterruptService记录forceType0/hintType2/actionOn0；00:16:19停止Alarm（280854采样）后页面报SYSTEM_PAUSE_MISSING。Player及录制器随后正常释放，capture-closed=1794586579477。没有到达手动恢复阶段，音轨未导出分析，不能勾选第1或第2项。API26先前崩溃未在API26重测，不作修复结论。

证据：[流程](t050-focus.txt)、[系统策略](t050-system-focus.txt)、[硬件摘记](t050-hardware-excerpt.txt)。这是可见HiLog摘记，不是完整日志或完整崩溃报告。系统策略不等于原生回调已到达。

T050已修明确共用userdata缺陷，但本次实机证明它不是音频打断验收的全部问题。下一步补注册成功、实际回调、token/恢复代、AO暂停请求及主循环消费的有界诊断，定位断点后再以回归驱动修复；不直接调用pause冒充打断。

本轮结束前再次查询PID仍为47542，随后主动释放平板，剩余免费额度356分钟。

补充Mini：实际MLR-AL10 6.1.0.125(SP20C00E125R1P4)，1.0.53内录出现CAPTURE_START_TIMEOUT，未进入播放，不计焦点复验。准备1.0.54复用既有recovery页面并选择standard，仅采音频初始化日志，不录制、不作为声音通过；HAR/九库不变，HAP SHA256为6f174d7409441c2cbf07fb5b81bdc8e3e858e5c6a5ee5f24ce15cf4efa47749a。

1.0.54在Mini实际运行PID49561，00:24:36及00:24:40均出现 `mpv[ao/ohaudio]: Fail to register renderer callbacks: error code 3.`。已确认音频初始化本身失败，不能再将该画面作为有音频输出的焦点验收。[原始摘记](t050-mini-init.txt)。T051新增局部可见符号红绿回归与官方库句柄查找；仍待实机确认注册失败的具体原因。
