@Entry
@Component
struct Index {
  @State startupMessage: string = '正在初始化播放器 SDK 骨架…';
  @State startupTime: string = '';

  aboutToAppear(): void {
    this.startupTime = new Date().toLocaleTimeString();
    this.startupMessage = '应用已启动；libmpv 原生构建尚未接入示例。';
    console.info(`VidAll_Player 启动完成，时间：${this.startupTime}`);
  }

  build() {
    Column({ space: 20 }) {
      Text('VidAll Player')
        .fontSize(42)
        .fontWeight(FontWeight.Bold)
        .fontColor('#F4F7FB')

      Text('HarmonyOS libmpv 播放 SDK')
        .fontSize(24)
        .fontColor('#AFC6E9')

      Divider()
        .color('#3B506D')
        .width('72%')

      Text(this.startupMessage)
        .fontSize(20)
        .fontColor('#DDE8F8')
        .textAlign(TextAlign.Center)

      Text(`启动时间：${this.startupTime}`)
        .fontSize(16)
        .fontColor('#8FA7C5')

      Button('输出启动日志')
        .id('startup-log-button')
        .fontSize(20)
        .backgroundColor('#2F7DE1')
        .onClick(() => {
          console.info('VidAll_Player 用户确认：初始应用界面可用。');
          this.startupMessage = '启动日志已输出；下一步接入 WebDAV 与 libmpv。';
        })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor('#102033')
    .padding(36)
  }
}
