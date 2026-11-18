# Spec 019 · 任务及验收

Todoist 分区 `6j3HqXPM9JrHWWmp`。验收入口见 [Player #95](https://github.com/yaoshining/VidAll_Player/issues/95)。

- [x] T001 定位 90° 首帧断言并建立失败回归。Todoist `6j3Hqg3CmPmj5Mmp`。
- [x] T002 修复 MPV 渲染并完成本地回归，验证锁定构建输入和 ARM64 核心。Todoist `6j3Hqg3rqhfJQJWp`。
- [ ] T003 发布修复分支 PR，验收 iMac CI ARM64 HAR。Todoist `6j3Hqg36XRXwxrhp`。
- [ ] T004 TV #372 原样接入 HAR 并完成 0°、90°、180° 模拟器复验。Todoist `6j3Hqg4rHMx3PrFG`。

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
