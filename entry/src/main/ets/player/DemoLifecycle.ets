export type DemoLifecycleState = 'idle' | 'playing' | 'paused' | 'released';

export class DemoLifecycleController {
  private activeSource: string = '';
  private state: DemoLifecycleState = 'idle';
  private surfaceDetached: boolean = false;
  private inBackground: boolean = false;
  private networkInterrupted: boolean = false;

  markPlaybackStarted(source: string): void {
    const normalizedSource = source.trim();
    if (normalizedSource.length > 0) {
      this.activeSource = normalizedSource;
    }
    this.state = 'playing';
    this.surfaceDetached = false;
    this.networkInterrupted = false;
  }

  markPlaybackStopped(): void {
    if (this.state !== 'released') {
      this.state = 'idle';
      this.surfaceDetached = false;
      this.networkInterrupted = false;
    }
  }

  markReleased(): void {
    this.activeSource = '';
    this.state = 'released';
    this.surfaceDetached = false;
    this.inBackground = false;
    this.networkInterrupted = false;
  }

  onSurfaceDestroyed(): boolean {
    this.surfaceDetached = this.state === 'playing' || this.state === 'paused';
    return this.surfaceDetached;
  }

  onSurfaceCreated(): boolean {
    const shouldResume = this.surfaceDetached && (this.state === 'playing' || this.state === 'paused') &&
      !this.inBackground && !this.networkInterrupted && this.activeSource.length > 0;
    this.surfaceDetached = false;
    if (shouldResume) {
      this.state = 'playing';
    }
    return shouldResume;
  }

  onBackground(): boolean {
    this.inBackground = true;
    if (this.state === 'playing') {
      this.state = 'paused';
      return true;
    }
    return false;
  }

  onForeground(): boolean {
    this.inBackground = false;
    if (this.state === 'paused' && !this.surfaceDetached && !this.networkInterrupted && this.activeSource.length > 0) {
      this.state = 'playing';
      return true;
    }
    return false;
  }

  onNetworkLost(): boolean {
    this.networkInterrupted = this.state === 'playing' || this.state === 'paused';
    return this.networkInterrupted;
  }

  onNetworkRecovered(): boolean {
    if (!this.networkInterrupted) {
      return false;
    }
    this.networkInterrupted = false;
    if (this.inBackground || this.surfaceDetached || this.activeSource.length === 0 ||
      this.state === 'released' || this.state === 'idle') {
      return false;
    }
    this.state = 'playing';
    return true;
  }

  getActiveSource(): string {
    return this.activeSource;
  }

  getState(): DemoLifecycleState {
    return this.state;
  }

  moveFocus(currentIndex: number, itemCount: number, direction: number): number {
    if (itemCount <= 0) {
      return -1;
    }
    const normalizedCurrent = currentIndex < 0 || currentIndex >= itemCount ? 0 : currentIndex;
    return Math.min(itemCount - 1, Math.max(0, normalizedCurrent + direction));
  }
}
