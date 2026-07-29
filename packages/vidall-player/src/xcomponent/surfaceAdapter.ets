import { PlayerSurface } from '../public/types';
import { lifecycleFailure } from '../internal/playerFailure';

export interface PlayerSurfaceTarget {
  attachSurface(surface: PlayerSurface): Promise<void>;
  resizeSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
}

export class XComponentSurfaceAdapter {
  private generation: number = 0;
  private attached: boolean = false;
  private lifecycle: Promise<void> = Promise.resolve();
  private readonly componentId: string;
  private readonly player: PlayerSurfaceTarget;

  constructor(componentId: string, player: PlayerSurfaceTarget) {
    this.componentId = componentId;
    this.player = player;
  }

  onLoad(width: number, height: number): Promise<void> {
    this.validateSize(width, height);
    this.generation += 1;
    const surface = this.surface(width, height);
    return this.schedule(() => this.player.attachSurface(surface).then(() => {
      this.attached = true;
    }));
  }

  onSizeChange(width: number, height: number): Promise<void> {
    const surface = this.surface(width, height);
    return this.schedule(() => {
      if (!this.attached) {
        return Promise.resolve();
      }
      this.validateSize(width, height);
      return this.player.resizeSurface(surface);
    });
  }

  onDestroy(): Promise<void> {
    const generation = this.generation;
    return this.schedule(() => {
      if (!this.attached) {
        return Promise.resolve();
      }
      return this.player.detachSurface(generation).then(() => {
        this.attached = false;
      });
    });
  }

  private schedule(operation: () => Promise<void>): Promise<void> {
    const task = this.lifecycle.catch(() => {}).then(operation);
    this.lifecycle = task;
    return task;
  }

  private surface(width: number, height: number): PlayerSurface {
    return { componentId: this.componentId, generation: this.generation, width, height };
  }

  private validateSize(width: number, height: number): void {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      throw lifecycleFailure('INVALID_SURFACE', 'Surface dimensions must be finite and positive. Surface 尺寸必须是有限正数。');
    }
  }
}
