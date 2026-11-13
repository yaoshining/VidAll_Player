# T047 内录阶段诊断及设备失败证据

## 本轮实机结果

2026-11-13用户手动上传后，内置浏览器确认1.0.48（Spec017修复-普通与焦点）出现，并安装至API24 MatePad Mini，MLR-AL10/6.1.0.135。两次焦点入口和一次普通入口均显示CAPTURE_START_TIMEOUT，未进入Player播放流程，没有可听音频或焦点结论。最后一次查询PID为35529。约9分钟后云端提示“连接设备失败，请检查本地网络或代理设置后重试”，返回机型列表；不能解释成应用崩溃，未修改代理设置。余额360变351分钟。

随后仅用免费额度申请API24 MatePad Air，WKI-W10/6.1.0.112，同样安装1.0.48。焦点入口与重开后的普通入口均显示内录启动超时；PID先22430，重开后27295。启用诊断日志后取得runtime ready及等待定时器片段，但没有完整录制状态链，不能据缺失日志推断系统拒绝授权。未见可操作的录屏授权弹窗。主动选择导出并释放，页面已回到机型列表，余额345分钟；自动导出的日志文件尚未验证。两台合计扣减15分钟，没有购买或使用手机。

截图分别保留Mini/Air录制失败及Mini连接失败。未取得capture.mp4，音轨分析、人工听声、真实系统焦点、OHCodec/Vulkan故障后音画均未完成；本次失败发生在播放前，不评价T046生产音频修复是否通过。

## 最小诊断改动

独立内录工具增加create/init/mic-off/start返回、等待STARTED、stop/release阶段回报，正常和失败返回分开显示。页面保留最近12条capture事件，每行160字符，换行被规范化；不含素材路径。保留15秒启动期限、一次性录制、无麦克风、必须收到STARTED才播放和未确认release保留fd。生产HAR、九库、FFmpeg及TV均不变。

真实录制器与页面先红后绿，另覆盖init未归还、release失败及有界显示；六套验收工具宿主回归通过，随后修正init返回后取消场景的阶段先后并重跑录制器通过。完整ArkTS编译及签名HAP构建通过，九库与原始iMac CI HAR逐一一致。1.0.49为本地验收包，详见tablet-preparation.json；准备完成时尚未上传或执行，后续实测见下文，仍不计设备通过。

## 后续 CI 核对

930b01a 的 iMac 自托管构建 [43347619195](https://github.com/yaoshining/VidAll_Player/actions/runs/43347619195) 与 Ubuntu 宿主回归 [43347835462](https://github.com/yaoshining/VidAll_Player/actions/runs/43347835462) 均已完成并通过，详见 ci-status.json。本次只核对任务结果，未将新上传附件替换为已核验的 62e4e3f 原始 HAR，也未增加任何设备或可听音频通过结论。

## 1.0.49 实测更新

用户随后完成手动上传，内置浏览器已确认 1.0.49，并在 API24 MatePad Mini（MLR-AL10 / 6.1.0.135）安装成功。普通内录入口的画面显示 create/init/mic-off/start 调用均返回，随后 waiting-started，最终 CAPTURE_START_TIMEOUT。没有观察到 STARTED 或可操作的授权弹窗，未进入 Player 播放。这里只定位到“启动调用返回后等待系统开始通知”，不能据此断定权限拒绝、设备不支持或 Player 音频故障。

页面截图与结构化记录见 `mini135-1.0.49-timeout.jpg`、`mini135-1.0.49.json`。云端生成了原始设备截屏，但内置浏览器下载授权被拒绝，未导出文件、未绕过权限；没有取得 PID 或完整原始 hilog。下载操作等待结束后，云端明确提示本次免费时长已用完，设备已释放；余额 345 → 325 分钟，无购买或手机测试。

核对官方 [AVScreenCapture 使用指南](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/using-avscreencapture-arkts/) 及 [状态枚举](https://developer.huawei.com/consumer/en/doc/harmonyos-references-V14/js-apis-media-V14/)：STARTED 为 0，需监听状态变化确认录制。现有门槛保持不变，不能将 startRecording Promise 返回替代有效录制或听声通过。系统原因仍待可读取的日志/权限交互证据；T045/T046/T047 和设备验收不关闭。

## 下一轮针对性定位

2026-11-13 核对本机官方 SDK 声明：当前使用的 init/startRecording/setMicEnabled/stateChange 均自 API12 提供，STARTED=0；1.0.49 中的录制器源码与仓库一致，未发现状态枚举或调用名称不匹配。官方指南没有要求为禁用麦克风的这条流程申请麦克风权限。

只读参考 [OpenHarmony ScreenCaptureServer](https://github.com/openharmony/multimedia_player_framework/blob/master/services/services/screen_capture/server/screen_capture_server.cpp)：`StartScreenCaptureInner` 可以在请求授权后返回成功，同时等待用户交互；`OnReceiveUserPrivacyAuthority` 接到允许后才启动采集。上游 master 不是该 HarmonyOS 商业设备的精确源码，因此仅用于制定日志检查，不把它作为本轮根因证明。

下一轮先取得应用 PID，再在点击内录前开始针对 `ScreenCaptureServer` 的系统日志观察；核对 StartScreenCapture、RequestUserPrivacyAuthority/StartAuthWindow、等待 ALLOW/DENY、OnReceiveUserPrivacyAuthority、OnStartScreenCapture 及状态回调的顺序。应用 PID 日志与系统服务日志分开，避免只按应用 PID 过滤漏掉服务事件。若窗口正常可见，按已授权的内录流程完成确认；窗口不可见或无返回则保留实际失败证据，不申请豁免隐私窗口、不启用系统特权、不把 Promise 完成改成录制成功。

本轮进入云调试时页面明确提示登录失效，已转至官方登录页等待用户重新登录；尚未申请新设备或消耗新时段。原始截图下载被拒绝后不再重试下载，也不通过其他渠道绕过；可先读取云端已有的可见日志来定位系统路径。
