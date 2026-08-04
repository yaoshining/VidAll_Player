import { PlayerSurface } from '@vidall/player';
import { PlayerSurfaceTarget, XComponentSurfaceAdapter } from '../../src/xcomponent/surfaceAdapter';

interface Call {
  kind: 'attach' | 'resize' | 'detach';
  generation: number;
  width?: number;
  height?: number;
}

class RecordingSurfaceTarget extends PlayerSurfaceTarget {
  readonly calls: Call[] = [];

  attachSurface(surface: PlayerSurface): Promise<void> {
    this.calls.push({ kind: 'attach', generation: surface.generation, width: surface.width, height: surface.height });
    return Promise.resolve();
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    this.calls.push({ kind: 'resize', generation: surface.generation, width: surface.width, height: surface.height });
    return Promise.resolve();
  }

  detachSurface(generation: number): Promise<void> {
    this.calls.push({ kind: 'detach', generation: generation });
    return Promise.resolve();
  }

}

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function expectFailure(operation: () => Promise<void>, code: string): Promise<void> {
  try {
    return operation().then(() => {
      throw new Error(`Expected ${code}.`);
    }).catch((error: Error & { playerError?: { code?: string } }) => {
      assert(error.playerError?.code === code, `Expected ${code}.`);
    });
  } catch (error) {
    const failure = error as Error & { playerError?: { code?: string } };
    assert(failure.playerError?.code === code, `Expected ${code}.`);
    return Promise.resolve();
  }
}

export async function xcomponentLoadResizeDestroyUsesCurrentGeneration(): Promise<void> {
  const target = new RecordingSurfaceTarget();
  const adapter = new XComponentSurfaceAdapter(target);

  await adapter.onLoad('player-surface', 1280, 720);
  await adapter.onSizeChange(1920, 1080);
  await adapter.onDestroy();

  assert(target.calls.length === 3, 'Expected attach, resize, and detach calls.');
  assert(target.calls[0].kind === 'attach' && target.calls[0].generation === 1, 'Load must attach generation 1.');
  assert(target.calls[1].kind === 'resize' && target.calls[1].generation === 1, 'Resize must target generation 1.');
  assert(target.calls[2].kind === 'detach' && target.calls[2].generation === 1, 'Destroy must detach generation 1.');
}

export async function xcomponentRebuildIgnoresStaleDestroy(): Promise<void> {
  const target = new RecordingSurfaceTarget();
  const adapter = new XComponentSurfaceAdapter(target);

  await adapter.onLoad('player-surface', 1280, 720);
  const staleDestroy = adapter.onDestroy();
  const rebuild = adapter.onLoad('player-surface', 1920, 1080);
  await Promise.all([staleDestroy, rebuild]);
  await adapter.onSizeChange(1600, 900);

  assert(target.calls.length === 4, 'Expected attach, detach, replacement attach, and current resize.');
  assert(target.calls[1].kind === 'detach' && target.calls[1].generation === 1, 'Destroy must detach only the captured generation.');
  assert(target.calls[2].kind === 'attach' && target.calls[2].generation === 2, 'Rebuild must attach generation 2.');
  assert(target.calls[3].kind === 'resize' && target.calls[3].generation === 2, 'Resize must not target the stale generation.');
}

export async function xcomponentRejectsInvalidSurfaceSizes(): Promise<void> {
  const target = new RecordingSurfaceTarget();
  const adapter = new XComponentSurfaceAdapter(target);

  await expectFailure(() => adapter.onLoad('', 1280, 720), 'INVALID_SURFACE');
  await expectFailure(() => adapter.onLoad('player-surface', 0, 720), 'INVALID_SURFACE');
  await expectFailure(() => adapter.onLoad('player-surface', 1280, Number.NaN), 'INVALID_SURFACE');
  await expectFailure(() => adapter.onSizeChange(0, 720), 'INVALID_SURFACE');
}
