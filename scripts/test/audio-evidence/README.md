# 系统内录音频证据检查

此工具检查设备**实际系统内录**中的已知测试音，不读取播放器输入 PCM，也不以 RUNNING、解码成功或首帧代替音频输出。

```sh
python3 -B scripts/test/audio-evidence/run.py --out /tmp/audio-evidence-host
ffmpeg -i capture.mp4 -map 0:a:0 -c:a pcm_s16le capture.wav
python3 scripts/test/audio-evidence/analyze.py capture.wav segments.json --out signal.json
```

Node 回归默认使用 DevEco Studio 自带 TypeScript；其他环境设置 `TYPESCRIPT_PATH`。音轨不存在时提取必须失败，不能补静音轨。`segments.json` 为数组，例如：

```json
[{"name":"故障后新视频","start":12.5,"end":17.5,"toneHz":440,"forbiddenHz":880},
 {"name":"关闭后静音","start":20.5,"end":22.5,"toneHz":null}]
```

时间以录制音轨为准，结合设备事件和视频画面校准；不得挑选零散成功窗口。有效区间至少一秒。测试音每200ms检测一次，需超过 -45 dBFS，有效时间占比至少95%，连续失败不得超过300ms；新旧音混播直接失败。静音区间每10ms检测RMS，采用 -55 dBFS 阈值及相同覆盖率/连续失败门槛，避免把短音尾放大为200ms失败。分辨率不是准许裁剪的窗口；完整区间和旧结果必须保留。

输出 `signalPassed` 仅是指定区间的信号检查，`deviceAccepted` 固定为 false。另行核对包/九库哈希、设备/API、PID、真实 OHCodec/Vulkan、故障记录、事件时间与录制完整性。人工听声/自然音质与物理扬声器效果单列；合成音单测不是任何设备的验收。API24不能替代API19 TV。

## 崩溃与内录导出（T049）

普通/焦点独立页面在播放前订阅本应用 APP_CRASH；崩溃后手动重启，可收到系统事件并保存最新崩溃文件。订阅前的历史故障不保证有日志。单次运行最多读取4个不重复路径，每份至多512KiB并标注截断；只接受系统提供的本应用日志路径，不访问系统故障目录。页面退出注销观察者。

录制释放并关闭后，通过“导出内录”“导出事件”“导出崩溃”调用系统保存选择器。取消、缺失、写入失败不会显示成功；录制未关闭时禁止导出。重启后残留MP4可能不完整，必须实际解析音轨，文件存在不等于有效录音。导出到设备文件后仍需借助云平台实际支持的文件下载路径取回；此接口本身不承诺云平台具备下载能力。

系统保存选择器导出仅接入普通/焦点页面；T054的显式剪贴板分块导出已覆盖普通/焦点、关闭故障、全局故障三组。三组API24真实事件和内录均已完整取回并校验SHA256；此能力不读取系统剪贴板内容，只复制本应用固定证据文件。

## T057 音画同步

`prepare_sync.py --project <独立消费工程>`保留坏片、焦点、手动恢复及释放重开入口，将首段连续播放延长到90秒，seek到180秒素材的120秒。只生成验收页，不改HAR；录制400kbps视频加96kbps音频，仍受16MiB证据上限约束。素材中心白框与880Hz短音在1秒开始每2秒同步100ms，440Hz连续底音用于判断音频是否存在。

```sh
ffmpeg -f lavfi -i "color=c=black:s=640x360:r=30:d=180,drawbox=x=160:y=90:w=320:h=180:color=white:t=fill:enable='gte(t,1)*lt(mod(t-1,2),0.1)'" -f lavfi -i "aevalsrc=0.04*sin(2*PI*440*t)+0.3*sin(2*PI*880*t)*gte(t\,1)*lt(mod(t-1\,2)\,0.1):s=48000:d=180" -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart test_video.mp4
python3 -B scripts/test/audio-evidence/av_sync.py capture.mp4 windows.json --roi x,y,w,h --out sync.json
```

ROI必须依据实际录制画面位于闪光框内，避开覆盖按钮/文字。`windows.json`按完整事件定义连续段，格式为`[{"name":"连续播放","start":3,"end":90}]`，时间是原始录制PTS；不能挑选仅成功脉冲。工具保留轨道原始时间偏移，逐次比较全部闪光/短音；缺失、数目不一致、少于3个脉冲均失败。绝对偏差≤80ms、首尾中位偏差变化≤40ms仅为本实验门槛；30fps/10ms窗口有量化误差。系统内录不是物理扬声器/面板或人耳听感验收，90秒也不是无限长播保证。源素材先自测，合成错位/漂移负例必须拒绝，实际设备单独记账。


### 独立时间锚点

在已生成的普通同步/关闭隔离/全局故障独立工程运行 `prepare_anchor.py --project <工程> --kind normal|fence|global`，完整保留HAR。组件在Player播放前后输出独立2200Hz脉冲并读取API19音频帧时间戳；视觉码全程记录单调序号。全局模式保留实际返回/选片门槛，将第二/第三片观测各延长至10秒，不裁首片启动窗口。录制后运行 `time_anchor.py capture.mp4 events.jsonl --row <实际时间码行> --out anchor.json`。必须先从实际画面核对行位置；校准一致不等于物理同步或设备整体验收。

播放段末尾不足200ms时，频率测量窗口向前覆盖完整200ms，统计权重仍为末尾实际时长。串音须同时超过-55dBFS静音底线及-25dB相对功率门槛，低电平噪声不算旧音，但新声音不足仍失败。对应合成回归及首次设备结果见Spec017 T060；保留旧判定以便对照。

## T063 独立原始采集

`prepare_raw.py --project <独立消费者>`增加单次原始采集诊断，不修改HAR。API19起允许，使用API12已提供的原始回调；显式系统授权后只启用系统内录、关闭麦克风。目标为640×360 RGBA/BGRA，回调有效期内读取并采样160×90灰度和48kHz双声道PCM，保持逐缓冲区纳秒时间戳与回调抵达时间。最大64MiB/12000记录，失败不重建采集器；未知格式、容量异常终止采集。前后各12秒独立AudioRenderer时钟校准，中间30秒原素材播放。

导出`phase17-raw/capture.bin`及`events.jsonl`，先核对结束事件、PID、包/九库和实际解码路径。`raw_capture.py capture.bin events.jsonl --roi 60,35,40,20 --out strict.json`严格拒绝重复/倒退时间戳及断裂，不删除坏样本。`audit()`保留全部记录，按每块原始PTS提取校准脉冲，只报告与平台输出帧时钟的差值；`calibrationPulseStable`不等于`syncAccepted`，后者始终false。不能用回调抵达时刻替换媒体时间或拼接坏时间轴。

T063 TV观察到内录音频时间戳未来约240ms及重复时间戳。官方OpenHarmony固定提交`9f9a285ff489afa66861a85dcc4213336a463b36`的`audio_capturer_wrapper.cpp/.h`包含内录240ms补偿，与此线索吻合，但不证明商业TV固件与该源码相同。真实屏幕/扬声器仍需同钟外部采集；不把原始回调当真实上屏时间。
