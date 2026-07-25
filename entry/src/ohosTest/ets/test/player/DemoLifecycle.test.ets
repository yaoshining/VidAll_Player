import { describe, expect, it } from '@ohos/hypium';
import { DemoLifecycleController } from '../../../../main/ets/player/DemoLifecycle';

export default function demoLifecycleTest() {
  describe('DemoLifecycleTest', () => {
    it('resumes an active source after a Surface is recreated', 0, () => {
      const controller = new DemoLifecycleController();
      controller.markPlaybackStarted('https://example.com/one.mp4');
      expect(controller.onSurfaceDestroyed()).assertTrue();
      expect(controller.onSurfaceCreated()).assertTrue();
    });

    it('pauses rendering in background and resumes only active playback', 0, () => {
      const controller = new DemoLifecycleController();
      controller.markPlaybackStarted('https://example.com/one.mp4');
      expect(controller.onBackground()).assertTrue();
      expect(controller.onSurfaceCreated()).assertFalse();
      expect(controller.onForeground()).assertTrue();
      controller.markPlaybackStopped();
      expect(controller.onBackground()).assertFalse();
      expect(controller.onForeground()).assertFalse();
    });

    it('keeps the latest rapid source and clears it after release', 0, () => {
      const controller = new DemoLifecycleController();
      for (let index = 0; index < 5; index++) {
        controller.markPlaybackStarted(`https://example.com/${index}.mp4`);
      }
      expect(controller.getActiveSource()).assertEqual('https://example.com/4.mp4');
      controller.markReleased();
      expect(controller.getActiveSource()).assertEqual('');
      expect(controller.onSurfaceCreated()).assertFalse();
    });

    it('preserves the loaded source when playback resumes after URL editing', 0, () => {
      const controller = new DemoLifecycleController();
      controller.markPlaybackStarted('https://example.com/loaded.mp4');
      controller.markPlaybackStopped();
      controller.markPlaybackStarted('');
      expect(controller.getActiveSource()).assertEqual('https://example.com/loaded.mp4');
      expect(controller.onBackground()).assertTrue();
      expect(controller.onForeground()).assertTrue();
    });

    it('does not request a Surface recovery after playback is stopped', 0, () => {
      const controller = new DemoLifecycleController();
      controller.markPlaybackStarted('https://example.com/one.mp4');
      controller.markPlaybackStopped();
      expect(controller.onSurfaceDestroyed()).assertFalse();
      expect(controller.onSurfaceCreated()).assertFalse();
    });

    it('keeps background state from resuming while the Surface is detached', 0, () => {
      const controller = new DemoLifecycleController();
      controller.markPlaybackStarted('https://example.com/one.mp4');
      expect(controller.onSurfaceDestroyed()).assertTrue();
      expect(controller.onBackground()).assertTrue();
      expect(controller.onForeground()).assertFalse();
    });

    it('wraps TV focus navigation at list boundaries', 0, () => {
      const controller = new DemoLifecycleController();
      expect(controller.moveFocus(0, 3, -1)).assertEqual(2);
      expect(controller.moveFocus(2, 3, 1)).assertEqual(0);
      expect(controller.moveFocus(0, 0, 1)).assertEqual(-1);
    });
  });
}
