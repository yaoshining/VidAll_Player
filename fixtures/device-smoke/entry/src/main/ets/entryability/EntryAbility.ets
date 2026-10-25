import { UIAbility, Want, AbilityConstant } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { LaunchSession } from '../smoke/LaunchSession';
export default class EntryAbility extends UIAbility {
  private valid: boolean = false;
  onCreate(want: Want, launch: AbilityConstant.LaunchParam): void {
    try {
      const nonce = want.parameters?.sessionNonce;
      const mode = want.parameters?.mode;
      const expectedSHA = want.parameters?.expectedUnsignedHapSHA256;
      if (typeof nonce !== 'string' || typeof mode !== 'string' || typeof expectedSHA !== 'string') throw new Error('INVALID_LAUNCH');
      LaunchSession.start(this.context, nonce, mode, expectedSHA); this.valid = true;
    } catch (_) { console.error('VIDALL_DEVICE_PROBE launch rejected'); this.context.terminateSelf(); }
  }
  onNewWant(want: Want, launch: AbilityConstant.LaunchParam): void {
    // 同一进程不能注入下一会话；外部执行器必须完成卸载/清理再发起新事务。
    LaunchSession.journal?.record('session-failed', 0, 'REPEATED_LAUNCH');
    this.context.terminateSelf();
  }
  onWindowStageCreate(stage: window.WindowStage): void {
    if (!this.valid) return;
    stage.loadContent('pages/Index', (error) => {
      if (error.code) { LaunchSession.journal?.record('session-failed', 0, 'CONTENT_LOAD_FAILED'); this.context.terminateSelf(); }
    });
  }
  onBackground(): void { LaunchSession.journal?.record('ability-background', 0, 'observed'); }
  onForeground(): void { LaunchSession.journal?.record('ability-foreground', 0, 'observed'); }
}
