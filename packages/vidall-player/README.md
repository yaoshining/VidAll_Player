# VidAll Player SDK

[中文文档](README-CN.md)

`@vidall/player` is a candidate ArkTS player HAR for HarmonyOS TV and phone apps. Its intended playback core is libmpv; it does not use HarmonyOS AVPlayer. `Index.ets` is the only public entry point; import only the APIs documented here.

## Candidate status

This package is not published to OHPM and is currently for VidAll_TV integration validation only. The current HAR includes only the internal NAPI packaging probe, not a libmpv playback bridge or a bundled libmpv runtime. Do not treat a successful build as actual media playback support.

The public API remains limited to the contract documented here. Additional libmpv capabilities are introduced only after they have been implemented and validated in VidAll_TV; undocumented mpv commands, properties, scripts, filters, recording, stream capture, and screenshots are not public APIs.

## Install

When a validated release is available, from the application project root run:

```sh
ohpm install @vidall/player
```

Declare the dependency in the application's `oh-package.json5`:

```json5
{
  "dependencies": {
    "@vidall/player": "0.1.0"
  }
}
```

Run `ohpm install` after editing dependencies, then build with DevEco Studio or `devecocli build`.

## Quick start

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

Release the instance when the page disappears or the Surface is rebuilt:

```ts
await player.detachSurface(surface.generation);
await player.release();
```

Use a new `generation` with `resizeSurface()` when the Surface size changes. A released instance cannot be reused; call `createPlayer()` again.

## API overview

- `createPlayer(options?)` creates a player. `eventListener` receives state, first-frame, position, track, subtitle, log, and error events.
- `attachSurface`, `resizeSurface`, and `detachSurface` manage the rendering Surface lifecycle.
- `load`, `play`, `pause`, `stop`, `seekRelative`, and `seekPercent` control playback.
- `setVolume`, `mute`, `setRate`, and `selectTrack` configure playback and tracks.
- `addExternalAudio`, `addExternalSubtitle`, and `setSubtitleDelay` add external media and adjust subtitle timing.
- `subscribe(listener)` registers another event listener and returns its unsubscribe function.
- `release()` frees native and playback resources and must be called before the page exits.

## Inputs and limitations

`MediaSource.kind` accepts `localFile`, `http`, `https`, `hls`, `dash`, `localhostProxy`, and `smb`. HTTP(S) headers are supported, but credentials must not be placed in URIs or logs. SMB, cache requests, crop, deinterlacing, and screenshots are not stable supported features and can return structured errors.

Do not import `src/internal`, NAPI, NativeWindow, EGL/GLES, or libmpv paths. They are not part of the compatibility contract.

## Compatibility and license

The HAR declares `phone` and `tv`, with HarmonyOS API 15 compatibility and API 22 as its target. Verify media behavior on actual target devices; a successful build does not prove codec, protocol, or hardware-decoding support.

The intended libmpv distribution includes GPL components, including the static Samba SMB path. This package is therefore licensed under the [GNU General Public License v3.0 or later](LICENSE). See [CHANGELOG.md](CHANGELOG.md) for release history and `docs/controlled-libmpv-release.md` for distribution obligations.
