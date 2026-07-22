import { abilityDelegatorRegistry, TestRunner } from '@kit.TestKit';
import { Want } from '@kit.AbilityKit';

export default class OpenHarmonyTestRunner implements TestRunner {
  onPrepare(): void {}

  onRun(): void {
    const testArguments = abilityDelegatorRegistry.getArguments();
    const want: Want = {
      bundleName: testArguments.bundleName,
      abilityName: 'TestAbility',
      moduleName: 'entry_test'
    };
    try {
      abilityDelegatorRegistry.getAbilityDelegator().startAbility(want);
    } catch (error) {
      console.error(`无法启动 Hypium 测试 Ability: ${error}`);
    }
  }
}
