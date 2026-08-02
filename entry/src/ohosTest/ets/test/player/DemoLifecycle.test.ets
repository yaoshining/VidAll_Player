import { describe, expect, it } from '@ohos/hypium';
import { DemoLifecycleController } from '../../../main/ets/player/DemoLifecycle';

export default function demoLifecycleTest(): void {
  describe('DemoLifecycleTest', () => {
    it('resumes only after a recreated surface remains foregrounded', 0, () => {
      const lifecycle = new DemoLifecycleController();
      lifecycle.markPlaybackStarted('https://example.com/first.mp4');
      expect(lifecycle.onSurfaceDestroyed()).assertTrue();
      expect(lifecycle.onSurfaceCreated()).assertTrue();
      expect(lifecycle.getState()).assertEqual('playing');
    });

    it('resumes after background then surface destroyed then foreground with recreated surface', 0, () => {
      const lifecycle = new DemoLifecycleController();
      lifecycle.markPlaybackStarted('https://example.com/movie.mp4');
      expect(lifecycle.onBackground()).assertTrue();
      expect(lifecycle.onSurfaceDestroyed()).assertTrue();
      // Surface recreated while still in background must not auto-resume.
      expect(lifecycle.onSurfaceCreated()).assertFalse();
      // Coming to foreground resumes because the surface is present.
      expect(lifecycle.onForeground()).assertTrue();
      expect(lifecycle.getState()).assertEqual('playing');
    });

    it('switches sources, handles background and waits for both foreground and network recovery', 0, () => {
      const lifecycle = new DemoLifecycleController();
      lifecycle.markPlaybackStarted('https://example.com/first.mp4');
      lifecycle.markPlaybackStarted('https://example.com/second.mp4');
      expect(lifecycle.getActiveSource()).assertEqual('https://example.com/second.mp4');
      expect(lifecycle.onBackground()).assertTrue();
      expect(lifecycle.onNetworkLost()).assertTrue();
      // A recovery event in background enables the later foreground resume.
      expect(lifecycle.onNetworkRecovered()).assertFalse();
      expect(lifecycle.onForeground()).assertTrue();
      expect(lifecycle.getState()).assertEqual('playing');
    });

    it('does not resume a detached or released player after recovery callbacks', 0, () => {
      const lifecycle = new DemoLifecycleController();
      lifecycle.markPlaybackStarted('https://example.com/movie.mp4');
      lifecycle.onSurfaceDestroyed();
      lifecycle.onNetworkLost();
      expect(lifecycle.onNetworkRecovered()).assertFalse();
      lifecycle.markReleased();
      expect(lifecycle.onForeground()).assertFalse();
      expect(lifecycle.onSurfaceCreated()).assertFalse();
      expect(lifecycle.getState()).assertEqual('released');
    });

    it('makes release idempotent and clamps focus at list boundaries', 0, () => {
      const lifecycle = new DemoLifecycleController();
      lifecycle.markPlaybackStarted('https://example.com/movie.mp4');
      lifecycle.markReleased();
      lifecycle.markReleased();
      expect(lifecycle.getState()).assertEqual('released');
      expect(lifecycle.moveFocus(0, 100, -1)).assertEqual(0);
      expect(lifecycle.moveFocus(99, 100, 1)).assertEqual(99);
      expect(lifecycle.moveFocus(-1, 0, 1)).assertEqual(-1);
    });
  });
}
