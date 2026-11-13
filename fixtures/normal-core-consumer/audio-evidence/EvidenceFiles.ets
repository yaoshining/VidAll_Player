import { common } from '@kit.AbilityKit';
import { hiAppEvent } from '@kit.PerformanceAnalysisKit';
import { fileIo as fs, picker } from '@kit.CoreFileKit';

interface CrashParams {
  bundle_name?: string;
  external_log?: string[];
}

// 仅用于独立验收：不改变正式 HAR，不将收证成功等同设备验收。
export class EvidenceFiles {
  private watcher?: hiAppEvent.Watcher;
  private closed: boolean = false;
  private seen: string[] = [];
  private reading: boolean = false;
  private exporting: boolean = false;
  private context: common.UIAbilityContext;
  private root: string;
  private notice: (message: string) => void;

  constructor(context: common.UIAbilityContext, root: string, notice: (message: string) => void) {
    this.context = context; this.root = root; this.notice = notice;
  }
  public start(): void {
    if (this.watcher !== undefined || this.closed) return;
    const watcher: hiAppEvent.Watcher = {
      name: 'Spec017CrashEvidence',
      appEventFilters: [{ domain: 'OS', names: [hiAppEvent.event.APP_CRASH] }],
      onReceive: (domain: string, groups: hiAppEvent.AppEventGroup[]): void => {
        this.receive(domain, groups).catch((error: Error) => {
          if (!this.closed) this.notice('崩溃收证失败：' + error.message);
        });
      }
    };
    if (!hiAppEvent.addWatcher(watcher)) throw new Error('CRASH_WATCHER_UNAVAILABLE');
    this.watcher = watcher;
  }
  public close(): void {
    this.closed = true;
    if (this.watcher !== undefined) {
      hiAppEvent.removeWatcher(this.watcher); this.watcher = undefined;
    }
  }
  public async receive(domain: string, groups: hiAppEvent.AppEventGroup[]): Promise<void> {
    if (this.closed || this.reading || domain !== 'OS') return;
    this.reading = true;
    try {
      for (const group of groups) {
        for (const event of group.appEventInfos) {
          if (event.name !== hiAppEvent.event.APP_CRASH) continue;
          const params = event.params as CrashParams;
          if (params.bundle_name !== 'com.yaoshining.vidallplayer' || !Array.isArray(params.external_log)) continue;
          for (const path of params.external_log) {
            if (this.closed || this.seen.length >= 4) return;
            // 只接受系统事件提供的本应用日志；禁止目录穿越及系统故障目录。
            if (typeof path !== 'string' || !/^\/data\/storage\/el2\/log\/hiappevent\/APP_CRASH_[A-Za-z0-9_.-]+\.log$/.test(path) || this.seen.includes(path)) continue;
            this.seen.push(path);
            const stat = await fs.stat(path);
            const stack = await fs.readText(path, { length: 524288 });
            if (this.closed) return;
            const text = '本应用 APP_CRASH；' + (stat.size > 524288 ? '日志已截断至512KiB' : '日志未截断') + '\n' + stack;
            const file = await fs.open(this.root + '/crash.txt', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
            try { await fs.write(file.fd, text); } finally { await fs.close(file); }
            if (!this.closed) this.notice('已保存本应用崩溃记录，可导出；不代表已修复');
          }
        }
      }
    } catch (error) {
      if (!this.closed) this.notice('崩溃收证失败：' + (error as Error).message);
    } finally { this.reading = false; }
  }
  public async exportFile(kind: string, captureBusy: boolean): Promise<boolean> {
    if (this.closed) throw new Error('EVIDENCE_CLOSED');
    if (this.exporting) throw new Error('EXPORT_BUSY');
    if (captureBusy) throw new Error('CAPTURE_BUSY');
    let name: string;
    if (kind === 'capture') name = 'capture.mp4';
    else if (kind === 'events') name = 'events.jsonl';
    else if (kind === 'crash') name = 'crash.txt';
    else throw new Error('UNKNOWN_EVIDENCE_KIND');
    this.exporting = true;
    try {
      // 先打开来源；缺失时不弹保存框，也不生成空成功文件。
      const source = await fs.open(this.root + '/' + name, fs.OpenMode.READ_ONLY);
      try {
        const uris = await new picker.DocumentViewPicker(this.context).save({ newFileNames: ['spec017-' + name] });
        if (this.closed || uris.length === 0) return false;
        if (uris.length !== 1) throw new Error('EXPORT_DESTINATION_COUNT');
        const target = await fs.open(uris[0], fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
        try { await fs.copyFile(source.fd, target.fd); } finally { await fs.close(target); }
      } finally { await fs.close(source); }
      return !this.closed;
    } finally { this.exporting = false; }
  }
}
