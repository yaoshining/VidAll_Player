import { PlayerSurface } from '../public/types';

export interface PlayerSurfaceTarget {
  attachSurface(surface: PlayerSurface): Promise<void>;
  resizeSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
}

export class XComponentSurfaceAdapter {
  private generation: number = 0;
  private attached: boolean = false;

  constructor(private readonly componentId: string, private readonly player: PlayerSurfaceTarget) {}

  onLoad(width: number, height: number): Promise<void> {
    this.generation += 1;
    this.attached = true;
    return this.player.attachSurface(this.surface(width, height));
  }

  onSizeChange(width: number, height: number): Promise<void> {
    if (!this.attached) {
      return Promise.resolve();
    }
    return this.player.resizeSurface(this.surface(width, height));
  }

  onDestroy(): Promise<void> {
    if (!this.attached) {
      return Promise.resolve();
    }
    this.attached = false;
    return this.player.detachSurface(this.generation);
  }

  private surface(width: number, height: number): PlayerSurface {
    return { componentId: this.componentId, generation: this.generation, width, height };
  }
}
