import { describe, expect, it } from '@ohos/hypium';
import { computeLetterboxSize } from '../../../main/ets/player/videoLetterbox';

// 覆盖视频 letterbox（按比例居中）尺寸计算的纯函数逻辑。
// 背景：曾用 ArkUI `.aspectRatio()` + `.constraintSize()` 自动布局，
// 但在 Stack 场景下尺寸解析不稳定（观察到失控放大到远超外框），
// 因此改为由业务代码显式计算确定宽高，这里对该纯函数做回归测试。
export default function videoLetterboxTest(): void {
  describe('VideoLetterboxTest', () => {
    it('fits video by height when outer frame is wider than the video', 0, () => {
      // 外框 16:9，视频 4:3（比外框「窄」）：应以外框高度为基准，左右留黑边。
      const size = computeLetterboxSize(1600, 900, 4 / 3);
      expect(size !== undefined).assertTrue();
      expect(size!.height).assertEqual(900);
      expect(size!.width).assertEqual(1200);
    });

    it('fits video by width when outer frame is narrower than the video', 0, () => {
      // 外框 4:3，视频 16:9（比外框「宽」）：应以外框宽度为基准，上下留黑边。
      const size = computeLetterboxSize(800, 800, 16 / 9);
      expect(size !== undefined).assertTrue();
      expect(size!.width).assertEqual(800);
      expect(size!.height).assertEqual(450);
    });

    it('fills the outer frame exactly when aspect ratios match', 0, () => {
      const size = computeLetterboxSize(1280, 720, 16 / 9);
      expect(size !== undefined).assertTrue();
      expect(size!.width).assertEqual(1280);
      expect(size!.height).assertEqual(720);
    });

    it('never exceeds the outer frame bounds even for extreme aspect ratios', 0, () => {
      // 回归测试：曾出现内框失控放大到远超外框（如 3819x2148）的问题，
      // 这里验证极端宽高比下计算结果始终被限制在外框范围内。
      const wide = computeLetterboxSize(1000, 1000, 21 / 9);
      expect(wide !== undefined).assertTrue();
      expect(wide!.width <= 1000).assertTrue();
      expect(wide!.height <= 1000).assertTrue();

      const tall = computeLetterboxSize(1000, 1000, 9 / 21);
      expect(tall !== undefined).assertTrue();
      expect(tall!.width <= 1000).assertTrue();
      expect(tall!.height <= 1000).assertTrue();
    });

    it('returns undefined for invalid or non-positive inputs', 0, () => {
      expect(computeLetterboxSize(0, 900, 16 / 9)).assertEqual(undefined);
      expect(computeLetterboxSize(1600, 0, 16 / 9)).assertEqual(undefined);
      expect(computeLetterboxSize(1600, 900, 0)).assertEqual(undefined);
      expect(computeLetterboxSize(-1, 900, 16 / 9)).assertEqual(undefined);
    });

    it('rounds down fractional sizes and never returns zero', 0, () => {
      // 极小外框下取整仍应保证最小值为 1，避免出现 0 宽/高。
      const size = computeLetterboxSize(3, 100, 16 / 9);
      expect(size !== undefined).assertTrue();
      expect(size!.width).assertEqual(3);
      expect(size!.height >= 1).assertTrue();
    });
  });
}
