export class DemoLifecycleController {
  private activeSource: string = '';
  private playing: boolean = false;
  private surfaceDetached: boolean = false;
  private inBackground: boolean = false;

  markPlaybackStarted(source: string): void {
    this.activeSource = source;
    this.playing = source.length > 0;
    this.surfaceDetached = false;
  }

  markPlaybackStopped(): void {
    this.playing = false;
  }

  markReleased(): void {
    this.activeSource = '';
    this.playing = false;
    this.surfaceDetached = false;
    this.inBackground = false;
  }

  onSurfaceDestroyed(): boolean {
    this.surfaceDetached = this.playing;
    return this.surfaceDetached;
  }

  onSurfaceCreated(): boolean {
    const shouldResume = this.surfaceDetached && this.playing && !this.inBackground && this.activeSource.length > 0;
    this.surfaceDetached = false;
    return shouldResume;
  }

  onBackground(): boolean {
    this.inBackground = true;
    return this.playing;
  }

  onForeground(): boolean {
    this.inBackground = false;
    return this.playing && !this.surfaceDetached && this.activeSource.length > 0;
  }

  getActiveSource(): string {
    return this.activeSource;
  }

  moveFocus(currentIndex: number, itemCount: number, direction: number): number {
    if (itemCount <= 0) {
      return -1;
    }
    const normalizedCurrent = currentIndex < 0 || currentIndex >= itemCount ? 0 : currentIndex;
    return (normalizedCurrent + direction + itemCount) % itemCount;
  }
}
