import libentry, { BufferingState, LibMpvTrack, NativePlayerEvent } from 'libentry.so';
import { fileIo as fs } from '@kit.CoreFileKit';
import { image } from '@kit.ImageKit';
import { detectMediaKind, newProxyLeaseId } from '../player/MediaKindDetection';
import { splitTracks, trackLabel } from '../player/TrackPresentation';
import { buildBasicAuthorization, WebDavConfig, WebDavEntry, WebDavService } from '../webdav/WebDavService';

interface FrameData {
  width: number;
  height: number;
  data: ArrayBuffer;
}

@Entry
@Component
struct Index {
  private readonly surfaceController: XComponentController = new XComponentController();
  @State nativeStatus: string = '正在检查 libmpv 原生模块...';
  @State runtimeInfo: string = '';
  @State url: string = '';
  @State subtitleUrl: string = '';
  @State externalAudioUrl: string = '';
  @State currentMediaKind: string = '';
  @State currentProxyLeaseId: string = '';
  @State bufferingInfo: string = '';
  @State playerHandle: number = 0;
  @State surfaceId: string = '';
  @State isPlaying: boolean = false;
  @State videoPixelMap: image.PixelMap | null = null;
  @State showVideo: boolean = false;
  private pixelMapBuffers: image.PixelMap[] = [];
  private pixelMapBufferIndex: number = 0;
  private pixelMapWidth: number = 0;
  private pixelMapHeight: number = 0;
  @State webDavEndpoint: string = 'http://192.168.3.59:5005';
  @State webDavUsername: string = '';
  @State webDavPassword: string = '';
  @State webDavEntries: WebDavEntry[] = [];
  @State webDavDirectory: string = '';
  @State isWebDavLoading: boolean = false;
  @State isWebDavSource: boolean = false;
  @State audioTracks: LibMpvTrack[] = [];
  @State subtitleTracks: LibMpvTrack[] = [];
  private webDavBrowseGeneration: number = 0;
  private framePollTimer: number = -1;

  aboutToAppear(): void {
    const buildInfo = libentry.getBuildInfo();
    this.runtimeInfo = `ABI: ${buildInfo.abi} | libmpv: ${buildInfo.mpvVersion}`;
    this.nativeStatus = buildInfo.available
      ? 'ARM64 libmpv 已打包。等待 XComponent Surface 创建...'
      : '当前为 x86_64 模拟器：ARM64 libmpv 未打包，不能播放。';
    console.info(`VidAll_Player native: ${this.runtimeInfo}; ${this.nativeStatus}`);
    this.loadSavedWebDavConfig();
    this.prepareLocalVideo().then(() => {
      console.info(`VidAll_Player: prepareLocalVideo done`);
      this.tryAutoPlay();
    }).catch((e: Error) => {
      console.error(`VidAll_Player: prepareLocalVideo failed: ${e}`);
    });
  }

  aboutToDisappear(): void {
    this.releasePlayer();
    if (this.framePollTimer >= 0) {
      clearInterval(this.framePollTimer);
      this.framePollTimer = -1;
    }
  }

  private async prepareLocalVideo(): Promise<void> {
    try {
      const context = getContext(this);
      const cacheDir = context.cacheDir;
      const destPath = `${cacheDir}/test_video.mp4`;
      try {
        const stat = fs.statSync(destPath);
        if (stat.size > 0) {
          console.info(`VidAll_Player: test video already at ${destPath} (${stat.size} bytes)`);
          this.url = destPath;
          return;
        }
      } catch (e) {
        // File doesn't exist, copy it
      }
      const rawFile = context.resourceManager.getRawFileContentSync('test_video.mp4');
      const file = fs.openSync(destPath, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE);
      fs.writeSync(file.fd, rawFile.buffer);
      fs.closeSync(file);
      this.url = destPath;
      console.info(`VidAll_Player: copied test video to ${destPath} (${rawFile.byteLength} bytes)`);
    } catch (e) {
      console.error(`VidAll_Player: failed to prepare local video: ${e}`);
      this.nativeStatus = `准备本地视频失败: ${e}`;
    }
  }

  private getWebDavConfig(): WebDavConfig {
    return {
      endpoint: this.webDavEndpoint.trim(),
      username: this.webDavUsername.trim(),
      password: this.webDavPassword
    };
  }

  private async loadSavedWebDavConfig(): Promise<void> {
    try {
      const saved = await new WebDavService(getContext(this)).loadSavedConfig();
      // 仅在已保存配置非空时覆盖默认值，避免空配置清空占位
      if (saved.endpoint.length > 0) {
        this.webDavEndpoint = saved.endpoint;
      }
      if (saved.username.length > 0) {
        this.webDavUsername = saved.username;
      }
    } catch (_) {
      this.nativeStatus = '无法读取已保存的 WebDAV 配置。';
    }
  }

  private async browseWebDav(directoryUrl?: string): Promise<void> {
    const config = this.getWebDavConfig();
    const generation = ++this.webDavBrowseGeneration;
    this.isWebDavLoading = true;
    try {
      await new WebDavService(getContext(this)).saveConfig(config);
      const entries = await new WebDavService(getContext(this)).listDirectory(config, directoryUrl);
      if (generation !== this.webDavBrowseGeneration) {
        return;
      }
      this.webDavEntries = entries;
      this.webDavDirectory = directoryUrl ?? config.endpoint;
      this.nativeStatus = `已列出 ${entries.length} 个 WebDAV 项目。`;
    } catch (error) {
      if (generation === this.webDavBrowseGeneration) {
        const message = error instanceof Error ? error.message : (typeof error === 'string' ? error : JSON.stringify(error));
        this.nativeStatus = message || '列出 WebDAV 目录失败。';
        console.error(`VidAll_Player WebDAV browse error: ${message}`);
      }
    } finally {
      if (generation === this.webDavBrowseGeneration) {
        this.isWebDavLoading = false;
      }
    }
  }

  private openWebDavEntry(entry: WebDavEntry): void {
    if (this.isWebDavLoading) {
      return;
    }
    if (entry.isDirectory) {
      this.browseWebDav(entry.url);
      return;
    }
    this.url = entry.url;
    this.isWebDavSource = true;
    this.loadVideo();
  }

  private tryAutoPlay(): void {
    if (this.playerHandle <= 0 || this.url.length === 0 || this.surfaceId.length === 0) {
      return;
    }
    console.info(`VidAll_Player: auto-playing, surfaceId = ${this.surfaceId}`);
    this.nativeStatus = libentry.attachSurface(this.playerHandle, this.surfaceId);
    console.info(`VidAll_Player: attachSurface status = ${this.nativeStatus}`);
    this.submitLoad();
    console.info(`VidAll_Player: load submitted`);
    this.isPlaying = true;
    this.refreshTracksWhenReady();
    // 启动帧轮询，供 PixelMap 回退渲染使用。
    this.startFramePoll();
  }

  // 统一的媒体提交入口（US4）：按 URL 识别 hls/dash/localhostProxy/http/https，
  // SMB localhost 代理生成租约 ID 交给原生层关联，凭据仍只走 Authorization 头。
  private submitLoad(): void {
    const targetUrl = this.url.trim();
    if (targetUrl.length === 0) {
      this.nativeStatus = '请先输入或选择媒体地址。';
      return;
    }
    const kind = detectMediaKind(targetUrl);
    const authorization = this.isWebDavSource
      ? `Authorization: ${buildBasicAuthorization(this.webDavUsername, this.webDavPassword)}`
      : '';
    const proxyLeaseId = kind === 'localhostProxy' ? newProxyLeaseId() : '';
    this.currentMediaKind = kind;
    this.currentProxyLeaseId = proxyLeaseId;
    this.nativeStatus = libentry.loadMedia(this.playerHandle, kind, targetUrl, authorization, proxyLeaseId);
    // 如果填写了外挂字幕/音频 URL，加载视频后立即附加（支持网络 URL）。
    if (this.subtitleUrl.trim().length > 0) {
      this.nativeStatus = libentry.addExternalSubtitle(this.playerHandle, this.subtitleUrl.trim());
    }
    if (this.externalAudioUrl.trim().length > 0) {
      this.nativeStatus = libentry.addExternalAudio(this.playerHandle, this.externalAudioUrl.trim());
    }
    this.audioTracks = [];
    this.subtitleTracks = [];
  }

  private startFramePoll(): void {
    if (this.framePollTimer >= 0) {
      return;
    }
    // 以约 30fps 轮询帧数据，供 PixelMap 显示。
    this.framePollTimer = setInterval(() => {
      this.pollFrame();
    }, 33);
    // 每 3 秒轮询一次播放器状态。
    setInterval(() => this.pollStatus(), 3000);
  }

  private releasePixelMapBuffers(): void {
    for (const pixelMap of this.pixelMapBuffers) {
      try {
        pixelMap.release();
      } catch (_) {
        // The PixelMap may already have been released after a failed write.
      }
    }
    this.pixelMapBuffers = [];
    this.pixelMapBufferIndex = 0;
    this.pixelMapWidth = 0;
    this.pixelMapHeight = 0;
    this.videoPixelMap = null;
  }

  private pollFrame(): void {
    if (this.playerHandle <= 0) {
      return;
    }
    const frameData: FrameData | null = libentry.getFrameData(this.playerHandle) as FrameData | null;
    if (frameData === null || frameData === undefined || frameData.width <= 0 || frameData.height <= 0) {
      return;
    }
    try {
      const opts: image.InitializationOptions = {
        size: { width: frameData.width, height: frameData.height },
        srcPixelFormat: image.PixelMapFormat.RGBA_8888,
        pixelFormat: image.PixelMapFormat.RGBA_8888,
        alphaType: image.AlphaType.OPAQUE,
      };
      if (this.videoPixelMap !== null &&
        (this.pixelMapWidth !== frameData.width || this.pixelMapHeight !== frameData.height)) {
        this.releasePixelMapBuffers();
      }
      const nextBuffer = this.pixelMapBuffers[this.pixelMapBufferIndex];
      if (nextBuffer === undefined) {
        this.pixelMapBuffers.push(image.createPixelMapSync(frameData.data, opts));
        this.pixelMapWidth = frameData.width;
        this.pixelMapHeight = frameData.height;
      } else {
        nextBuffer.writeBufferToPixels(frameData.data);
      }
      this.videoPixelMap = this.pixelMapBuffers[this.pixelMapBufferIndex];
      this.pixelMapBufferIndex = (this.pixelMapBufferIndex + 1) % 2;
      this.showVideo = true;
    } catch (_) {
      this.releasePixelMapBuffers();
    }
  }

  private createPlayer(): boolean {
    if (this.playerHandle > 0) {
      return true;
    }
    // 先设置字体目录，确保 libass/fontconfig 能找到系统字体渲染字幕
    try {
      const cacheDir = getContext(this).cacheDir;
      libentry.setDataDir(cacheDir);
    } catch (e) {
      console.error(`VidAll_Player: setDataDir failed: ${e}`);
    }
    const handle = libentry.createPlayer();
    if (handle <= 0) {
      this.nativeStatus = '创建 libmpv 失败；请确认运行在 ARM64 真机且 libmpv.so 已打包。';
      return false;
    }
    this.playerHandle = handle;
    const eventStatus = libentry.setEventCallback(handle, (event: NativePlayerEvent) => this.onNativePlayerEvent(event));
    if (eventStatus !== '事件回调已注册') {
      this.nativeStatus = `libmpv 事件回调注册失败：${eventStatus}`;
      libentry.release(handle);
      this.playerHandle = 0;
      return false;
    }
    this.nativeStatus = `libmpv 已创建，句柄 #${handle}`;
    return true;
  }

  private onNativePlayerEvent(event: NativePlayerEvent): void {
    if (event.type === 'error') {
      this.isPlaying = false;
      this.showVideo = false;
      this.nativeStatus = `媒体加载失败：${event.message} (${event.errorCode})`;
      console.error(`VidAll_Player libmpv error: ${event.message} (${event.errorCode})`);
      return;
    }
    if (event.type === 'tracks') {
      this.refreshTracks();
      return;
    }
    if (event.type === 'buffering') {
      this.pollStatus();
      return;
    }
    console.warn(`VidAll_Player libmpv: ${event.message}`);
  }

  private loadVideo(): void {
    if (!this.createPlayer()) {
      return;
    }
    if (this.surfaceId.length === 0) {
      this.nativeStatus = '正在等待 XComponent Surface 创建。';
      return;
    }
    this.nativeStatus = libentry.attachSurface(this.playerHandle, this.surfaceId);
    this.submitLoad();
    this.isPlaying = true;
    this.refreshTracksWhenReady();
    this.startFramePoll();
  }

  private refreshTracks(): boolean {
    if (this.playerHandle <= 0) {
      return false;
    }
    const groups = splitTracks(libentry.getTracks(this.playerHandle));
    this.audioTracks = groups.audio;
    this.subtitleTracks = groups.subtitle;
    return this.audioTracks.length > 0 || this.subtitleTracks.length > 0;
  }

  private refreshTracksWhenReady(): void {
    let attempts = 0;
    const timer = setInterval(() => {
      attempts++;
      if (this.refreshTracks() || attempts >= 10) {
        clearInterval(timer);
      }
    }, 500);
  }

  private selectAudioTrack(track: LibMpvTrack): void {
    if (this.playerHandle <= 0 || track.id === undefined) {
      return;
    }
    this.nativeStatus = libentry.selectAudioTrack(this.playerHandle, track.id);
    this.pollTracksAfterSwitch();
  }

  private loadExternalSubtitle(): void {
    if (this.playerHandle <= 0) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    const uri = this.subtitleUrl.trim();
    if (uri.length === 0) {
      this.nativeStatus = '请先填写外挂字幕 URL。';
      return;
    }
    this.nativeStatus = libentry.addExternalSubtitle(this.playerHandle, uri);
    // 字幕加载后刷新轨道列表，让新字幕出现在字幕轨面板中
    this.pollTracksAfterSwitch();
  }

  private loadExternalAudio(): void {
    if (this.playerHandle <= 0) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    const uri = this.externalAudioUrl.trim();
    if (uri.length === 0) {
      this.nativeStatus = '请先填写外挂音频 URL。';
      return;
    }
    this.nativeStatus = libentry.addExternalAudio(this.playerHandle, uri);
    // 音轨加载后刷新轨道列表，让新音轨出现在音轨面板中
    this.pollTracksAfterSwitch();
  }

  private selectSubtitleTrack(track: LibMpvTrack | null): void {
    if (this.playerHandle <= 0) {
      return;
    }
    this.nativeStatus = libentry.selectSubtitleTrack(this.playerHandle, track?.id ?? null);
    this.pollTracksAfterSwitch();
  }

  private pollTracksAfterSwitch(): void {
    this.refreshTracks();
    let attempts = 0;
    const timer = setInterval(() => {
      attempts++;
      this.refreshTracks();
      if (attempts >= 4) {
        clearInterval(timer);
      }
    }, 250);
  }

  private togglePlayback(): void {
    if (this.playerHandle <= 0) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    this.isPlaying = !this.isPlaying;
    this.nativeStatus = libentry.setPause(this.playerHandle, !this.isPlaying);
  }

  private seekBy(deltaSeconds: number): void {
    if (this.playerHandle <= 0) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    this.nativeStatus = libentry.seekRelative(this.playerHandle, deltaSeconds);
  }

  private stopPlayback(): void {
    if (this.playerHandle > 0) {
      this.nativeStatus = libentry.stop(this.playerHandle);
      this.isPlaying = false;
      this.showVideo = false;
    }
  }

  private releasePlayer(): void {
    if (this.playerHandle > 0) {
      this.nativeStatus = libentry.release(this.playerHandle);
      this.playerHandle = 0;
      this.isPlaying = false;
      this.showVideo = false;
    }
    if (this.framePollTimer >= 0) {
      clearInterval(this.framePollTimer);
      this.framePollTimer = -1;
    }
    this.releasePixelMapBuffers();
  }

  private pollStatus(): void {
    if (this.playerHandle > 0) {
      this.nativeStatus = libentry.getPlayerStatus(this.playerHandle);
      // 缓冲/缓存状态（US4）：paused-for-cache 表示等待缓存，demuxer 预读显示已缓存时长。
      const buffering: BufferingState = libentry.getBufferingState(this.playerHandle);
      this.currentMediaKind = buffering.mediaKind;
      this.currentProxyLeaseId = buffering.proxyLeaseId;
      if (buffering.pausedForCache) {
        this.bufferingInfo = '缓冲中：等待缓存恢复 (paused-for-cache)';
      } else if (buffering.demuxerBuffering) {
        this.bufferingInfo = `预读中：已缓存 ${buffering.cacheDurationSeconds.toFixed(1)} 秒`;
      } else {
        this.bufferingInfo = '';
      }
    }
  }

  private attachSurface(): void {
    console.info(`VidAll_Player attachSurface: called`);
    const surfaceId = this.surfaceController.getXComponentSurfaceId();
    console.info(`VidAll_Player attachSurface: surfaceId = ${surfaceId}`);
    this.surfaceId = surfaceId;
    if (this.playerHandle <= 0) {
      console.info(`VidAll_Player attachSurface: creating player...`);
      if (!this.createPlayer()) {
        console.error(`VidAll_Player attachSurface: createPlayer FAILED`);
        return;
      }
      console.info(`VidAll_Player attachSurface: createPlayer returned ${this.playerHandle}`);
    }
    this.tryAutoPlay();
  }

  build() {
    Scroll() {
      Column({ space: 16 }) {
      Text('VidAll Player')
        .fontSize(36)
        .fontWeight(FontWeight.Bold)
        .fontColor('#F4F7FB')

      Text('HarmonyOS libmpv + XComponent + EGL/GLES 验证')
        .fontSize(18)
        .fontColor('#AFC6E9')

      // Video display area — XComponent provides surface, Image(PixelMap) overlays for emulator display
      Stack() {
        // XComponent surface (used for NativeWindow path on real hardware)
        XComponent({ id: 'mpv-video-surface', type: XComponentType.SURFACE, controller: this.surfaceController })
          .width('100%')
          .height('100%')
          .onLoad(() => {
            console.info(`VidAll_Player: XComponent onLoad fired`);
            this.attachSurface();
          })
          .onDestroy(() => {
            console.info(`VidAll_Player: XComponent onDestroy fired`);
            if (this.playerHandle > 0) {
              this.nativeStatus = libentry.detachSurface(this.playerHandle);
            }
            this.surfaceId = '';
          })
        // PixelMap overlay for emulator display (when NativeWindow BufferQueue is broken)
        if (this.showVideo && this.videoPixelMap !== null) {
          Image(this.videoPixelMap)
            .width('100%')
            .height('100%')
            .objectFit(ImageFit.Contain)
        }
        // Status text when no video
        if (!this.showVideo) {
          Text(this.playerHandle > 0 ? '正在等待视频帧...' : '点击"加载视频"开始播放')
            .fontSize(18)
            .fontColor('#D9E6F7')
        }
      }
      .width('88%')
      .height(260)
      .border({ width: 2, color: '#426991', radius: 12 })
      .backgroundColor('#07121F')

      // 播放控制栏：紧贴视频画面，方便操作
      Row({ space: 10 }) {
        Button(this.isPlaying ? '暂停' : '播放')
          .id('toggle-playback-button')
          .fontSize(16)
          .backgroundColor('#1A9A78')
          .enabled(this.playerHandle > 0)
          .onClick(() => this.togglePlayback())

        Button('快退 10s')
          .id('seek-backward-button')
          .fontSize(16)
          .backgroundColor('#4B6C8A')
          .enabled(this.playerHandle > 0)
          .onClick(() => this.seekBy(-10))

        Button('快进 10s')
          .id('seek-forward-button')
          .fontSize(16)
          .backgroundColor('#4B6C8A')
          .enabled(this.playerHandle > 0)
          .onClick(() => this.seekBy(10))

        Button('停止')
          .id('stop-video-button')
          .fontSize(16)
          .backgroundColor('#9B6A2F')
          .enabled(this.playerHandle > 0)
          .onClick(() => this.stopPlayback())
      }
      .width('88%')
      .justifyContent(FlexAlign.Center)

      Text(this.runtimeInfo)
        .fontSize(15)
        .fontColor('#8FA7C5')

      Text(this.nativeStatus)
        .fontSize(16)
        .fontColor('#DDE8F8')
        .textAlign(TextAlign.Center)
        .width('88%')

      Text(`Surface ID: ${this.surfaceId.length > 0 ? this.surfaceId : '(未创建)'}`)
        .fontSize(14)
        .fontColor('#8FA7C5')
        .width('88%')

      if (this.currentMediaKind.length > 0) {
        Text(`媒体类型: ${this.currentMediaKind}${this.currentProxyLeaseId.length > 0 ? ` | SMB 代理租约: ${this.currentProxyLeaseId}` : ''}`)
          .id('media-kind-info')
          .fontSize(14)
          .fontColor('#8FA7C5')
          .width('88%')
      }
      if (this.bufferingInfo.length > 0) {
        Text(this.bufferingInfo)
          .id('buffering-info')
          .fontSize(15)
          .fontColor('#E0B34D')
          .width('88%')
      }

      Column({ space: 8 }) {
        Row() {
          Text('音轨与字幕')
            .fontSize(20)
            .fontWeight(FontWeight.Medium)
            .fontColor('#DDE8F8')
            .layoutWeight(1)
          Button('刷新轨道')
            .id('refresh-tracks-button')
            .enabled(this.playerHandle > 0)
            .backgroundColor('#2F7DE1')
            .onClick(() => this.refreshTracks())
        }
        if (this.audioTracks.length === 0 && this.subtitleTracks.length === 0) {
          Text('加载包含多音轨或字幕的视频后显示轨道元数据。')
            .fontSize(14)
            .fontColor('#8FA7C5')
        } else {
          Text('音轨')
            .fontSize(16)
            .fontColor('#AFC6E9')
          Row({ space: 8 }) {
            ForEach(this.audioTracks, (track: LibMpvTrack) => {
              Button(trackLabel(track))
                .id(`audio-track-${track.id}`)
                .fontSize(15)
                .backgroundColor(track.selected ? '#1A9A78' : '#315473')
                .onClick(() => this.selectAudioTrack(track))
            }, (track: LibMpvTrack) => `audio-${track.id}-${track.selected}`)
          }
          .width('100%')
          Text('字幕')
            .fontSize(16)
            .fontColor('#AFC6E9')
          Row({ space: 8 }) {
            Button('关闭字幕')
              .id('subtitle-track-off')
              .fontSize(15)
              .backgroundColor(this.subtitleTracks.every((track: LibMpvTrack) => !track.selected) ? '#9B6A2F' : '#315473')
              .onClick(() => this.selectSubtitleTrack(null))
            ForEach(this.subtitleTracks, (track: LibMpvTrack) => {
              Button(trackLabel(track))
                .id(`subtitle-track-${track.id}`)
                .fontSize(15)
                .backgroundColor(track.selected ? '#1A9A78' : '#315473')
                .onClick(() => this.selectSubtitleTrack(track))
            }, (track: LibMpvTrack) => `subtitle-${track.id}-${track.selected}`)
          }
          .width('100%')
        }
      }
      .width('88%')
      .padding(12)
      .border({ width: 1, color: '#426991', radius: 10 })
      .backgroundColor('#0C1A2A')

      TextInput({ text: this.url, placeholder: '输入视频 URL（HTTP/HTTPS、HLS .m3u8、DASH .mpd 或 SMB 代理 http://127.0.0.1…）' })
        .id('video-url-input')
        .width('88%')
        .fontSize(17)
        .onChange((value: string) => {
          this.url = value;
          this.isWebDavSource = false;
        })

      Row({ space: 8 }) {
        TextInput({ text: this.subtitleUrl, placeholder: '外挂字幕 URL（可选，如 http://…/movie.srt）' })
          .id('subtitle-url-input')
          .layoutWeight(1)
          .fontSize(15)
          .onChange((value: string) => {
            this.subtitleUrl = value;
          })
        Button('加载外挂字幕')
          .id('load-external-subtitle-button')
          .fontSize(15)
          .enabled(this.playerHandle > 0 && this.subtitleUrl.trim().length > 0)
          .backgroundColor('#2F7DE1')
          .onClick(() => this.loadExternalSubtitle())
      }
      .width('88%')

      Row({ space: 8 }) {
        TextInput({ text: this.externalAudioUrl, placeholder: '外挂音频 URL（可选，如 http://…/movie.m4a）' })
          .id('external-audio-url-input')
          .layoutWeight(1)
          .fontSize(15)
          .onChange((value: string) => {
            this.externalAudioUrl = value;
          })
        Button('加载外挂音频')
          .id('load-external-audio-button')
          .fontSize(15)
          .enabled(this.playerHandle > 0 && this.externalAudioUrl.trim().length > 0)
          .backgroundColor('#2F7DE1')
          .onClick(() => this.loadExternalAudio())
      }
      .width('88%')

      Column({ space: 8 }) {
        Text('WebDAV 媒体目录')
          .fontSize(20)
          .fontWeight(FontWeight.Medium)
          .fontColor('#DDE8F8')
          .width('100%')
        TextInput({ text: this.webDavEndpoint, placeholder: 'WebDAV 地址，例如 https://example.com/dav/media/' })
          .width('100%')
          .onChange((value: string) => this.webDavEndpoint = value)
        Row({ space: 8 }) {
          TextInput({ text: this.webDavUsername, placeholder: '用户名' })
            .layoutWeight(1)
            .onChange((value: string) => this.webDavUsername = value)
          TextInput({ text: this.webDavPassword, placeholder: '密码' })
            .layoutWeight(1)
            .type(InputType.Password)
            .onChange((value: string) => this.webDavPassword = value)
          Button(this.isWebDavLoading ? '读取中' : '列出目录')
            .enabled(!this.isWebDavLoading)
            .backgroundColor('#2F7DE1')
            .onClick(() => this.browseWebDav())
        }
        if (this.webDavDirectory.length > 0) {
          Text(this.webDavDirectory)
            .fontSize(13)
            .fontColor('#8FA7C5')
            .maxLines(1)
        }
        if (this.webDavEntries.length === 0 && !this.isWebDavLoading) {
          Text('目录中没有可播放的视频或子目录。')
            .fontSize(15)
            .fontColor('#8FA7C5')
            .padding({ top: 8, bottom: 8 })
        } else {
          Text('选择目录继续浏览；选择视频将立即加载播放。')
            .fontSize(14)
            .fontColor('#AFC6E9')
          Column({ space: 8 }) {
            ForEach(this.webDavEntries, (entry: WebDavEntry) => {
              Button() {
                Row({ space: 10 }) {
                  Text(entry.isDirectory ? '目录' : '视频')
                    .fontSize(14)
                    .fontColor(entry.isDirectory ? '#B9DFFF' : '#B8F4D9')
                    .width(40)
                  Text(entry.name)
                    .fontSize(18)
                    .fontColor('#F4F7FB')
                    .layoutWeight(1)
                    .maxLines(1)
                  if (!entry.isDirectory && entry.size > 0) {
                    Text(`${Math.ceil(entry.size / 1024 / 1024)} MB`)
                      .fontSize(14)
                      .fontColor('#B7C8DE')
                  }
                }
                .width('100%')
              }
              .id(`webdav-entry-${entry.url}`)
              .width('100%')
              .height(52)
              .enabled(!this.isWebDavLoading)
              .padding({ left: 12, right: 12 })
              .backgroundColor(entry.isDirectory ? '#1B4C79' : '#17624C')
              .borderRadius(8)
              .onClick(() => this.openWebDavEntry(entry))
            }, (entry: WebDavEntry) => entry.url)
          }
          .width('100%')
        }
      }
      .width('88%')
      .padding(12)
      .border({ width: 1, color: '#426991', radius: 10 })
      .backgroundColor('#0C1A2A')

      Row({ space: 12 }) {
        Button('加载视频')
          .id('load-video-button')
          .fontSize(18)
          .backgroundColor('#2F7DE1')
          .onClick(() => this.loadVideo())

        Button('释放')
          .id('release-mpv-button')
          .fontSize(18)
          .backgroundColor('#B34D4D')
          .onClick(() => this.releasePlayer())

        Button('状态')
          .id('status-button')
          .fontSize(18)
          .backgroundColor('#5B4D8A')
          .onClick(() => {
            if (this.playerHandle > 0) {
              this.nativeStatus = libentry.getPlayerStatus(this.playerHandle);
            } else {
              this.nativeStatus = '播放器未创建';
            }
          })
      }
      }
      .width('100%')
      .justifyContent(FlexAlign.Start)
      .alignItems(HorizontalAlign.Center)
      .padding(28)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#102033')
  }
}