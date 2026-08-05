import {
  createPlayer,
  VidAllPlayer,
  XComponentSurfaceAdapter,
  VidAllPlayerSurfaceTarget,
  MediaSource,
  PlayerEvent,
  PlayerTrack,
  PlayerTrackKind,
  VideoParams,
  ExternalAudio,
  ExternalSubtitle
} from '@vidall/player';
import { fileIo as fs, picker } from '@kit.CoreFileKit';
import { common } from '@kit.AbilityKit';
import { KeyCode } from '@kit.InputKit';
import { image } from '@kit.ImageKit';
import { detectMediaKind, newProxyLeaseId } from '../player/MediaKindDetection';
import { computeLetterboxSize } from '../player/videoLetterbox';
import { DemoLifecycleController } from '../player/DemoLifecycle';
import { splitTracks, trackLabel } from '../player/TrackPresentation';
import { buildBasicAuthorization, buildWebDavPlaybackHeaders, WebDavConfig, WebDavEntry, WebDavService } from '../webdav/WebDavService';
import { buildSmbMediaUri, SmbConfig, SmbService } from '../smb/SmbService';

@Entry
@Component
struct Index {
  private readonly surfaceController: XComponentController = new XComponentController();
  private surfaceAdapter: XComponentSurfaceAdapter | null = null;
  @State nativeStatus: string = '正在初始化 @vidall/player...';
  @State runtimeInfo: string = '@vidall/player HAR';
  @State url: string = '';
  @State subtitleUrl: string = '';
  @State externalAudioUrl: string = '';
  @State currentMediaKind: string = '';
  @State currentProxyLeaseId: string = '';
  @State bufferingInfo: string = '';
  @State errorCode: string = '';
  @State errorDescription: string = '';
  @State errorRetryable: boolean = false;
  @StorageLink('vidallAppForeground') @Watch('onAppForegroundChanged') private appForeground: boolean = true;
  private player: VidAllPlayer | null = null;
  private unsubscribe: (() => void) | null = null;
  private pendingAutoPlay: boolean = false;
  @State surfaceId: string = '';
  @State isPlaying: boolean = false;
  private activePlaybackUrl: string = '';
  @State showVideo: boolean = false;
  @State webDavEndpoint: string = 'http://192.168.3.59:5005';
  @State webDavUsername: string = '';
  @State webDavPassword: string = '';
  @State webDavEntries: WebDavEntry[] = [];
  @State webDavDirectory: string = '';
  @State isWebDavLoading: boolean = false;
  @State isWebDavSource: boolean = false;
  @State smbHost: string = '';
  @State smbShare: string = '';
  @State smbPath: string = '';
  @State smbUsername: string = '';
  @State smbPassword: string = '';
  @State smbConfigStatus: string = '';
  @State audioTracks: PlayerTrack[] = [];
  @State subtitleTracks: PlayerTrack[] = [];
  // 当前字幕纯文本（来自原生 "sub-text" 事件），独立于软件渲染是否把字幕像素
  // 画进视频帧；用于在视频下方展示一条调试字幕条，验证字幕解析/切换是否生效。
  // 空字符串表示当前无字幕命中。
  @State subtitleText: string = '';
  // 视频真实宽高比：默认 16:9，收到原生 videoParams 事件后按真实分辨率更新，
  // 用于让视频容器按比例居中显示，避免 SURFACE XComponent 在低 API 级别下强制拉伸填满。
  @State videoAspectRatio: number = 16 / 9;
  @State isFullscreen: boolean = false;
  @State isExitButtonVisible: boolean = false;
  private exitButtonHideTimer: number | undefined = undefined;
  // 视频显示框（letterbox 内框）的最终尺寸，按外框尺寸与真实宽高比计算得出；
  // 0 表示尚未测量到外框尺寸，此时先填满外框，等 onAreaChange 触发后立即校正。
  @State videoBoxWidthVp: number = 0;
  @State videoBoxHeightVp: number = 0;
  private outerWidthVp: number = 0;
  private outerHeightVp: number = 0;
  // 初始默认值仅用于首次 attach 前的占位，onAreaChange 触发后会立即校正为真实像素尺寸。
  private lastKnownWidthPx: number = 1280;
  private lastKnownHeightPx: number = 720;
  private webDavBrowseGeneration: number = 0;
  private readonly lifecycle: DemoLifecycleController = new DemoLifecycleController();

  constructor() {
    super();
  }

  aboutToAppear(): void {
    // 在 aboutToAppear 中创建播放器与 Surface 适配器，避免 struct 构造函数字段赋值不可靠。
    const subtitleFontsDir = this.prepareSubtitleFontsDirSync();
    this.player = createPlayer({ subtitleFontsDir });
    this.surfaceAdapter = new XComponentSurfaceAdapter(new VidAllPlayerSurfaceTarget(this.player));
    this.nativeStatus = '@vidall/player 已创建，等待 XComponent Surface...';
    console.info(`VidAll_Player: ${this.nativeStatus}`);
    this.subscribePlayerEvents();
    this.loadSavedWebDavConfig();
    this.loadSavedSmbConfig();
    this.prepareLocalVideo().then(() => {
      console.info(`VidAll_Player: prepareLocalVideo done`);
      this.tryAutoPlay();
    }).catch((e: Error) => {
      console.error(`VidAll_Player: prepareLocalVideo failed: ${e}`);
    });
    this.prepareTestSubtitleSync();
  }

  // 临时诊断：把内置的字幕诊断文件从 rawfile 解包到应用沙箱，自动填入外挂字幕 URL 输入框，
  // 便于在本地测试视频上快速复现"字幕轨道选中但不渲染"问题，无需每次都重新导航 WebDAV 目录。
  private prepareTestSubtitleSync(): void {
    try {
      const context = getContext(this);
      const cacheDir = context.cacheDir;
      const destPath = `${cacheDir}/test_subtitle.srt`;
      try {
        const stat = fs.statSync(destPath);
        if (stat.size > 0) {
          this.subtitleUrl = `file://${destPath}`;
          return;
        }
      } catch (e) {
        // 文件不存在，继续解包
      }
      const rawFile = context.resourceManager.getRawFileContentSync('subs/test.srt');
      const file = fs.openSync(destPath, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE);
      fs.writeSync(file.fd, rawFile.buffer);
      fs.closeSync(file);
      // externalSubtitles.uri 未经过 submitLoad() 里对主 URL 做的 file:// 归一化处理，
      // 必须自己拼出绝对 URI，否则 SDK 的 URI 校验会把整个 load() 请求拒绝掉。
      this.subtitleUrl = `file://${destPath}`;
      console.info(`VidAll_Player: extracted test subtitle to ${destPath} (${rawFile.byteLength} bytes)`);
    } catch (e) {
      console.error(`VidAll_Player: failed to prepare test subtitle: ${e}`);
    }
  }

  aboutToDisappear(): void {
    this.releasePlayer();
  }

  // 把内置的 Noto Sans 字体从 rawfile 解包到应用沙箱内的真实文件路径，供原生层
  // libass 通过 sub-fonts-dir 匹配字幕字体使用（HarmonyOS 沙箱没有系统 fontconfig，
  // 不解包字体的话字幕轨道会被正确选中但完全不可见）。同步执行以确保在
  // createPlayer()（进而触发原生 mpv 初始化）之前就已经就绪。
  private prepareSubtitleFontsDirSync(): string {
    try {
      const context = getContext(this);
      const fontsDir = `${context.filesDir}/fonts`;
      const destPath = `${fontsDir}/NotoSans-Regular.ttf`;
      try {
        const stat = fs.statSync(destPath);
        if (stat.size > 0) {
          return fontsDir;
        }
      } catch (e) {
        // 目录或文件不存在，继续执行解包
      }
      try {
        fs.mkdirSync(fontsDir, true);
      } catch (e) {
        // 目录已存在时会抛错，忽略
      }
      const rawFile = context.resourceManager.getRawFileContentSync('fonts/NotoSans-Regular.ttf');
      const file = fs.openSync(destPath, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE);
      fs.writeSync(file.fd, rawFile.buffer);
      fs.closeSync(file);
      console.info(`VidAll_Player: extracted subtitle font to ${destPath} (${rawFile.byteLength} bytes)`);
      return fontsDir;
    } catch (e) {
      console.error(`VidAll_Player: failed to prepare subtitle fonts dir: ${e}`);
      return '';
    }
  }

  private subscribePlayerEvents(): void {
    if (this.player === null || this.unsubscribe !== null) {
      return;
    }
    this.unsubscribe = this.player.subscribe((event: PlayerEvent) => this.onPlayerEvent(event));
  }

  private onPlayerEvent(event: PlayerEvent): void {
    switch (event.type) {
      case 'error': {
        this.isPlaying = false;
        this.showVideo = false;
        this.lifecycle.markPlaybackStopped();
        if (event.error) {
          this.setPlayerError(event.error.code, event.error.message, event.error.retryable);
          this.nativeStatus = `媒体加载失败：${event.error.message} (${event.error.code})`;
          console.error(`VidAll_Player error: ${event.error.message} (${event.error.code})`);
        }
        break;
      }
      case 'firstFrame': {
        this.showVideo = true;
        this.nativeStatus = `已提交真实首帧（事件 #${event.sequence}）`;
        break;
      }
      case 'tracks': {
        this.refreshTracksFromEvent(event.tracks ?? []);
        break;
      }
      case 'subtitleText': {
        this.subtitleText = event.subtitleText ?? '';
        break;
      }
      case 'videoParams': {
        const params = event.params as VideoParams;
        if (params !== undefined && params.width > 0 && params.height > 0) {
          this.videoAspectRatio = params.width / params.height;
          this.recomputeVideoBoxSize();
          const hwdec = params.hardwareDecoding ?? 'n/a';
          this.runtimeInfo = `${params.width}x${params.height} 硬解: ${hwdec}`;
        }
        break;
      }
      case 'buffering': {
        if (event.paused) {
          this.bufferingInfo = '缓冲中：等待缓存恢复 (paused-for-cache)';
        } else {
          this.bufferingInfo = '';
        }
        break;
      }
      case 'state': {
        console.info(`VidAll_Player: state -> ${event.state}`);
        if (event.state === 'playing') {
          this.isPlaying = true;
          this.showVideo = true;
        } else if (event.state === 'paused') {
          this.isPlaying = false;
        } else if (event.state === 'error' || event.state === 'completed' || event.state === 'released') {
          this.isPlaying = false;
          this.pendingAutoPlay = false;
          if (event.state === 'released') {
            this.showVideo = false;
          }
        }
        if (event.state === 'preparing' || event.state === 'paused' || event.state === 'buffering') {
          // 媒体已就绪（preparing/paused/buffering），此时才能安全调用 play()。
          this.triggerPendingAutoPlay();
        }
        break;
      }
      default: {
        if (event.message) {
          console.info(`VidAll_Player event: ${event.type} ${event.message}`);
        }
      }
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

  private getSmbConfig(): SmbConfig {
    return {
      host: this.smbHost.trim(),
      share: this.smbShare.trim(),
      path: this.smbPath.trim(),
      username: this.smbUsername.trim(),
      password: this.smbPassword
    };
  }

  private async loadSavedSmbConfig(): Promise<void> {
    try {
      const saved = await new SmbService(getContext(this)).loadSavedConfig();
      this.smbHost = saved.host;
      this.smbShare = saved.share;
      this.smbPath = saved.path;
      this.smbUsername = saved.username;
    } catch (_) {
      this.nativeStatus = '无法读取已保存的 SMB 配置。';
    }
  }

  private async saveSmbConfig(): Promise<void> {
    const config = this.getSmbConfig();
    try {
      buildSmbMediaUri(config);
      await new SmbService(getContext(this)).saveConfig(config);
      this.smbConfigStatus = 'SMB 配置已保存，密码未保存。';
      this.nativeStatus = this.smbConfigStatus;
    } catch (error) {
      this.smbConfigStatus = error instanceof Error ? error.message : 'SMB 配置无效。';
      this.nativeStatus = this.smbConfigStatus;
    }
  }

  private async loadSmbVideo(): Promise<void> {
    const config = this.getSmbConfig();
    this.smbConfigStatus = '正在验证 SMB 配置...';
    try {
      const uri = buildSmbMediaUri(config);
      await new SmbService(getContext(this)).saveConfig(config);
      this.url = uri;
      this.isWebDavSource = false;
      this.currentMediaKind = 'smb';
      this.nativeStatus = config.username.length > 0
        ? '已提交 SMB 认证加载，凭据仅保留在本次会话。'
        : '已提交匿名 SMB 加载。';
      this.smbConfigStatus = this.nativeStatus;
      this.loadVideo();
    } catch (error) {
      this.nativeStatus = error instanceof Error ? error.message : 'SMB 配置无效。';
      this.smbConfigStatus = this.nativeStatus;
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
        this.nativeStatus = this.redactSensitiveText(message) || '列出 WebDAV 目录失败。';
        console.error(`VidAll_Player WebDAV browse error: ${this.redactSensitiveText(message)}`);
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
    if (this.player === null || this.url.length === 0 || this.surfaceId.length === 0) {
      return;
    }
    console.info(`VidAll_Player: auto-playing, surfaceId = ${this.surfaceId}`);
    this.startOrReloadMedia();
  }

  private startOrReloadMedia(): void {
    this.submitLoad();
    console.info(`VidAll_Player: load submitted`);
    this.isPlaying = true;
    this.lifecycle.markPlaybackStarted(this.activePlaybackUrl);
  }

  // 统一的媒体提交入口（US4）：按 URL 识别 hls/dash/localhostProxy/http/https，
  // SMB localhost 代理生成租约 ID 交给原生层关联，凭据仍只走 Authorization 头。
  private submitLoad(): void {
    if (this.player === null) {
      this.nativeStatus = '播放器未创建。';
      return;
    }
    let targetUrl = this.url.trim();
    if (targetUrl.length === 0) {
      this.nativeStatus = '请先输入或选择媒体地址。';
      return;
    }
    // 本地文件路径（不含 scheme）规范化为 file:// URI，满足 @vidall/player 的绝对 URI 校验。
    if (targetUrl.indexOf('://') < 0) {
      targetUrl = targetUrl.indexOf('/') === 0 ? `file://${targetUrl}` : `file:///${targetUrl}`;
    }
    const detected = detectMediaKind(targetUrl);
    const kind = this.mapMediaKind(detected, targetUrl);
    const playbackHeaders: Record<string, string> = {};
    if (this.isWebDavSource) {
      const webDavHeaders = buildWebDavPlaybackHeaders(this.webDavUsername, this.webDavPassword);
      if (webDavHeaders['Authorization'] !== undefined) {
        playbackHeaders['Authorization'] = webDavHeaders['Authorization'];
      }
    } else if (detected === 'smb' && this.smbUsername.length > 0) {
      playbackHeaders['Authorization'] = buildBasicAuthorization(this.smbUsername, this.smbPassword);
    }
    const proxyLeaseId = detected === 'localhostProxy' ? newProxyLeaseId() : '';
    this.currentMediaKind = detected;
    this.currentProxyLeaseId = proxyLeaseId;
    this.activePlaybackUrl = targetUrl;

    const headers: Record<string, string> = {};
    if (playbackHeaders['Authorization'] !== undefined) {
      // SMB 凭据复用与 WebDAV 相同的 Authorization Basic 头传递给 @vidall/player SDK：
      // SDK 内部会为 kind='smb' 单独解码出用户名/密码，转发给原生层的
      // demuxer-lavf-o/stream-lavf-o 选项（libsmbclient 鉴权），不会作为 HTTP header 发出。
      headers['Authorization'] = playbackHeaders['Authorization'];
    }
    const source: MediaSource = {
      kind: kind,
      uri: targetUrl,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      proxyLeaseId: proxyLeaseId.length > 0 ? proxyLeaseId : undefined,
      externalSubtitles: this.subtitleUrl.trim().length > 0
        ? [{ uri: this.subtitleUrl.trim() } as ExternalSubtitle] : undefined,
      externalAudio: this.externalAudioUrl.trim().length > 0
        ? [{ uri: this.externalAudioUrl.trim() } as ExternalAudio] : undefined
    };
    this.audioTracks = [];
    this.subtitleTracks = [];
    // load() 的 Promise 在原生命令派发后即 resolve，实际状态转换到 preparing/paused 是
    // 通过异步 state 事件到达的；这里不能在 load().then() 里直接调用 play()（会与状态机竞态），
    // 而是置位 pendingAutoPlay，待 onPlayerEvent 收到可播放状态后再触发 play()。
    this.pendingAutoPlay = true;
    this.player.load(source).then(() => {
      this.nativeStatus = this.redactSensitiveText(`已加载：${targetUrl}`);
    }).catch((e: Error) => {
      this.pendingAutoPlay = false;
      this.setPlayerError('LOAD', e.message, true);
      this.nativeStatus = `加载失败：${this.redactSensitiveText(e.message)}`;
      console.error(`VidAll_Player load failed: ${e}`);
    });
  }

  private triggerPendingAutoPlay(): void {
    if (!this.pendingAutoPlay || this.player === null) {
      return;
    }
    this.pendingAutoPlay = false;
    this.player.play().then(() => {
      this.nativeStatus = '播放中。';
    }).catch((e: Error) => {
      this.setPlayerError('PLAY', e.message, true);
      this.nativeStatus = `播放失败：${this.redactSensitiveText(e.message)}`;
      console.error(`VidAll_Player play failed: ${e}`);
    });
  }

  private mapMediaKind(detected: string, uri: string): 'localFile' | 'http' | 'https' | 'hls' | 'dash' | 'localhostProxy' | 'smb' {
    if (uri.indexOf('file://') === 0) {
      return 'localFile';
    }
    if (uri.indexOf('smb://') === 0) {
      return 'smb';
    }
    if (detected === 'hls') {
      return 'hls';
    }
    if (detected === 'dash') {
      return 'dash';
    }
    if (detected === 'localhostProxy') {
      return 'localhostProxy';
    }
    if (detected === 'https') {
      return 'https';
    }
    if (detected === 'http') {
      return 'http';
    }
    return 'localFile';
  }

  private loadVideo(): void {
    if (this.player === null) {
      this.nativeStatus = '播放器未创建。';
      return;
    }
    if (this.surfaceId.length === 0) {
      this.nativeStatus = '正在等待 XComponent Surface 创建。';
      return;
    }
    this.startOrReloadMedia();
  }

  private refreshTracksFromEvent(tracks: PlayerTrack[]): void {
    const groups = splitTracks(tracks);
    this.audioTracks = groups.audio;
    this.subtitleTracks = groups.subtitle;
  }

  private selectAudioTrack(track: PlayerTrack): void {
    if (this.player === null) {
      return;
    }
    this.player.selectTrack('audio', track.id).then(() => {
      this.nativeStatus = `已选择音轨 #${track.id}`;
    }).catch((e: Error) => {
      this.nativeStatus = `切换音轨失败：${e.message}`;
    });
  }

  private loadExternalSubtitle(): void {
    if (this.player === null) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    const uri = this.subtitleUrl.trim();
    if (uri.length === 0) {
      this.nativeStatus = '请先填写外挂字幕 URL。';
      return;
    }
    this.player.addExternalSubtitle({ uri }).then(() => {
      this.nativeStatus = `已加载外挂字幕：${uri}`;
    }).catch((e: Error) => {
      this.nativeStatus = `加载外挂字幕失败：${e.message}`;
    });
  }

  private loadExternalAudio(): void {
    if (this.player === null) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    const uri = this.externalAudioUrl.trim();
    if (uri.length === 0) {
      this.nativeStatus = '请先填写外挂音频 URL。';
      return;
    }
    this.player.addExternalAudio({ uri }).then(() => {
      this.nativeStatus = `已加载外挂音频：${uri}`;
    }).catch((e: Error) => {
      this.nativeStatus = `加载外挂音频失败：${e.message}`;
    });
  }

  private selectSubtitleTrack(track: PlayerTrack | null): void {
    if (this.player === null) {
      return;
    }
    this.player.selectTrack('subtitle', track?.id ?? null).then(() => {
      this.nativeStatus = track === null ? '已关闭字幕' : `已选择字幕 #${track.id}`;
    }).catch((e: Error) => {
      this.nativeStatus = `切换字幕失败：${e.message}`;
    });
  }

  private togglePlayback(): void {
    if (this.player === null) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    this.isPlaying = !this.isPlaying;
    if (this.isPlaying) {
      this.player.play().then(() => {
        this.nativeStatus = '播放中。';
        this.lifecycle.markPlaybackStarted(this.activePlaybackUrl);
      }).catch((e: Error) => {
        this.nativeStatus = `播放失败：${e.message}`;
      });
    } else {
      this.player.pause().then(() => {
        this.nativeStatus = '已暂停。';
        this.lifecycle.markPlaybackStopped();
      }).catch((e: Error) => {
        this.nativeStatus = `暂停失败：${e.message}`;
      });
    }
  }

  private seekBy(deltaSeconds: number): void {
    if (this.player === null) {
      this.nativeStatus = '请先加载视频。';
      return;
    }
    this.player.seekRelative(deltaSeconds).then(() => {
      this.nativeStatus = `已跳转 ${deltaSeconds}s`;
    }).catch((e: Error) => {
      this.nativeStatus = `跳转失败：${e.message}`;
    });
  }

  private stopPlayback(): void {
    if (this.player === null) {
      return;
    }
    this.player.stop().then(() => {
      this.nativeStatus = '已停止。';
      this.isPlaying = false;
      this.showVideo = false;
      this.lifecycle.markPlaybackStopped();
    }).catch((e: Error) => {
      this.nativeStatus = `停止失败：${e.message}`;
    });
  }

  private releasePlayer(): void {
    if (this.unsubscribe !== null) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
    if (this.player !== null) {
      this.player.release().then(() => {
        this.nativeStatus = '@vidall/player 已释放。';
      }).catch((e: Error) => {
        this.nativeStatus = `释放失败：${e.message}`;
      });
      this.isPlaying = false;
      this.showVideo = false;
    }
    this.lifecycle.markReleased();
  }

  private vpToPx(vp: number): number {
    return Math.round(this.getUIContext().vp2px(vp));
  }

  // 外框（letterbox 画框）尺寸变化时（初始布局、全屏切换）触发，
  // 记录外框实际 vp 尺寸并据此重新计算内部按比例居中的视频框尺寸。
  private onOuterAreaChange(newValue: Area): void {
    const width = Number(newValue.width);
    const height = Number(newValue.height);
    if (!(width > 0) || !(height > 0)) {
      return;
    }
    this.outerWidthVp = width;
    this.outerHeightVp = height;
    this.recomputeVideoBoxSize();
  }

  // 用显式计算的宽高代替 ArkUI 的 aspectRatio 自动布局：
  // aspectRatio + constraintSize 在 Stack 场景下的最终尺寸解析存在不确定性，
  // 曾观察到视频框失控放大到远超外框的尺寸（例如 3819x2148），
  // 导致原生缓冲区与 XComponent 实际渲染尺寸不匹配、画面无法正常显示（全黑）。
  // 因此改为自行按“取更小的缩放比例”算法算出确定的内框宽高，直接赋给 .width()/.height()。
  private recomputeVideoBoxSize(): void {
    const size = computeLetterboxSize(this.outerWidthVp, this.outerHeightVp, this.videoAspectRatio);
    if (size === undefined) {
      return;
    }
    this.videoBoxWidthVp = size.width;
    this.videoBoxHeightVp = size.height;
  }

  // XComponent 自身尺寸变化（跟随 videoBoxWidthVp/videoBoxHeightVp 更新）时触发，
  // 把真实像素尺寸同步给原生渲染器，使缓冲区尺寸与实际渲染尺寸保持一致。
  private onSurfaceAreaChange(newValue: Area): void {
    const width = this.vpToPx(Number(newValue.width));
    const height = this.vpToPx(Number(newValue.height));
    if (width <= 0 || height <= 0) {
      return;
    }
    this.lastKnownWidthPx = width;
    this.lastKnownHeightPx = height;
    if (this.surfaceAdapter !== null) {
      this.surfaceAdapter.onSizeChange(width, height).catch((e: Error) => {
        console.error(`VidAll_Player onSizeChange failed: ${e}`);
      });
    }
  }

  private attachSurface(): void {
    console.info(`VidAll_Player attachSurface: called`);
    const surfaceId = this.surfaceController.getXComponentSurfaceId();
    console.info(`VidAll_Player attachSurface: surfaceId = ${surfaceId}`);
    this.surfaceId = surfaceId;
    if (this.surfaceAdapter === null) {
      this.nativeStatus = 'Surface 适配器未初始化。';
      console.error(`VidAll_Player attachSurface: surfaceAdapter null`);
      return;
    }
    // 委托给 XComponentSurfaceAdapter 处理 attach/generation/尺寸校验；
    // 使用最近一次 onAreaChange 上报的真实像素尺寸而非固定值，
    // 避免原生缓冲区宽高比与实际渲染区域宽高比不一致导致画面拉伸。
    this.surfaceAdapter.onLoad(surfaceId, this.lastKnownWidthPx, this.lastKnownHeightPx).then(() => {
      this.nativeStatus = `Surface 已接入：${surfaceId}`;
      this.lifecycle.onSurfaceCreated();
      this.tryAutoPlay();
    }).catch((e: Error) => {
      this.nativeStatus = `Surface 接入失败：${e.message}`;
      console.error(`VidAll_Player attachSurface failed: ${e}`);
    });
  }

  private setPlayerError(code: string, message: string, retryable: boolean): void {
    const sanitized = this.redactSensitiveText(message);
    this.errorCode = code;
    this.errorDescription = sanitized.length > 0 ? sanitized : '播放器无法继续播放当前媒体。';
    this.errorRetryable = retryable;
  }

  private clearPlayerError(): void {
    this.errorCode = '';
    this.errorDescription = '';
    this.errorRetryable = false;
  }

  private redactSensitiveText(text: string): string {
    // 头部值可能包含多个以空格分隔的 token（如 `Basic <base64>`），
    // 需要整体脱敏到分隔符（逗号/分号/行尾），与 SDK redactText 保持一致。
    return text
      .replace(/(authorization\s*[:=]\s*)([^\s,;]+(?:[ \t]+[^\s,;]+)*)/gi, '$1[REDACTED]')
      .replace(/(password\s*[:=]\s*)([^\s,;]+(?:[ \t]+[^\s,;]+)*)/gi, '$1[REDACTED]')
      .replace(/([?&](?:access_token|apikey|api_key|auth|password|token)=[^&#\s]*)/gi, '[REDACTED_QUERY]');
  }

  private retryPlayback(): void {
    if (!this.errorRetryable) {
      return;
    }
    this.clearPlayerError();
    this.loadVideo();
  }

  private async pickLocalVideo(): Promise<void> {
    try {
      const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const result = await new picker.DocumentViewPicker(context).select();
      if (result.length === 0) {
        return;
      }
      this.url = result[0];
      this.isWebDavSource = false;
      this.nativeStatus = '已选择本地视频，请点击"加载视频"。';
    } catch (error) {
      this.setPlayerError('PICK', '无法选择本地视频文件。', false);
      console.error(`VidAll_Player local picker error: ${JSON.stringify(error)}`);
    }
  }

  onAppForegroundChanged(): void {
    if (this.player === null) {
      return;
    }
    if (this.appForeground && this.lifecycle.onForeground()) {
      this.nativeStatus = '已回到前台，正在恢复渲染。';
      this.player.play().catch((e: Error) => {
        this.nativeStatus = `恢复播放失败：${e.message}`;
      });
      return;
    }
    if (!this.appForeground && this.lifecycle.onBackground()) {
      this.nativeStatus = '应用进入后台，已暂停渲染。';
      this.player.pause().catch((e: Error) => {
        this.nativeStatus = `暂停失败：${e.message}`;
      });
    }
  }

  @Builder
  VideoStack() {
    Stack() {
      // 内层按真实视频宽高比计算出确定的宽高，在外层黑色画框内居中显示（letterbox），
      // 避免 SURFACE 类型 XComponent 在当前 API 级别下只能拉伸填满的限制。
      Stack() {
        XComponent({ id: 'mpv-video-surface', type: XComponentType.SURFACE, controller: this.surfaceController })
          .width('100%')
          .height('100%')
          .onLoad(() => {
            console.info(`VidAll_Player: XComponent onLoad fired`);
            this.attachSurface();
          })
          .onDestroy(() => {
            console.info(`VidAll_Player: XComponent onDestroy fired`);
            if (this.surfaceAdapter !== null) {
              this.surfaceAdapter.onDestroy().catch((e: Error) => {
                console.error(`VidAll_Player detachSurface failed: ${e}`);
              });
            }
            this.lifecycle.onSurfaceDestroyed();
            this.surfaceId = '';
          })
          .onAreaChange((_: Area, newValue: Area) => this.onSurfaceAreaChange(newValue))
      }
      .width(this.videoBoxWidthVp > 0 ? this.videoBoxWidthVp : '100%')
      .height(this.videoBoxHeightVp > 0 ? this.videoBoxHeightVp : '100%')

      // Status text when no video
      if (!this.showVideo) {
        Text(this.player !== null ? '正在等待视频帧...' : '点击"加载视频"开始播放')
          .fontSize(18)
          .fontColor('#D9E6F7')
      }

      if (this.isFullscreen) {
        // 退出全屏按钮默认隐藏；鼠标悬停、点击画面或按返回键都能重新显示/退出，
        // 兼顾桌面鼠标与 TV 遥控器等无鼠标输入场景。
        Button('退出全屏')
          .id('exit-fullscreen-button')
          .fontSize(16)
          .backgroundColor('#4B6C8A')
          .position({ x: 12, y: 12 })
          .opacity(this.isExitButtonVisible ? 1 : 0)
          .onClick(() => { this.isFullscreen = false; })
      }
    }
    .width(this.isFullscreen ? '100%' : '88%')
    .height(this.isFullscreen ? '100%' : 260)
    .border(this.isFullscreen ? { width: 0, radius: 0 } : { width: 2, color: '#426991', radius: 12 })
    .backgroundColor(this.isFullscreen ? '#000000' : '#07121F')
    .onAreaChange((_: Area, newValue: Area) => this.onOuterAreaChange(newValue))
    .onHover((isHover: boolean) => {
      if (this.isFullscreen && isHover) {
        this.revealExitButton();
      }
    })
    .onClick(() => {
      if (this.isFullscreen) {
        this.revealExitButton();
      }
    })
  }

  // 显示退出全屏按钮，并在 3 秒无操作后自动隐藏，避免遮挡画面。
  private revealExitButton(): void {
    this.isExitButtonVisible = true;
    if (this.exitButtonHideTimer !== undefined) {
      clearTimeout(this.exitButtonHideTimer);
    }
    this.exitButtonHideTimer = setTimeout(() => {
      this.isExitButtonVisible = false;
      this.exitButtonHideTimer = undefined;
    }, 3000);
  }

  // 按返回键时优先退出全屏，而不是直接退出应用/页面。
  onBackPress(): boolean {
    if (this.isFullscreen) {
      this.isFullscreen = false;
      return true;
    }
    return false;
  }

  build() {
    Column() {
      if (!this.isFullscreen) {
        Text('VidAll Player')
          .fontSize(36)
          .fontWeight(FontWeight.Bold)
          .fontColor('#F4F7FB')

        Text('HarmonyOS libmpv + XComponent + EGL/GLES 验证')
          .fontSize(18)
          .fontColor('#AFC6E9')
      }

      // Video display area — 常驻挂载，全屏切换只改变尺寸而不销毁重建 XComponent，
      // 避免反复 attach/detach 原生 Surface 导致画面无法恢复（黑屏）。
      this.VideoStack()

      // 调试字幕条：展示原生 "sub-text" 上报的当前字幕纯文本，最多两行，
      // 独立于软件渲染合成管线是否把字幕像素画进视频帧，用于验证字幕解析
      // 是否生效（而非依赖肉眼在画面里辨认字幕像素）。
      if (this.subtitleText.length > 0) {
        Text(this.subtitleText)
          .id('subtitle-debug-text')
          .fontSize(16)
          .fontColor('#F4F7FB')
          .backgroundColor('#000000')
          .opacity(0.72)
          .padding({ left: 12, right: 12, top: 6, bottom: 6 })
          .borderRadius(6)
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .textAlign(TextAlign.Center)
          .margin({ top: 6 })
          .width(this.isFullscreen ? '80%' : '88%')
      }

      if (!this.isFullscreen) {
        Scroll() {
          Column({ space: 16 }) {
          // 播放控制栏：紧贴视频画面，方便操作
          Row({ space: 10 }) {
            Button(this.isPlaying ? '暂停' : '播放')
              .id('toggle-playback-button')
              .fontSize(16)
              .backgroundColor('#1A9A78')
              .enabled(this.player !== null)
              .onClick(() => this.togglePlayback())

        Button('快退 10s')
          .id('seek-backward-button')
          .fontSize(16)
          .backgroundColor('#4B6C8A')
          .enabled(this.player !== null)
          .onClick(() => this.seekBy(-10))

        Button('快进 10s')
          .id('seek-forward-button')
          .fontSize(16)
          .backgroundColor('#4B6C8A')
          .enabled(this.player !== null)
          .onClick(() => this.seekBy(10))

        Button('停止')
          .id('stop-video-button')
          .fontSize(16)
          .backgroundColor('#9B6A2F')
          .enabled(this.player !== null)
          .onClick(() => this.stopPlayback())

        Button('全屏')
          .id('toggle-fullscreen-button')
          .fontSize(16)
          .backgroundColor('#5B4B8A')
          .enabled(this.showVideo)
          .onClick(() => { this.isFullscreen = true; })
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
            .enabled(this.player !== null)
            .backgroundColor('#2F7DE1')
            .onClick(() => {
              // 轨道列表由事件驱动；此处仅提示用户当前状态。
              if (this.audioTracks.length === 0 && this.subtitleTracks.length === 0) {
                this.nativeStatus = '暂无轨道信息。加载媒体后会通过事件自动刷新。';
              } else {
                this.nativeStatus = `当前音轨 ${this.audioTracks.length} 条，字幕 ${this.subtitleTracks.length} 条。`;
              }
            })
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
            ForEach(this.audioTracks, (track: PlayerTrack) => {
              Button(trackLabel(track))
                .id(`audio-track-${track.id}`)
                .fontSize(15)
                .backgroundColor(track.selected ? '#1A9A78' : '#315473')
                .onClick(() => this.selectAudioTrack(track))
            }, (track: PlayerTrack) => `audio-${track.id}-${track.selected}`)
          }
          .width('100%')
          Text('字幕')
            .fontSize(16)
            .fontColor('#AFC6E9')
          Row({ space: 8 }) {
            Button('关闭字幕')
              .id('subtitle-track-off')
              .fontSize(15)
              .backgroundColor(this.subtitleTracks.every((track: PlayerTrack) => !track.selected) ? '#9B6A2F' : '#315473')
              .onClick(() => this.selectSubtitleTrack(null))
            ForEach(this.subtitleTracks, (track: PlayerTrack) => {
              Button(trackLabel(track))
                .id(`subtitle-track-${track.id}`)
                .fontSize(15)
                .backgroundColor(track.selected ? '#1A9A78' : '#315473')
                .onClick(() => this.selectSubtitleTrack(track))
            }, (track: PlayerTrack) => `subtitle-${track.id}-${track.selected}`)
          }
          .width('100%')
        }
      }
      .width('88%')
      .padding(12)
      .border({ width: 1, color: '#426991', radius: 10 })
      .backgroundColor('#0C1A2A')

      TextInput({ text: this.url, placeholder: '输入视频 URL（HTTP/HTTPS、HLS .m3u8、DASH .mpd 或 smb://…）' })
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
          .enabled(this.player !== null && this.subtitleUrl.trim().length > 0)
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
          .enabled(this.player !== null && this.externalAudioUrl.trim().length > 0)
          .backgroundColor('#2F7DE1')
          .onClick(() => this.loadExternalAudio())
      }
      .width('88%')

      Column({ space: 8 }) {
        Text('SMB 直连媒体')
          .fontSize(20)
          .fontWeight(FontWeight.Medium)
          .fontColor('#DDE8F8')
          .width('100%')
        Text('填写服务器、共享和文件路径。地址不会包含用户名或密码；密码只保留在当前会话且不会保存。')
          .fontSize(14)
          .fontColor('#AFC6E9')
          .width('100%')
        Row({ space: 8 }) {
          TextInput({ text: this.smbHost, placeholder: '服务器，例如 192.168.1.10' })
            .layoutWeight(1)
            .onChange((value: string) => this.smbHost = value)
          TextInput({ text: this.smbShare, placeholder: '共享名，例如 Media' })
            .layoutWeight(1)
            .onChange((value: string) => this.smbShare = value)
        }
        TextInput({ text: this.smbPath, placeholder: '视频路径，例如 Movies/movie.mkv（可选）' })
          .width('100%')
          .onChange((value: string) => this.smbPath = value)
        Row({ space: 8 }) {
          TextInput({ text: this.smbUsername, placeholder: '用户名（认证共享需要）' })
            .layoutWeight(1)
            .onChange((value: string) => this.smbUsername = value)
          TextInput({ text: this.smbPassword, placeholder: '密码（仅当前会话）' })
            .layoutWeight(1)
            .type(InputType.Password)
            .onChange((value: string) => this.smbPassword = value)
        }
        Row({ space: 8 }) {
          Button('保存 SMB 配置')
            .id('save-smb-config-button')
            .layoutWeight(1)
            .backgroundColor('#31577F')
            .onClick(() => this.saveSmbConfig())
          Button('配置并加载 SMB')
            .id('configure-smb-button')
            .layoutWeight(1)
            .backgroundColor('#2F7DE1')
            .onClick(() => this.loadSmbVideo())
        }
        if (this.smbConfigStatus.length > 0) {
          Text(this.smbConfigStatus)
            .id('smb-config-status')
            .fontSize(14)
            .fontColor('#B8F4D9')
            .width('100%')
        }
        if (this.currentMediaKind === 'smb' && this.url.length > 0) {
          Text(`SMB 地址: ${this.url}`)
            .fontSize(13)
            .fontColor('#8FA7C5')
            .maxLines(1)
        }
      }
      .width('88%')
      .padding(12)
      .border({ width: 1, color: '#426991', radius: 10 })
      .backgroundColor('#0C1A2A')

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
            if (this.player !== null) {
              this.nativeStatus = '@vidall/player 会话已创建。';
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
    .layoutWeight(1)
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#102033')
  }
}