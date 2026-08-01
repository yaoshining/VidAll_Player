/* Copyright (c) 2025 VidAll. All rights reserved. */

import { createPlayer, VidAllPlayer, PlayerEvent, PlayerSurface, MediaSource } from '@vidall/player';

@Entry
@Component
struct Index {
  @State results: string[] = [];
  @State running: boolean = false;
  private player: VidAllPlayer | undefined;
  private unsubscribe: (() => void) | undefined;

  aboutToAppear() {
    this.runSmoke();
  }

  aboutToDisappear() {
    this.releasePlayer();
  }

  private async runSmoke(): Promise<void> {
    if (this.running) {
      return;
    }
    this.running = true;
    this.results = [];
    await this.releasePlayer();
    try {
      this.player = createPlayer();
      this.unsubscribe = this.player.subscribe((event: PlayerEvent) => {
        this.addResult(`事件: ${event.type}`);
      });
      const surface: PlayerSurface = { componentId: 'consumer-smoke-surface', generation: 1, width: 1920, height: 1080 };
      const source: MediaSource = { kind: 'localFile', uri: 'file:///data/test.mp4' };
      await this.player.attachSurface(surface);
      await this.player.load(source);
      await this.player.play();
      this.addResult('PASS: 公开 API、播放调用和订阅均可调用');
    } catch (error) {
      this.addResult(`FAIL: ${error.message}`);
    } finally {
      await this.releasePlayer();
      this.player = createPlayer();
      this.addResult('PASS: 释放后可重建播放器');
      this.running = false;
    }
  }

  private async releasePlayer(): Promise<void> {
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    const player = this.player;
    if (player) {
      await player.release();
      if (this.player === player) {
        this.player = undefined;
      }
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
        Text(result).fontSize(14).fontColor(result.startsWith('PASS') ? Color.Green : result.startsWith('FAIL:') ? Color.Red : Color.Gray)
      })
      Button(this.running ? '运行中...' : '重新运行')
        .enabled(!this.running)
        .onClick(() => { this.runSmoke(); })
    }
    .width('100%')
    .height('100%')
    .padding(20)
  }
}
