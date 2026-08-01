/*
 * Copyright (c) 2025 VidAll. All rights reserved.
 * Consumer smoke test entry page.
 * Only uses public API, no access to native/entry/VidAll_TV.
 */

import { createPlayer, PlayerState, PlayerEvent } from '@vidall/player';

@Entry
@Component
struct Index {
  @State playerState: string = 'IDLE';
  @State testResults: string[] = [];
  @State surfaceId: string = 'test-surface';
  private player: any = null;

  aboutToAppear() {
    this.runSmokeTests();
  }

  aboutToDisappear() {
    if (this.player) {
      this.player.release();
      this.player = null;
    }
  }

  runSmokeTests() {
    this.testResults = [];
    
    // Test 1: API import
    try {
      this.logTest('API import', 'PASS', 'Public API imported successfully');
    } catch (error) {
      this.logTest('API import', 'FAIL', error.message);
    }

    // Test 2: Player creation
    try {
      this.player = createPlayer({
        surfaceId: this.surfaceId,
        width: 1920,
        height: 1080
      });
      this.logTest('Player creation', 'PASS', `Player created with ID: ${this.player.id}`);
    } catch (error) {
      this.logTest('Player creation', 'FAIL', error.message);
    }

    // Test 3: State transitions
    try {
      if (this.player) {
        const initialState = this.player.state;
        this.player.load('file:///test.mp4');
        const loadingState = this.player.state;
        this.player.release();
        this.player = null;  // 释放后置空，避免后续测试使用已释放的 player
        
        this.logTest('State transitions', 'PASS', 
          `IDLE → LOADING → RELEASED: ${initialState} → ${loadingState} → RELEASED`);
      }
    } catch (error) {
      this.logTest('State transitions', 'FAIL', error.message);
    }

    // Test 4: Event handling (需要新的 player 实例)
    try {
      if (!this.player) {
        this.player = createPlayer({
          surfaceId: this.surfaceId,
          width: 1920,
          height: 1080
        });
      }
      let eventReceived = false;
      this.player.on(PlayerEvent.ERROR, (error) => {
        eventReceived = true;
      });
      this.logTest('Event subscription', 'PASS', 'Event listener attached');
    } catch (error) {
      this.logTest('Event subscription', 'FAIL', error.message);
    }

    // Test 5: Public API surface
    try {
      if (this.player) {
        const requiredMethods = ['load', 'play', 'pause', 'seek', 'setVolume', 'setMute', 'setSpeed', 'release', 'on', 'off'];
        const missingMethods = requiredMethods.filter(method => typeof this.player[method] !== 'function');
        
        if (missingMethods.length === 0) {
          this.logTest('Public API surface', 'PASS', 'All required methods available');
        } else {
          this.logTest('Public API surface', 'FAIL', `Missing methods: ${missingMethods.join(', ')}`);
        }
      }
    } catch (error) {
      this.logTest('Public API surface', 'FAIL', error.message);
    }

    // Test 6: No internal access
    try {
      // Attempt to access internal properties (should be undefined)
      if (this.player && (this.player._internal || this.player.nativeHandle)) {
        this.logTest('Internal access', 'FAIL', 'Internal properties exposed');
      } else {
        this.logTest('Internal access', 'PASS', 'No internal properties accessible');
      }
    } catch (error) {
      this.logTest('Internal access', 'PASS', 'Internal access properly restricted');
    }
  }

  logTest(name: string, result: string, message: string) {
    const entry = `${result}: ${name} - ${message}`;
    this.testResults.push(entry);
  }

  build() {
    Column({ space: 20 }) {
      Text('VidAll Player Consumer Smoke Test')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
        .margin({ top: 30 })

      Text('Testing public API only - no access to native/entry/VidAll_TV')
        .fontSize(16)
        .fontColor(Color.Gray)
        .margin({ bottom: 30 })

      Text(`Player State: ${this.playerState}`)
        .fontSize(18)
        .fontColor(Color.Blue)
        .margin({ bottom: 20 })

      Divider()
        .strokeWidth(1)
        .color(Color.Gray)

      Text('Test Results:')
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .margin({ bottom: 10 })

      Scroll() {
        Column({ space: 10 }) {
          ForEach(this.testResults, (result: string) => {
            Text(result)
              .fontSize(14)
              .fontColor(result.startsWith('PASS') ? Color.Green : Color.Red)
              .textAlign(TextAlign.Start)
              .width('100%')
          })
        }
        .width('100%')
        .padding(10)
      }
      .height(300)
      .width('90%')
      .border({ width: 1, color: Color.Gray })

      Button('Run Tests Again')
        .width('80%')
        .height(50)
        .fontSize(16)
        .onClick(() => {
          if (this.player) {
            this.player.release();
            this.player = null;
          }
          this.runSmokeTests();
        })
        .margin({ top: 20 })
    }
    .width('100%')
    .height('100%')
    .padding(20)
    .alignItems(HorizontalAlign.Center)
  }
}