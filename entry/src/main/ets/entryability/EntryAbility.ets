import { AbilityConstant, ConfigurationConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';

const DOMAIN = 0x4D50;
const TAG = 'VidAllPlayer';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch (err) {
      hilog.error(DOMAIN, TAG, '设置颜色模式失败：%{public}s', JSON.stringify(err));
    }
    hilog.info(DOMAIN, TAG, 'VidAll_Player 应用已创建。');
  }

  onDestroy(): void {
    hilog.info(DOMAIN, TAG, 'VidAll_Player 应用已销毁。');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    hilog.info(DOMAIN, TAG, '主窗口已创建，正在加载初始界面。');
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(DOMAIN, TAG, '加载初始界面失败：%{public}s', JSON.stringify(err));
        return;
      }
      hilog.info(DOMAIN, TAG, '初始界面加载完成。');
    });
  }

  onWindowStageDestroy(): void {
    hilog.info(DOMAIN, TAG, '主窗口已销毁。');
  }

  onForeground(): void {
    AppStorage.SetOrCreate('vidallAppForeground', true);
    hilog.info(DOMAIN, TAG, '应用进入前台。');
  }

  onBackground(): void {
    AppStorage.SetOrCreate('vidallAppForeground', false);
    hilog.info(DOMAIN, TAG, '应用进入后台。');
  }
}
