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

时间以录制音轨为准，结合设备事件和视频画面校准；不得挑选零散成功窗口。有效区间至少一秒。每200ms检测一次：测试音需超过 -45 dBFS，有效时间占比至少95%，连续失败不得超过300ms；新旧音混播直接失败。静音区间采用 -55 dBFS 阈值。

输出 `signalPassed` 仅是指定区间的信号检查，`deviceAccepted` 固定为 false。另行核对包/九库哈希、设备/API、PID、真实 OHCodec/Vulkan、故障记录、事件时间与录制完整性。人工听声/自然音质与物理扬声器效果单列；合成音单测不是任何设备的验收。API24不能替代API19 TV。

## 崩溃与内录导出（T049）

普通/焦点独立页面在播放前订阅本应用 APP_CRASH；崩溃后手动重启，可收到系统事件并保存最新崩溃文件。订阅前的历史故障不保证有日志。单次运行最多读取4个不重复路径，每份至多512KiB并标注截断；只接受系统提供的本应用日志路径，不访问系统故障目录。页面退出注销观察者。

录制释放并关闭后，通过“导出内录”“导出事件”“导出崩溃”调用系统保存选择器。取消、缺失、写入失败不会显示成功；录制未关闭时禁止导出。重启后残留MP4可能不完整，必须实际解析音轨，文件存在不等于有效录音。导出到设备文件后仍需借助云平台实际支持的文件下载路径取回；此接口本身不承诺云平台具备下载能力。

系统保存选择器导出仅接入普通/焦点页面；T054的显式剪贴板分块导出已覆盖普通/焦点、关闭故障、全局故障三组。三组API24真实事件和内录均已完整取回并校验SHA256；此能力不读取系统剪贴板内容，只复制本应用固定证据文件。
