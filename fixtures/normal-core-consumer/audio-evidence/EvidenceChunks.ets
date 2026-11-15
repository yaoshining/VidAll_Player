import { fileIo as fs } from '@kit.CoreFileKit';
import { pasteboard } from '@kit.BasicServicesKit';
import { util } from '@kit.ArkTS';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';

interface EvidenceChunk {
  version: string;
  kind: string;
  bytes: number;
  sha256: string;
  chunks: number;
  index: number;
  data: string;
}

// 仅独立验收工具：显式复制本应用生成的文件，不读取剪贴板或任意路径。
export class EvidenceChunks {
  private root: string;
  private notice: (text: string) => void;
  private bytes?: Uint8Array;
  private digest: string = '';
  private kind: string = '';
  private index: number = -1;
  private busy: boolean = false;
  private closed: boolean = false;
  constructor(root: string, notice: (text: string) => void) { this.root = root; this.notice = notice; }
  public close(): void { this.closed = true; this.bytes = undefined; }
  private check(captureBusy: boolean): void {
    if (this.closed) throw new Error('EVIDENCE_CLOSED');
    if (captureBusy) throw new Error('CAPTURE_BUSY');
    if (this.busy) throw new Error('EXPORT_BUSY');
  }
  private active(): void { if (this.closed) throw new Error('EVIDENCE_CLOSED'); }
  public async begin(kind: string, captureBusy: boolean): Promise<void> {
    this.check(captureBusy);
    if (kind !== 'capture' && kind !== 'events') throw new Error('UNKNOWN_EVIDENCE_KIND');
    this.busy = true; this.bytes = undefined; this.index = -1;
    try {
      const path = this.root + (kind === 'capture' ? '/capture.mp4' : '/events.jsonl');
      const before = await fs.stat(path); this.active();
      if (!Number.isInteger(before.size) || before.size < 1 || before.size > 16777216) throw new Error('EVIDENCE_SIZE');
      const bytes = new Uint8Array(before.size);
      const file = await fs.open(path, fs.OpenMode.READ_ONLY);
      try {
        let offset = 0;
        while (offset < bytes.length) {
          this.active();
          const buffer = new ArrayBuffer(Math.min(262144, bytes.length - offset));
          const count = await fs.read(file.fd, buffer, { length: buffer.byteLength });
          this.active();
          if (count < 1 || count > buffer.byteLength) throw new Error('EVIDENCE_SHORT_READ');
          bytes.set(new Uint8Array(buffer, 0, count), offset); offset += count;
        }
      } finally { await fs.close(file); }
      const after = await fs.stat(path); this.active();
      if (after.size !== before.size || after.mtime !== before.mtime) throw new Error('EVIDENCE_CHANGED');
      const md = cryptoFramework.createMd('SHA256');
      await md.update({ data: bytes }); const hash = await md.digest(); this.active();
      let digest = '';
      for (let i = 0; i < hash.data.length; i++) digest += hash.data[i].toString(16).padStart(2, '0');
      this.bytes = bytes; this.digest = digest; this.kind = kind;
      await this.send(0);
    } finally { this.busy = false; }
  }
  private async send(index: number): Promise<void> {
    this.active();
    const bytes = this.bytes;
    if (bytes === undefined) throw new Error('EVIDENCE_NOT_READY');
    const chunks = Math.ceil(bytes.length / 262144);
    if (index < 0 || index >= chunks) throw new Error('CHUNK_END');
    const packet: EvidenceChunk = { version: 'spec017-evidence-v1', kind: this.kind,
      bytes: bytes.length, sha256: this.digest, chunks, index,
      data: new util.Base64Helper().encodeToStringSync(bytes.slice(index * 262144, Math.min(bytes.length, (index + 1) * 262144))) };
    this.active();
    await pasteboard.getSystemPasteboard().setData(pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, JSON.stringify(packet)));
    this.active(); this.index = index;
    this.notice('已复制' + this.kind + '第' + String(index + 1) + '/' + String(chunks) + '块，' + String(bytes.length) + '字节；需接收并校验全部块');
  }
  public async next(captureBusy: boolean): Promise<void> {
    this.check(captureBusy); this.busy = true;
    try { await this.send(this.index + 1); } finally { this.busy = false; }
  }
  public async repeat(captureBusy: boolean): Promise<void> {
    this.check(captureBusy); this.busy = true;
    try { await this.send(Math.max(0, this.index)); } finally { this.busy = false; }
  }
}
