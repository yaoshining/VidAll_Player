import libentry from 'libentry.so';
import { fileIo as fs } from '@kit.CoreFileKit';
import { image } from '@kit.ImageKit';

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
  private framePollTimer: number = -1;

  aboutToAppear(): void {
    const buildInfo = libentry.getBuildInfo();
    this.runtimeInfo = `ABI: ${buildInfo.abi} | libmpv: ${buildInfo.mpvVersion}`;
    this.nativeStatus = buildInfo.available
      ? 'ARM64 libmpv 已打包。等待 XComponent Surface 创建...'
      : '当前为 x86_64 模拟器：ARM64 libmpv 未打包，不能播放。';
    console.info(`VidAll_Player native: ${this.runtimeInfo}; ${this.nativeStatus}`);
    this.prepareLocalVideo().then(() => {
      console.info(`VidAll_Player: prepareLocalVideo done, url = ${this.url}`);
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

  private tryAutoPlay(): void {
    if (this.playerHandle <= 0 || this.url.length === 0 || this.surfaceId.length === 0) {
      return;
    }
    console.info(`VidAll_Player: auto-playing, url = '${this.url}', surfaceId = ${this.surfaceId}`);
    this.nativeStatus = libentry.attachSurface(this.playerHandle, this.surfaceId);
    console.info(`VidAll_Player: attachSurface status = ${this.nativeStatus}`);
    this.nativeStatus = libentry.load(this.playerHandle, this.url);
    console.info(`VidAll_Player: load status = ${this.nativeStatus}`);
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

  private pollFrame(): void {
    if (this.playerHandle <= 0) {
      return;
    }
    const frameData: FrameData | null = libentry.getFrameData(this.playerHandle) as FrameData | null;
    if (frameData === null || frameData === undefined) {
      return;
    }
    try {
      const w = frameData.width;
      const h = frameData.height;
      if (w <= 0 || h <= 0) {
        return;
      }
      // Reuse existing PixelMap if dimensions match
      if (this.videoPixelMap !== null) {
        try {
          // Write data directly into existing PixelMap
          this.videoPixelMap.writeBufferToPixels(frameData.data);
          return;
        } catch (e) {
          // Fallback to creating new PixelMap
          this.videoPixelMap.release();
          this.videoPixelMap = null;
        }
      }
      const opts: image.InitializationOptions = {
        size: { width: w, height: h },
        srcPixelFormat: image.PixelMapFormat.RGBA_8888,
        pixelFormat: image.PixelMapFormat.RGBA_8888,
        alphaType: image.AlphaType.OPAQUE,
      };
      this.videoPixelMap = image.createPixelMapSync(frameData.data, opts);
      this.showVideo = true;
    } catch (e) {
      // PixelMap creation may fail on first few frames; ignore
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
    this.nativeStatus = libentry.load(this.playerHandle, this.url);
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
    if (this.videoPixelMap !== null) {
      this.videoPixelMap.release();
      this.videoPixelMap = null;
    }
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

      TextInput({ text: this.url, placeholder: '输入 HTTP / HTTPS / WebDAV 视频 URL' })
        .id('video-url-input')
        .width('88%')
        .fontSize(17)
        .onChange((value: string) => {
          this.url = value;
        })

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
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor('#102033')
    .padding(28)
  }
}