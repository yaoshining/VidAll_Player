# VidAll Player SDK

[中文文档](README-CN.md)

`@vidall/player` is a candidate ArkTS HAR for HarmonyOS. Its only playback core is libmpv; it does not use HarmonyOS `AVPlayer`. `Index.ets` is the sole public entry point.

## Candidate status

The package is not published to OHPM. It is used only by this repository's independent fixture for development validation and neither modifies nor depends on VidAll_TV. The HAR contains an internal NAPI bridge and an ARM64 libmpv candidate artifact, but G1 (device/sample), G2 (supply chain), and G3 (Surface/threading) remain open. A build, emulator installation, session creation, or XComponent attach/detach does not prove media playback, first frame, TV support, or release readiness.

## Local fixture

There is no OHPM installation, upload, or public release path. Build the local HAR, fixture, and test module from the repository root:

```sh
devecocli build --modules vidall_player libmpv_player_consumer libmpv_player_consumer@ohosTest
```

The fixture imports only from `@vidall/player`. Do not import `src/internal`, NAPI, NativeWindow, EGL/GLES, or libmpv paths; they are not compatibility commitments.

## Development interfaces

`createPlayer()`, Surface lifecycle calls, `load()`, `play()`, `stop()`, and `release()` are candidate interfaces. A successful call, lifecycle event, or emulator log only demonstrates execution of the controlled bridge path; it is not playback or first-frame evidence. Call `release()` when a page is destroyed; released instances cannot be reused.

Unapproved capabilities return typed errors. For example, `requestCache()` returns `FEATURE_UNSUPPORTED`, `load()` without a valid Surface returns `SURFACE_UNAVAILABLE`, and controls after release return `RELEASED`. Public errors are redacted and must not be relied on for full URIs, native handles, or load paths.

## Capability status and gates

Capabilities may only be described as `built pending verification`, `verified on real-device samples`, or `unsupported/deferred`. This candidate is `built pending verification`.

The ARM64 TV emulator is only for build, installation, public-import, NAPI-load, and lifecycle regression work. It cannot close G1 (target ARM64 TV/API and media sample rules), G2 (libmpv source, GPL materials, loading boundary, ABI/ELF, and candidate admission), or G3 (XComponent/Surface, NativeWindow, threads, input, and actual first frame).

Until real-device evidence and written G1/G2/G3 approval exist for the same `candidateId`, do not deliver the HAR, upload to OHPM, publish publicly, or claim playback, first-frame, TV support, or ijkplayer replacement.

中文说明：当前仅能用于本仓库 fixture 的开发期验证；模拟器和构建成功均不能作为播放、首帧、TV 支持或发布依据。

## License

The candidate libmpv distribution contains GPL components and the SMB path involves Samba. Any future controlled distribution must comply with the [GNU General Public License v3.0 or later](LICENSE) and the materials and approvals in `docs/controlled-libmpv-release.md`; the current status is not distribution authorization.
