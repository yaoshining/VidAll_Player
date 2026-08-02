# VidAll Player SDK

`@vidall/player` 是面向 HarmonyOS TV 和手机应用的 ArkTS 播放器候选 HAR。播放器的目标内核是 libmpv，不使用 HarmonyOS AVPlayer。包的唯一公开入口是 `Index.ets`；只应导入本文列出的 API。

## 候选状态

该包尚未发布到 OHPM，当前仅用于 VidAll_TV 集成验证。现有 HAR 仅包含内部 NAPI 打包探针，尚未包含 libmpv 播放桥接或可分发的 libmpv 运行时；构建成功不能视为真实媒体播放已支持。

公开 API 暂严格限定为本文所列契约。其余 libmpv 能力须先在 VidAll_TV 完成实现和验证后再按需加入；未在本文声明的 mpv 命令、属性、脚本、滤镜、录制、流捕获和截图均不是公开 API。

## 安装

验证后的版本可在应用工程根目录执行：

```sh
ohpm install @vidall/player
```

然后在应用模块的 `oh-package.json5` 中声明依赖：

```json5
{
  "dependencies": {
    "@vidall/player": "0.1.0"
  }
}
```

安装后执行 `ohpm install`，再使用 DevEco Studio 或 `devecocli build` 构建应用。

## 快速开始

```ts
import {
  createPlayer,
  MediaSource,
  PlayerEvent,
  PlayerSurface,
  VidAllPlayer
} from '@vidall/player';

const player: VidAllPlayer = createPlayer({
  eventListener: (event: PlayerEvent) => {
    if (event.type === 'error') {
      console.error(`${event.error?.code}: ${event.error?.message}`);
    }
  }
});

const surface: PlayerSurface = {
  componentId: 'video-surface',
  generation: 1,
  width: 1920,
  height: 1080
};
const source: MediaSource = {
  kind: 'https',
  uri: 'https://example.com/video.m3u8'
};

await player.attachSurface(surface);
await player.load(source);
await player.play();
```

页面销毁或 Surface 重建时必须释放播放器：

```ts
await player.detachSurface(surface.generation);
await player.release();
```

Surface 尺寸变化时，使用新的 `generation` 调用 `resizeSurface()`；释放后的实例不可复用，应重新调用 `createPlayer()`。

## API 概览

- `createPlayer(options?)`：创建播放器实例；可通过 `eventListener` 接收状态、首帧、进度、音轨、字幕、日志和错误事件。
- `attachSurface`、`resizeSurface`、`detachSurface`：管理渲染 Surface 生命周期。
- `load`、`play`、`pause`、`stop`、`seekRelative`、`seekPercent`：管理媒体播放。
- `setVolume`、`mute`、`setRate`、`selectTrack`：设置播放参数和轨道。
- `addExternalAudio`、`addExternalSubtitle`、`setSubtitleDelay`：添加外部音频、字幕并调整字幕延迟。
- `subscribe(listener)`：订阅事件；返回的函数用于取消订阅。
- `release()`：释放原生和播放资源；页面退出前必须调用。

## 输入与限制

`MediaSource.kind` 支持 `localFile`、`http`、`https`、`hls`、`dash`、`localhostProxy` 和 `smb`。HTTP(S) 可使用 `headers`，但不要在 URI 或日志中写入凭据。当前 `smb`、缓存请求、裁剪、去隔行与截图不属于稳定支持能力，调用时可能返回结构化错误。

仅导入 `@vidall/player`；不要导入 `src/internal`、NAPI、NativeWindow、EGL/GLES 或 libmpv 相关路径，它们不属于兼容性承诺的一部分。

## 兼容性与许可

HAR 声明支持 `phone` 和 `tv`，兼容 HarmonyOS API 15，目标 API 22。媒体能力需要在目标设备验证；构建通过不代表特定编码、协议或硬件解码器已得到支持。

目标 libmpv 分发物包含 GPL 组件，其中 SMB 路径静态链接 Samba。因此，本包采用 [GNU General Public License v3.0 or later](LICENSE)。分发义务见 `docs/controlled-libmpv-release.md`，版本记录见 [CHANGELOG.md](CHANGELOG.md)。
