import libentry from 'libentry.so';
import { fileIo as fs } from '@kit.CoreFileKit';
import { image } from '@kit.ImageKit';
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
  @State playerHandle: number = 0;
  @State surfaceId: string = '';
  @State isPlaying: boolean = false;
  @State videoPixelMap: image.PixelMap | null = null;
  @State showVideo: boolean = false;
  private pixelMapBuffers: image.PixelMap[] = [];
  private pixelMapBufferIndex: number = 0;
  private pixelMapWidth: number = 0;
  private pixelMapHeight: number = 0;
  @State webDavEndpoint: string = '';
  @State webDavUsername: string = '';
  @State webDavPassword: string = '';
  @State webDavEntries: WebDavEntry[] = [];
  @State webDavDirectory: string = '';
  @State isWebDavLoading: boolean = false;
  @State isWebDavSource: boolean = false;
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
      this.webDavEndpoint = saved.endpoint;
      this.webDavUsername = saved.username;
    } catch (_) {
      this.nativeStatus = '无法读取已保存的 WebDAV 配置。';
    }
  }

  private async browseWebDav(directoryUrl?: string): Promise<void> {
    const config = this.getWebDavConfig();
    this.isWebDavLoading = true;
    try {
      await new WebDavService(getContext(this)).saveConfig(config);
      this.webDavEntries = await new WebDavService(getContext(this)).listDirectory(config, directoryUrl);
      this.webDavDirectory = directoryUrl ?? config.endpoint;
      this.nativeStatus = `已列出 ${this.webDavEntries.length} 个 WebDAV 项目。`;
    } catch (error) {
      this.nativeStatus = error instanceof Error ? error.message : '列出 WebDAV 目录失败。';
    } finally {
      this.isWebDavLoading = false;
    }
  }

  private openWebDavEntry(entry: WebDavEntry): void {
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
    this.nativeStatus = libentry.load(this.playerHandle, this.url,
      this.isWebDavSource ? `Authorization: ${buildBasicAuthorization(this.webDavUsername, this.webDavPassword)}` : '');
    console.info(`VidAll_Player: load submitted`);
    this.isPlaying = true;
    // Start polling for frame data (for PixelMap display)
    this.startFramePoll();
  }

  private startFramePoll(): void {
    if (this.framePollTimer >= 0) {
      return;
    }
    // Poll frames at ~30fps for PixelMap display
    this.framePollTimer = setInterval(() => {
      this.pollFrame();
    }, 33);
    // Status poll every 3 seconds
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
    const handle = libentry.createPlayer();
    if (handle <= 0) {
      this.nativeStatus = '创建 libmpv 失败；请确认运行在 ARM64 真机且 libmpv.so 已打包。';
      return false;
    }
    this.playerHandle = handle;
    this.nativeStatus = `libmpv 已创建，句柄 #${handle}`;
    return true;
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
    this.nativeStatus = libentry.load(this.playerHandle, this.url,
      this.isWebDavSource ? `Authorization: ${buildBasicAuthorization(this.webDavUsername, this.webDavPassword)}` : '');
    this.isPlaying = true;
    this.startFramePoll();
  }

  private togglePlayback(): void {
    if (this.playerHandle <= 0) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    this.isPlaying = !this.isPlaying;
    this.nativeStatus = libentry.setPause(this.playerHandle, !this.isPlaying);
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
      const status = libentry.getPlayerStatus(this.playerHandle);
      this.nativeStatus = status;
    }
  }

  private attachSurface(): void {
    console.info(`VidAll_Player attachSurface: called`);
    const surfaceId = this.surfaceController.getXComponentSurfaceId();
    console.info(`VidAll_Player attachSurface: surfaceId = ${surfaceId}`);
    this.surfaceId = surfaceId;
    if (this.playerHandle <= 0) {
      console.info(`VidAll_Player attachSurface: creating player...`);
      const handle = libentry.createPlayer();
      console.info(`VidAll_Player attachSurface: createPlayer returned ${handle}`);
      if (handle > 0) {
        this.playerHandle = handle;
        this.nativeStatus = `libmpv 已创建，句柄 #${handle}`;
      } else {
        this.nativeStatus = '创建 libmpv 失败；请确认运行在 ARM64 真机且 libmpv.so 已打包。';
        console.error(`VidAll_Player attachSurface: createPlayer FAILED`);
        return;
      }
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

      TextInput({ text: this.url, placeholder: '输入 HTTP / HTTPS 视频 URL' })
        .id('video-url-input')
        .width('88%')
        .fontSize(17)
        .onChange((value: string) => {
          this.url = value;
          this.isWebDavSource = false;
        })

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

        Button(this.isPlaying ? '暂停' : '播放')
          .id('toggle-playback-button')
          .fontSize(18)
          .backgroundColor('#1A9A78')
          .onClick(() => this.togglePlayback())

        Button('停止')
          .id('stop-video-button')
          .fontSize(18)
          .backgroundColor('#9B6A2F')
          .onClick(() => this.stopPlayback())

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