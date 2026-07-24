import { parseUri } from './inputValidator';

// SMB localhost HTTP 代理由业务应用（VidAll_TV）维护：业务层把 SMB 文件暴露为
// http://localhost:PORT/smb/... 并把 proxyLeaseId 与内置 HTTP 服务器的一次租约绑定。
// SDK 只负责在会话内关联租约，并在切源、停止、释放或网络失败时清理关联，
// 让业务层可以据此关闭代理连接、回收端口，避免旧租约泄漏。
export interface ProxyLeaseRecord {
  leaseId: string;
  // 仅保留 authority（host:port），不记录路径和查询，避免敏感信息进入事件或日志。
  host: string;
  trackedAt: number;
  releasedAt?: number;
  reason?: string;
}

export class ProxyLeaseRegistry {
  private readonly leaseRecords: ProxyLeaseRecord[] = [];

  track(leaseId: string, uri: string): void {
    if (leaseId.length === 0) {
      return;
    }
    let host = 'localhost';
    try {
      host = parseUri(uri).authority;
    } catch (_) {
      // URI 已由上层校验；解析失败时退回占位主机名，不阻断租约跟踪。
    }
    // 同一租约重复跟踪时刷新关联，避免重复释放记录。
    for (let index = 0; index < this.leaseRecords.length; index++) {
      const record = this.leaseRecords[index];
      if (record.leaseId === leaseId && record.releasedAt === undefined) {
        record.host = host;
        return;
      }
    }
    this.leaseRecords.push({ leaseId: leaseId, host: host, trackedAt: Date.now() });
  }

  release(leaseId: string, reason: string): ProxyLeaseRecord | undefined {
    for (let index = 0; index < this.leaseRecords.length; index++) {
      const record = this.leaseRecords[index];
      if (record.leaseId === leaseId && record.releasedAt === undefined) {
        record.releasedAt = Date.now();
        record.reason = reason;
        return record;
      }
    }
    return undefined;
  }

  releaseAll(reason: string): ProxyLeaseRecord[] {
    const released: ProxyLeaseRecord[] = [];
    for (let index = 0; index < this.leaseRecords.length; index++) {
      const record = this.leaseRecords[index];
      if (record.releasedAt === undefined) {
        record.releasedAt = Date.now();
        record.reason = reason;
        released.push(record);
      }
    }
    return released;
  }

  active(): ProxyLeaseRecord[] {
    return this.leaseRecords.filter((record: ProxyLeaseRecord) => record.releasedAt === undefined);
  }

  records(): ProxyLeaseRecord[] {
    return this.leaseRecords.slice();
  }
}

export function leaseReleaseMessage(record: ProxyLeaseRecord): string {
  return `SMB 代理租约已释放 lease=${record.leaseId} host=${record.host} reason=${record.reason ?? 'unknown'}`;
}
