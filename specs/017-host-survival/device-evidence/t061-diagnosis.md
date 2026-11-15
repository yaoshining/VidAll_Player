# T061：实际呈现能力核验（2026-11-14）

## 结论与边界

同步最终归因仍未完成。API24 MatePad Air（6.1.0.112 / WKI-W10）已运行两版独立能力诊断，但没有取得实际上屏时间。不能把T060原始143.511ms偏差全部归为录制，也不能直接判为播放器真实偏差；不添加生产延迟补偿，不降低80ms门槛。

- Vulkan完整枚举成功：Maleoon 935B没有`VK_GOOGLE_display_timing`或`VK_EXT_present_timing`。当前Vulkan逐帧实际呈现查询路径不可用。
- EGL只读查询返回`EGL_NOT_INITIALIZED`（12289），两个帧时间查询入口也未取得。扩展支持状态是**未知**，不是已证明不支持。未初始化/终止共享display，未切换Player后端。
- 能力存在也不等于测到呈现时间；仍须窗口支持、已启用扩展、唯一帧ID、非零实际呈现值及可对应的时基。
- 云设备已释放，页面确认成功，免费余额183分钟；无购买、无后台设备测试。

## 实现、测试与产物

仅独立消费诊断工程新增`libpresentation_probe.so`，使用异步工作线程和有界枚举（最多3次、16个设备、1024个扩展）；枚举失败、反复变化、异常数量不当成扩展缺失。先红后绿覆盖这些分支及候选能力/未知/缺入口的分类；19套工具回归通过，见`t061-host-tools.json`。该探针尚不是逐帧实际呈现采集器。

1.0.76和1.0.77均为本地MacBook Pro ARM64诊断构建，不是最终CI交付。包哈希、十库哈希分别见`t061-preparation.json`和`t061-egl-preparation.json`。原CI HAR与九库保持一致；首次构建曾发现新模块带入不同的`libc++_shared.so`，未上传该包，改用诊断模块静态C++运行库后重建并逐库验证，再上传实测。

原生产候选仍为`cbfc5863832e6becd0f5aa4f099f234ef23f940d`，原HAR SHA-256为`85f3eddab398c8312ad9fb6e49f5f96bfa6a1bc941077e920a3ec16f67407ccb`。FFmpeg和TV代码未修改。

原始事件为`t061-capability-events.jsonl`及`t061-egl-events.jsonl`（后者包含两轮，分析取最后一次能力事件）；分类见`t061-capability-summary.json`。本轮没有新的同步录制或实际呈现采样，不把能力探测记成音画验收通过。

## iMac CI

[43586493407](https://github.com/yaoshining/VidAll_Player/actions/runs/43586493407)已成功，固定源提交`e35c31d177d25b3ac60d5278f87093c6083fa701`。实际runner和机器均为`yaoshiningdeiMac`，是iMac自托管，不是云端Mac。完整HAR、公共API缺失负例、独立消费九库一致性及Hypium编译步骤通过。见`t061-ci.json`。

本轮未下载该次新HAR核验哈希；上述成功也不覆盖此后尚未提交的T061修改，更不代表真机同步验收通过。

## 下一步：现场TV同次音画采集

用户确认有现场TV、非API19；平板只有模拟器。先自行读取已连接设备和项目已有TV地址，核对实际系统、架构及安装条件；历史型号/API不能当当前实测。该TV可以补对应设备的物理音画证据，不替代API19 TV正式入口验收。

本轮连接检查：本机及iMac的`devecocli device list`均无在线设备；项目既有地址`192.168.3.85:5555`的TCP连接明确被拒绝，HDC未能建立连接并已停止本次挂起请求。历史记录为MateTV Pro EDIS-790A/API24，但当前型号/API尚未重新读取。已请用户打开TV网络调试或提供变化后的地址，未安装、重启或修改TV。

在具备安装和采集条件后，保留完整90秒闪光/短音、故障后列表静音与新视频续播序列。用同一外部采集设备同时记录屏幕和扬声器；需测量采集设备自身音视频偏移并计入帧率、曝光和声传播误差，不能简单假定手机录像没有偏移。无法校准时只作人工体验和有限误差证据，不能宣称消除了录制误差。仍保留PID、实际解码/渲染路径和原始完整录制。

## 接口资料与一致性检查

- [NativeWindow](https://developer.huawei.com/consumer/en/doc/doccenter-references/api/capi-external-window-h/)的期望呈现时间属于调度输入，不是已呈现证明。
- [VK_GOOGLE_display_timing](https://docs.vulkan.org/refpages/latest/refpages/source/VK_GOOGLE_display_timing.html)提供呈现引擎时间；仍不能直接当作物理面板发光时刻。
- 本机SDK的`window_manager/oh_window.h`将FrameMetrics标为API26，VSync timestamp描述帧开始；不代替API24/19实际呈现。
- S31 → plan T061 → tasks T061 → 有界枚举/分类测试 → 本地包 → 原始设备事件相互对应；宪章要求的测试先行、产物来源和设备验收分层保留。
- T061整体、Todoist任务3/4均不勾选，总清单2/4；无新PR。Todoist项目`6j294wJX64V7p54G`，分区`6j296fXM7c27Vg7p`，任务`6j295Q6WFFfJ74fG` / `6j295Q7jffjHC3qp`。
