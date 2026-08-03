import { createPlayer, VidAllPlayer, VidAllPlayerSurfaceTarget, XComponentSurfaceAdapter } from '@vidall/player';

function describeFailure(error: Error): string {
  return error instanceof Error ? error.message : '未知错误';
}

@Entry
@Component
struct Index {
  private readonly surfaceController: XComponentController = new XComponentController();
  @State status: string = '正在创建受控 native 会话...';
  private player?: VidAllPlayer;
  private surfaceAdapter?: XComponentSurfaceAdapter;

  aboutToAppear(): void {
    try {
      this.player = createPlayer();
      this.surfaceAdapter = new XComponentSurfaceAdapter(new VidAllPlayerSurfaceTarget(this.player));
      this.status = '会话已创建，正在等待 XComponent Surface。模拟器仅用于开发期生命周期验证，不代表真实播放或首帧。';
    } catch (error) {
      this.status = `创建被拒绝：${describeFailure(error)}`;
    }
  }

  aboutToDisappear(): void {
    if (this.player !== undefined) {
      void this.player.release();
      this.player = undefined;
      this.surfaceAdapter = undefined;
    }
  }

  private attachSurface(): void {
    const adapter = this.surfaceAdapter;
    if (adapter === undefined) {
      return;
    }
    const surfaceId = this.surfaceController.getXComponentSurfaceId();
    adapter.onLoad(surfaceId, 1280, 720).then(() => {
      this.status = 'Surface 已附着。该结果仅用于开发期 attach/detach 回归。';
    }).catch((error: Error) => {
      this.status = `Surface 附着被拒绝：${describeFailure(error)}`;
    });
  }

  private detachSurface(): void {
    const adapter = this.surfaceAdapter;
    if (adapter !== undefined) {
      void adapter.onDestroy();
    }
  }

  build() {
    Column({ space: 24 }) {
      Text('libmpv HAR XComponent 生命周期验证')
        .fontSize(30)
        .fontWeight(FontWeight.Bold)
      XComponent({ id: 'fixture-player-surface', type: XComponentType.SURFACE, controller: this.surfaceController })
        .width('90%')
        .height(280)
        .backgroundColor('#111111')
        .onLoad(() => this.attachSurface())
        .onDestroy(() => this.detachSurface())
      Text(this.status)
        .fontSize(18)
        .textAlign(TextAlign.Center)
      Button('释放会话')
        .onClick(() => {
          if (this.player === undefined) {
            this.status = '没有可释放的会话。';
            return;
          }
          this.player.release().then(() => {
            this.status = '会话已释放。';
            this.player = undefined;
          }).catch((error: Error) => {
            this.status = `释放失败：${describeFailure(error)}`;
          });
        })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .padding(48)
  }
}
