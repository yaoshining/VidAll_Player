import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import process from '@ohos.process';
import { SessionJournal, JournalPort } from './SessionJournal';
export class FileJournal implements JournalPort {
  root: string = '';
  private base: string;
  constructor(base: string) { this.base = base; }
  now(): number { return Date.now(); }
  pid(): number { return process.pid; }
  mkdirExclusive(nonce: string): void {
    const parent = this.base + '/device-smoke';
    if (!fs.accessSync(parent)) fs.mkdirSync(parent);
    this.root = parent + '/' + nonce;
    // mkdir不是递归创建；存在同nonce立即失败，不读取或追加旧会话。
    fs.mkdirSync(this.root);
  }
  append(line: string): void {
    const file = fs.openSync(this.root + '/events.jsonl', fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.APPEND);
    try { fs.writeSync(file.fd, line); } finally { fs.closeSync(file); }
  }
}
export class LaunchSession {
  static journal?: SessionJournal;
  static files?: FileJournal;
  static opened: boolean = false;
  static start(context: common.UIAbilityContext, nonce: string, mode: string, expectedSHA: string): void {
    if (LaunchSession.opened) throw new Error('SESSION_ALREADY_ACTIVE');
    const files = new FileJournal(context.filesDir);
    const journal = new SessionJournal(files, nonce);
    journal.start(mode, expectedSHA);
    LaunchSession.files = files; LaunchSession.journal = journal; LaunchSession.opened = true;
  }
}
