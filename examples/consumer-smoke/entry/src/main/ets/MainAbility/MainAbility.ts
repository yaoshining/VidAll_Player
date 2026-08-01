/*
 * Copyright (c) 2025 VidAll. All rights reserved.
 * Main ability for consumer smoke test.
 */

import UIAbility from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';

export default class MainAbility extends UIAbility {
  onCreate(want, launchParam) {
    console.info('[ConsumerSmoke] MainAbility onCreate');
  }

  onDestroy() {
    console.info('[ConsumerSmoke] MainAbility onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage) {
    console.info('[ConsumerSmoke] MainAbility onWindowStageCreate');

    windowStage.loadContent('pages/Index', (err, data) => {
      if (err.code) {
        console.error(`[ConsumerSmoke] Failed to load the content. Cause: ${JSON.stringify(err)}`);
        return;
      }
      console.info('[ConsumerSmoke] Succeeded in loading the content.');
    });
  }

  onWindowStageDestroy() {
    console.info('[ConsumerSmoke] MainAbility onWindowStageDestroy');
  }

  onForeground() {
    console.info('[ConsumerSmoke] MainAbility onForeground');
  }

  onBackground() {
    console.info('[ConsumerSmoke] MainAbility onBackground');
  }
}