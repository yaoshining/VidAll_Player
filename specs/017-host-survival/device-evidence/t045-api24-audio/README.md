# T045 API24 云平板音频验收失败记录

2026-11-12 约22:00–22:12（设备日志时区），内置浏览器操作 MatePad Mini、MLR-AL10、HarmonyOS 6.1.0.125、API24。仅使用免费额度；本轮结束已释放设备，余额由287分钟变为275分钟。

安装云端“Spec017内录-普通与焦点”1.0.45成功；HAP及原始 iMac CI HAR、九库身份见上级 t045-full-audio-preparation.json。此HAP是本地消费构建，不是最终CI产物。关闭/全局故障两包未执行。

- 首次授权超过15秒，页面 CAPTURE_START_TIMEOUT；这是失败尝试，不是录制成功。
- 后续授权成功，实际显示测试视频及系统录屏指示。焦点模式三次均出现 SYSTEM_PAUSE_MISSING；其中PID2628的同轮系统日志记录22:11:14 hintType:2，另有 OHAudioRenderer 提示中断回调未设置。未把页面失败理解为进程退出。
- 普通模式PID62404显示视频，最终 DIAGNOSTIC_UNAVAILABLE。源码检查发现工具对durationMs调用拒绝estimated的通用读取器，而生产契约明确将durationMs标为estimated；此项首先按验收工具缺陷处理。
- mpv当前补丁的API>=20路径仅注册WriteData回调；API<20才注册Interrupt。需要为现代路径补真实回调及会话生命周期回归，不能归责FFmpeg。
- events.jsonl和capture.mp4仍在应用私有目录；云Shell对/data/app/el2拒绝访问，尚未导出实际音轨。页面播放、录屏启动和RUNNING日志都不算声音验收通过。云HiLog提供了附录中的可见日志；早期按P17筛选无记录，不能据此声称没有事件。
- 结束时点击“导出并释放”，设备已回到列表；未核实浏览器自动下载文件，不将其记为已保存证据。已保存的证据为本目录截图和可见日志文本。

## 验收结论

T045仍未通过。需要修正时长断言、现代音频打断路径，并提供可经云调试导出系统内录的验收工具，再用新CI HAR和对应诊断包复验。实际音频、故障后旧音消失与新音出现均未通过；API24不替代API19 TV正式文件入口。尚不创建PR。
