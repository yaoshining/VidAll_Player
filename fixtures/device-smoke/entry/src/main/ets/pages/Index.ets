import { common } from '@kit.AbilityKit';
import { SmokeSession } from '../smoke/SmokeSession';
import { PlatformPort } from '../smoke/PlatformPort';
import { LaunchSession } from '../smoke/LaunchSession';
@Entry
@Component
struct Index {
  @State status: string = '专用短测：等待受控会话';
  private controller: XComponentController = new XComponentController();
  private started: boolean = false;
  private session?: SmokeSession;
  private port?: PlatformPort;
  private async start(): Promise<void> {
    if (this.started || !LaunchSession.opened) return;
    this.started = true;
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    const port = new PlatformPort(context, this.controller.getXComponentSurfaceId()); this.port = port;
    const session = new SmokeSession(port, 120000, 3000); this.session = session;
    try { const result = await session.run(); this.status = result.passed ? '短测完成，保屏已释放' : '短测未通过，待审查'; }
    catch (_) { LaunchSession.journal?.record('session-failed', 0, 'UNEXPECTED_FAILURE'); this.status = '短测异常'; }
    finally { port.dispose(); }
  }
  aboutToDisappear(): void { this.session?.cancel(); }
  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      XComponent({ id: 'device-smoke-video', type: XComponentType.SURFACE, controller: this.controller })
        .width('100%').height('100%').onLoad(() => { this.start(); })
      Text(this.status).fontSize(24).fontColor(Color.White).backgroundColor('#88000000').padding(16)
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
