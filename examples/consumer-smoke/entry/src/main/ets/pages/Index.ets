/* Copyright (c) 2025 VidAll. All rights reserved. */

import { createPlayer, VidAllPlayer, PlayerEvent, PlayerSurface, MediaSource } from '@vidall/player';

@Entry
@Component
struct Index {
  @State results: string[] = [];
  private player: VidAllPlayer | undefined;

  aboutToAppear() {
    this.runSmoke();
  }

  aboutToDisappear() {
    this.releasePlayer();
  }

  private async runSmoke(): Promise<void> {
    this.results = [];
    this.releasePlayer();
    try {
      const player = createPlayer();
      const unsubscribe = player.subscribe((event: PlayerEvent) => {
        this.addResult(`事件: ${event.type}`);
      });
      const surface: PlayerSurface = { componentId: 'consumer-smoke-surface', generation: 1, width: 1920, height: 1080 };
      const source: MediaSource = { kind: 'localFile', uri: 'file:///data/test.mp4' };
      await player.attachSurface(surface);
      await player.load(source);
      unsubscribe();
      await player.release();
      this.player = createPlayer();
      this.addResult('PASS: 公开 API、订阅和释放后重建均可调用');
    } catch (error) {
      this.addResult(`FAIL: ${error.message}`);
    }
  }

  private releasePlayer(): void {
    if (this.player) {
      this.player.release();
      this.player = undefined;
    }
  }

  private addResult(result: string): void {
    this.results.push(result);
  }

  build() {
    Column({ space: 16 }) {
      Text('VidAll Player Consumer Smoke')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('候选 HAR 的公开 API 验证')
        .fontSize(16)
        .fontColor(Color.Gray)
      ForEach(this.results, (result: string) => {
        Text(result).fontSize(14).fontColor(result.startsWith('PASS') ? Color.Green : Color.Red)
      })
      Button('重新运行').onClick(() => { this.runSmoke(); })
    }
    .width('100%')
    .height('100%')
    .padding(20)
  }
}
