# 播放诊断快照 API（Issue #79）

`@vidall/player` 0.1.0 未发布候选新增 `VidAllPlayer.getDiagnostics(): Promise<PlayerDiagnosticsSnapshot>`。公开类型从包根导入，消费端无需引用 NAPI。版本号保持 0.1.0，schemaVersion 为 1；本变更没有更换 libmpv 或修改播放/渲染策略。

```typescript
import { VidAllPlayer, PlayerDiagnosticsSnapshot } from '@vidall/player';

async function readDiagnostics(player: VidAllPlayer): Promise<string> {
  const snapshot: PlayerDiagnosticsSnapshot = await player.getDiagnostics();
  // 包含收起的字段及缺失原因；不要拼接原始 MediaSource、URL、headers。
  return JSON.stringify(snapshot, null, 2);
}
```

面板打开后建议每次 await 完成，再等待约 1000 ms 采样。关闭面板即取消消费端计时器，并使待返回结果失效。SDK 自身没有定时器、观察属性注册或每帧快照事件；没有调用就没有额外采样。并发调用合并为同一 Promise，单会话最多一次读取。不要使用不等待结果的 setInterval 堆积请求。

采样通过 NAPI async work 在工作线程读取，与播放命令串行；release 会等待正在持有生命周期锁的这一次读取结束。`collectionDurationMs` 是原生采集耗时（不包含队列等待）。属性按顺序读取，**不是同一媒体帧的原子快照**。跨字段不应推导毫秒级精确同步关系。

每个字段含 `status`、`unit`、`source`、`estimated`，仅 `available` 才含 `value`。有效 0 / false 保留；`unavailable` 表示当前阶段没有值或隐私隐去，`unsupported` 表示锁定版本不提供属性，`error` 表示读取、类型或数值校验失败。失败不触发播放器 error 事件。

字节数、输入字节速度及累计丢帧计数使用**非负十进制字符串**，完整保留 mpv int64 精度；需要参与 JS 运算时必须自行检查安全范围。其他数值为 number，秒统一乘 1000 转毫秒，拒绝非有限值及超出安全范围的数值。不输出 NaN、Infinity 或格式化展示字符串。

快照附带 Unix 时间 `sampledAtMs`、会话标识 `sessionId`、媒体代际 `mediaGeneration`、表面代际 `surfaceGeneration`、SDK 版本和运行时 `mpvVersion`。会话标识只用于日志关联，不是指针或可操作的公开 native handle。切源、stop、release、attach/resize/detach 在调用时使在途结果过期，Promise 拒绝 `DIAGNOSTICS_STALE`；release 后拒绝 `DIAGNOSTICS_RELEASED`。排队时已释放也可能返回既有队列的 RELEASED 生命周期错误。消费端应丢弃过期结果，切换完成后重新采样。未加载、加载中或结束后的媒体字段为 `unavailable`，停止命令成功后立即屏蔽旧媒体值。

## 字段口径与来源

来源锁：`native/config/sources.lock.json` 中 mpv `feat-ohos-0.41.0`，提交 `6edeee00a07b9b76f197aa71eee3d029fb090de4`。已核对该提交的 [input.rst](https://github.com/ErBWs/mpv/blob/6edeee00a07b9b76f197aa71eee3d029fb090de4/DOCS/man/input.rst) 和 [command.c](https://github.com/ErBWs/mpv/blob/6edeee00a07b9b76f197aa71eee3d029fb090de4/player/command.c)。实际设备返回的版本另外写入快照，不能把来源锁当成设备验证。

- 视频 `videoInput*` 来自无覆盖的解码参数；`video*` 与现有 VideoParams 的 mpv video-params 来源一致；`videoOutput*` 为滤镜后数据，不是屏幕最终扫描输出。没有复用事件缓存，避免轨道切换时旧值残留；原有序列化事件保持不变。
- `audioInput*` 与现有 AudioParams 同源，指音频解码器输出；`audioOutput*` 是写给音频 API 的数据，不承诺 HDMI/功放最终格式。
- 编码器与解码器从当前选中轨道读取，与 PlayerTrack 的 track-list 数据同源。无相应轨道即不可用。
- `mediaFps` 是容器声明帧率估算，不是实际呈现帧率。音视频 bitrate 是两关键帧间包级估算，不是文件平均码率，也不是网络速度。
- `hardwareDecoder` 是 hwdec-current 实际报告（no 表示软件解码），不是 hwdec 配置意图。`renderBackend` 复用 #77 的实际后端选择和 SW 降级判定。
- `avSyncMs` 是瞬时音画偏差；`totalAvSyncCorrectionMs` 是累计同步修正量，不叫“实时漂移”。两种丢帧计数分别保留，未启用相应策略时 0 不代表策略能力已经验证。
- `cacheForwardBytes` 是前向包缓存估算；`cacheTotalBytes` 为全包队列含可 seek 范围及开销的估算；`cacheDiskBytes` 包含磁盘缓存开销及可能未使用数据。不可相加当总内存。关闭缓存、直播、无音/视频轨道或文件未知大小/时长时保留属性返回的不可用状态。
- `surfaceWidth/Height` 来自当前表面状态，单位 px，来源 `session.surface`；无表面即不可用。与媒体分辨率无关。
- `filename/mediaTitle` 固定隐去为 unavailable/redacted（有媒体时）；任意字符串可能含嵌入的私有 URL、令牌或认证信息，SDK 不承诺自动识别所有秘密。App 可另行附加已脱敏展示名称与原始协议。SDK 不读取路径、鉴权头或来源 URL，不会把代理 HTTP 当原始协议。
- **位深限制**：锁定版本没有 `plane-depth` 属性。三组 BitDepth 固定 `unsupported/absent-in-locked-version`，不复用既有 VideoParams 的像素格式尾数推断（该推断对硬解格式或带 le 后缀格式不可靠），也不以 average-bpp 冒充位深。保留像素格式供分析。

下面 Number 接受 mpv DOUBLE/INT64（安全范围内），IntegerString 只接受 INT64，Text 只接受 STRING，Flag 只接受 FLAG。技术名称仅允许受控字符，异常字符串隐去；未知类型不强制转字符串或数字。BitDepth 的候选属性已确认不支持，Redacted 字段不读取底层值。

| 字段 | mpv 属性 | 类型 | 单位 | 估算 |
|---|---|---|---|---|
| `filename` | `filename` | Redacted | text | 否 |
| `mediaTitle` | `media-title` | Redacted | text | 否 |
| `fileSizeBytes` | `file-size` | IntegerString | byte | 否 |
| `containerFormat` | `file-format` | Text | text | 否 |
| `videoCodec` | `current-tracks/video/codec` | Text | text | 否 |
| `videoDecoder` | `current-tracks/video/decoder` | Text | text | 否 |
| `videoBitrate` | `video-bitrate` | Number | bit/s | 是 |
| `audioCodec` | `current-tracks/audio/codec` | Text | text | 否 |
| `audioDecoder` | `current-tracks/audio/decoder` | Text | text | 否 |
| `audioBitrate` | `audio-bitrate` | Number | bit/s | 是 |
| `mediaFps` | `container-fps` | Number | frame/s | 是 |
| `videoInputWidth` | `video-dec-params/w` | Number | px | 否 |
| `videoInputHeight` | `video-dec-params/h` | Number | px | 否 |
| `videoInputPixelFormat` | `video-dec-params/pixelformat` | Text | text | 否 |
| `videoInputBitDepth` | `video-dec-params/plane-depth` | Number | bit | 否 |
| `videoInputColorMatrix` | `video-dec-params/colormatrix` | Text | text | 否 |
| `videoInputColorPrimaries` | `video-dec-params/primaries` | Text | text | 否 |
| `videoInputColorTransfer` | `video-dec-params/gamma` | Text | text | 否 |
| `videoInputColorRange` | `video-dec-params/colorlevels` | Text | text | 否 |
| `videoWidth` | `video-params/w` | Number | px | 否 |
| `videoHeight` | `video-params/h` | Number | px | 否 |
| `videoPixelFormat` | `video-params/pixelformat` | Text | text | 否 |
| `videoBitDepth` | `video-params/plane-depth` | Number | bit | 否 |
| `videoColorMatrix` | `video-params/colormatrix` | Text | text | 否 |
| `videoColorPrimaries` | `video-params/primaries` | Text | text | 否 |
| `videoColorTransfer` | `video-params/gamma` | Text | text | 否 |
| `videoColorRange` | `video-params/colorlevels` | Text | text | 否 |
| `videoOutputWidth` | `video-out-params/w` | Number | px | 否 |
| `videoOutputHeight` | `video-out-params/h` | Number | px | 否 |
| `videoOutputPixelFormat` | `video-out-params/pixelformat` | Text | text | 否 |
| `videoOutputBitDepth` | `video-out-params/plane-depth` | Number | bit | 否 |
| `videoOutputColorMatrix` | `video-out-params/colormatrix` | Text | text | 否 |
| `videoOutputColorPrimaries` | `video-out-params/primaries` | Text | text | 否 |
| `videoOutputColorTransfer` | `video-out-params/gamma` | Text | text | 否 |
| `videoOutputColorRange` | `video-out-params/colorlevels` | Text | text | 否 |
| `hardwareDecoder` | `hwdec-current` | Text | text | 否 |
| `videoOutputBackend` | `current-vo` | Text | text | 否 |
| `audioOutputBackend` | `current-ao` | Text | text | 否 |
| `audioInputSampleRate` | `audio-params/samplerate` | Number | Hz | 否 |
| `audioInputSampleFormat` | `audio-params/format` | Text | text | 否 |
| `audioInputChannels` | `audio-params/channel-count` | Number | count | 否 |
| `audioInputChannelLayout` | `audio-params/channels` | Text | text | 否 |
| `audioOutputSampleRate` | `audio-out-params/samplerate` | Number | Hz | 否 |
| `audioOutputSampleFormat` | `audio-out-params/format` | Text | text | 否 |
| `audioOutputChannels` | `audio-out-params/channel-count` | Number | count | 否 |
| `audioOutputChannelLayout` | `audio-out-params/channels` | Text | text | 否 |
| `decoderDroppedFrames` | `decoder-frame-drop-count` | IntegerString | frame | 否 |
| `outputDroppedFrames` | `frame-drop-count` | IntegerString | frame | 否 |
| `positionMs` | `time-pos` | Number | ms | 否 |
| `durationMs` | `duration` | Number | ms | 否 |
| `avSyncMs` | `avsync` | Number | ms | 否 |
| `totalAvSyncCorrectionMs` | `total-avsync-change` | Number | ms | 否 |
| `progressPercent` | `percent-pos` | Number | percent | 否 |
| `paused` | `pause` | Flag | boolean | 否 |
| `buffering` | `paused-for-cache` | Flag | boolean | 否 |
| `rate` | `speed` | Number | ratio | 否 |
| `volumePercent` | `volume` | Number | percent | 否 |
| `muted` | `mute` | Flag | boolean | 否 |
| `syncMode` | `video-sync` | Text | text | 否 |
| `cacheDurationMs` | `demuxer-cache-duration` | Number | ms | 是 |
| `cacheForwardBytes` | `demuxer-cache-state/fw-bytes` | IntegerString | byte | 是 |
| `cacheTotalBytes` | `demuxer-cache-state/total-bytes` | IntegerString | byte | 是 |
| `cacheDiskBytes` | `demuxer-cache-state/file-cache-bytes` | IntegerString | byte | 否 |
| `inputBytesPerSecond` | `cache-speed` | IntegerString | byte/s | 是 |

另外 `renderBackend: DiagnosticField<string>` 来源为 `session.actual-render-backend`；`surfaceWidth/Height: DiagnosticField<number>` 来源为 `session.surface`。`mpvVersion` 来源 `mpv-version`，STRING，text。

## 验证边界

自动化覆盖转换、单位、大整数、缺失/错误、并发合并、切源/表面/stop/release 过期及失败不影响播放状态。HAR 编译覆盖 arm64-v8a 的实际 mpv 桥接和 x86_64 probe 路径；后者仍不具备播放能力。测试命令：

```sh
cmake -S native/tests -B /tmp/vidall-native-tests
cmake --build /tmp/vidall-native-tests -j 4
ctest --test-dir /tmp/vidall-native-tests --output-on-failure
node native/tests/diagnostics-session.test.cjs
devecocli build --modules vidall_player@default
```

主机 ETS 测试使用 DevEco 自带 TypeScript 编译器，其他环境可通过 TYPESCRIPT_PATH 指定模块位置。

当前 TV 正由消费端界面任务占用，**尚未完成**本地/网络资源的真实快照、轨道切换、暂停恢复、seek、快速切源退出、采样开关性能、硬解/Vulkan/DV/降级路径验收。不得把单元测试或 HAR 构建当作这些项目通过的证据。产物用于后续集成验收，PR 保持草稿，Issue 保持打开。
