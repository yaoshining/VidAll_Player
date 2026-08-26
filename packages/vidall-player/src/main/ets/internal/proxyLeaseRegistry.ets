import { parseUri } from './inputValidator';

const MAX_LEASE_RECORDS = 64;

export type ProxyLeaseState = 'acquired' | 'renewed' | 'releaseRequested' | 'released' | 'expired' | 'cleanupFailed';

export interface ProxyLeaseRecord {
  leaseId: string;
  host: string;
  epoch: number;
  state: ProxyLeaseState;
  retryable: boolean;
  trackedAt: number;
  releasedAt?: number;
  reason?: string;
}

export class ProxyLeaseRegistry {
  private readonly leaseRecords: ProxyLeaseRecord[] = [];

  track(leaseId: string, uri: string, epoch: number): ProxyLeaseRecord | undefined {
    if (leaseId.length === 0 || !Number.isInteger(epoch) || epoch < 1) {
      return undefined;
    }
    let host = 'localhost';
    try {
      host = parseUri(uri).authority;
    } catch (_) {
      return undefined;
    }
    const current = this.find(leaseId);
    if (current !== undefined && current.state !== 'released' && current.state !== 'expired' && current.state !== 'cleanupFailed') {
      if (epoch <= current.epoch) {
        return current;
      }
      current.host = host;
      current.epoch = epoch;
      current.state = 'renewed';
      current.retryable = true;
      return current;
    }
    const record: ProxyLeaseRecord = {
      leaseId: leaseId,
      host: host,
      epoch: epoch,
      state: 'acquired',
      retryable: true,
      trackedAt: Date.now()
    };
    this.leaseRecords.push(record);
    if (this.leaseRecords.length > MAX_LEASE_RECORDS) {
      this.leaseRecords.splice(0, this.leaseRecords.length - MAX_LEASE_RECORDS);
    }
    return record;
  }

  requestReleaseAll(reason: string): ProxyLeaseRecord[] {
    const requested: ProxyLeaseRecord[] = [];
    for (let index = 0; index < this.leaseRecords.length; index++) {
      const record = this.leaseRecords[index];
      if (record.state === 'acquired' || record.state === 'renewed') {
        record.state = 'releaseRequested';
        record.reason = reason;
        requested.push(record);
      }
    }
    return requested;
  }

  confirmReleased(leaseId: string, epoch: number): ProxyLeaseRecord | undefined {
    const record = this.find(leaseId);
    if (record === undefined || record.epoch !== epoch || record.state !== 'releaseRequested') {
      return undefined;
    }
    record.state = 'released';
    record.retryable = false;
    record.releasedAt = Date.now();
    return record;
  }

  expire(leaseId: string, epoch: number): ProxyLeaseRecord | undefined {
    return this.terminal(leaseId, epoch, 'expired', true);
  }

  cleanupFailed(leaseId: string, epoch: number): ProxyLeaseRecord | undefined {
    return this.terminal(leaseId, epoch, 'cleanupFailed', true);
  }

  active(): ProxyLeaseRecord[] {
    return this.leaseRecords.filter((record: ProxyLeaseRecord) =>
      record.state === 'acquired' || record.state === 'renewed' || record.state === 'releaseRequested');
  }

  records(): ProxyLeaseRecord[] {
    return this.leaseRecords.slice();
  }

  private find(leaseId: string): ProxyLeaseRecord | undefined {
    for (let index = this.leaseRecords.length - 1; index >= 0; index--) {
      if (this.leaseRecords[index].leaseId === leaseId) {
        return this.leaseRecords[index];
      }
    }
    return undefined;
  }

  private terminal(leaseId: string, epoch: number, state: 'expired' | 'cleanupFailed', retryable: boolean): ProxyLeaseRecord | undefined {
    const record = this.find(leaseId);
    if (record === undefined || record.epoch !== epoch || record.state === 'released' || record.state === 'cleanupFailed') {
      return undefined;
    }
    record.state = state;
    record.retryable = retryable;
    record.releasedAt = Date.now();
    return record;
  }
}
