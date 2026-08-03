import { lifecycleFailure } from '../internal/playerFailure';
import { VidAllPlayer } from '../public/playerContract';
import { PlayerSurface } from '../public/types';

export abstract class PlayerSurfaceTarget {
  abstract attachSurface(surface: PlayerSurface): Promise<void>;
  abstract resizeSurface(surface: PlayerSurface): Promise<void>;
  abstract detachSurface(generation: number): Promise<void>;
}

// ArkTS uses nominal typing, so the public player interface needs this explicit adapter.
export class VidAllPlayerSurfaceTarget extends PlayerSurfaceTarget {
  private readonly player: VidAllPlayer;

  constructor(player: VidAllPlayer) {
    super();
    this.player = player;
  }

  attachSurface(surface: PlayerSurface): Promise<void> {
    return this.player.attachSurface(surface);
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    return this.player.resizeSurface(surface);
  }

  detachSurface(generation: number): Promise<void> {
    return this.player.detachSurface(generation);
  }
}

export class XComponentSurfaceAdapter {
  private generation: number = 0;
  private attached: boolean = false;
  private attachedGeneration: number = 0;
  private lifecycle: Promise<void> = Promise.resolve();
  private componentId: string = '';
  private readonly player: PlayerSurfaceTarget;

  constructor(player: PlayerSurfaceTarget) {
    this.player = player;
  }

  onLoad(componentId: string, width: number, height: number): Promise<void> {
    this.validateComponentId(componentId);
    this.validateSize(width, height);
    this.generation += 1;
    this.componentId = componentId;
    const generation = this.generation;
    const surface = this.surface(componentId, generation, width, height);
    return this.schedule(() => this.player.attachSurface(surface).then(() => {
      this.attached = true;
      this.attachedGeneration = generation;
    }));
  }

  onSizeChange(width: number, height: number): Promise<void> {
    this.validateSize(width, height);
    const generation = this.generation;
    const surface = this.surface(this.componentId, generation, width, height);
    return this.schedule(() => {
      if (!this.attached || generation !== this.generation || generation !== this.attachedGeneration) {
        return Promise.resolve();
      }
      return this.player.resizeSurface(surface);
    });
  }

  onDestroy(): Promise<void> {
    const generation = this.generation;
    return this.schedule(() => {
      if (!this.attached || generation !== this.generation || generation !== this.attachedGeneration) {
        return Promise.resolve();
      }
      return this.player.detachSurface(generation).then(() => {
        if (this.attachedGeneration === generation) {
          this.attached = false;
          this.attachedGeneration = 0;
        }
      });
    });
  }

  private schedule(operation: () => Promise<void>): Promise<void> {
    const task = this.lifecycle.catch(() => {}).then(operation);
    this.lifecycle = task;
    return task;
  }

  private surface(componentId: string, generation: number, width: number, height: number): PlayerSurface {
    return { componentId, generation, width, height };
  }

  private validateComponentId(componentId: string): void {
    if (componentId.length === 0) {
      throw lifecycleFailure('INVALID_SURFACE', 'XComponent surface ID must not be empty. XComponent Surface ID 不能为空。');
    }
  }

  private validateSize(width: number, height: number): void {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      throw lifecycleFailure('INVALID_SURFACE', 'Surface dimensions must be finite and positive. Surface 尺寸必须是有限正数。');
    }
  }
}
