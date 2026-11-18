# Spec 019 · 任务及验收

Todoist 分区 `6j3HqXPM9JrHWWmp`。验收入口见 [Player #95](https://github.com/yaoshining/VidAll_Player/issues/95)。

- [x] T001 定位 90° 首帧断言并建立失败回归。Todoist `6j3Hqg3CmPmj5Mmp`。
- [x] T002 修复 MPV 渲染并完成本地回归，验证锁定构建输入和 ARM64 核心。Todoist `6j3Hqg3rqhfJQJWp`。
- [x] T003 发布修复分支 PR，验收 iMac CI ARM64 HAR。Todoist `6j3Hqg36XRXwxrhp`。
- [x] T004 TV #372 原样接入 HAR 并完成 0°、90°、180° 模拟器复验。Todoist `6j3Hqg4rHMx3PrFG`。
- [x] T005 修复启动帧回归测试的两条漏检路径。旧测试误通过仅首帧为黑的样片。新测试四角度通过，黑色首帧在恢复播放前失败。Todoist `6j3MJHGpPQ86m64G`。
- [x] T006 补录 API 19 首帧帧序号与两个 CI HAR 的逐文件比较。Todoist `6j3MJHJwHqX3mRGp`。
- T007 的审查答复和检查结果在 [PR #96](https://github.com/yaoshining/VidAll_Player/pull/96) 跟踪。Todoist `6j3MJHMmwv9XG6Hp`。

## 宿主回归

实际编译上游锁定提交 `6edeee00a07b9b76f197aa71eee3d029fb090de4`，调用 `MPV_RENDER_API_TYPE_SW`。同一 H.264 像素流保留不同的 MP4 显示矩阵。测试核对象限颜色、竖屏边界、后续亮块和缺失渲染目标时的错误返回。

| 显示矩阵 | 原核心 | 本轮补丁 |
| --- | --- | --- |
| 0° | 首帧方向正确，后续出画 | 通过 |
| 90° | `mp_image_crop` 越界断言，退出码 134 | 通过 |
| 180° | 首帧出画，方向错误 | 通过 |
| 270° | 同一断言，退出码 134 | 通过 |

## ARM64 核心预验证

- 沿用事故 HAR 对应的封存依赖，仅增加本轮 mpv 补丁。派生构建输入 SHA-256 为 `65ccf932738ab8630e93b1a5076d863b28394f3a4b5e71911149b83183fdc366`。
- 使用 DevEco OHOS SDK 按正常生产配置交叉编译。新 `libmpv.so` SHA-256 为 `4e35bcc57b47745e7b94b8912b6ba2cbde50cb055c6a38afb38c3ca6e3e67ee2`。
- 生产来源、ABI 与包装输入审计均通过。归档的六个 FFmpeg 运行库、`libc++_shared.so` 及静态 libplacebo 哈希与基线一致。

## CI HAR 和消费端复验

- `00e5a080b9a4afb5c5395352c78a56cd7d4785c6` 由 [iMac GitHub Actions 44306605463](https://github.com/yaoshining/VidAll_Player/actions/runs/44306605463) 构建。实际执行器为 `yaoshiningdeiMac` 自托管 macOS X64，独立消费者和 Hypium 套件编译通过。[产物与九库哈希](ci-har.json)
- 原 HAR SHA-256 为 `07d9807602727d73a96c64ec84ad51b8b646260e4c7e4d97f9c19d84c582c816`。TV #372 测试副本原样接入，刷新 ohpm 本地依赖缓存后逐库比对签名 HAP。
- 原 25 秒样片记录了 `onReady` 事件。点击返回后约 2.2、7 秒的截图显示 0°、90°、180° 方向正确并持续出画，约 10 秒后仍为 PID `13214`。截图未与首个帧绑定。[模拟器结果](api19-tv.json)
- 11 月 19 日使用同一 HAR、签名 HAP 和 WebDAV 正式入口补测。首帧独有的白块及象限颜色确认 0°、90°、180° 的帧 0 方向正确，后续帧白块消失。三次均为 MPV standard 软件路径，同一 PID `2365` 存活。[首帧截图，左至右为 0°、90°、180°](api19-first-frame.png)
- [分支 iMac CI 44309543487](https://github.com/yaoshining/VidAll_Player/actions/runs/44309543487) 使用提交 `6476cdf73aaf82d86830787c1e7d8bc09aa65ded`，产物 ID `14429897519`。两个 HAR 原件 SHA-256 各自独立。逐路径比对解包后的 37 个普通文件，SHA-256 全部一致。[比较证据](har-comparison.json)
- 这组验收覆盖模拟器软件路径。实体 TV 硬解与正式发布仍需对应环境的独立验收。
