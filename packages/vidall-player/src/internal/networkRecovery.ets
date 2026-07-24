import { PlayerError } from '../public/types';
import { PlayerFailure } from './playerFailure';

// 网络失败稳定码：消费者可据此决定重试或展示不可恢复原因。
// 可重试：瞬时网络问题，重新 load 同一来源即可恢复。
const RETRYABLE_NETWORK_CODES: string[] = [
  'NETWORK_TIMEOUT',
  'NETWORK_DISCONNECTED',
  'CONNECTION_REFUSED',
  'PROXY_UNAVAILABLE'
];

// 不可恢复：需要用户干预（更换地址、重新认证、更换媒体），重试无意义。
const UNRECOVERABLE_NETWORK_CODES: string[] = [
  'TLS_CERTIFICATE_INVALID',
  'HTTP_AUTH_REQUIRED',
  'HTTP_NOT_FOUND',
  'FORMAT_UNSUPPORTED'
];

const NETWORK_FAILURE_MESSAGES: Record<string, string> = {
  'NETWORK_TIMEOUT': '网络连接超时，可重试 (Network connection timed out; retryable).',
  'NETWORK_DISCONNECTED': '网络已断开，恢复后可重试 (Network disconnected; retryable after recovery).',
  'CONNECTION_REFUSED': '服务器拒绝连接，可重试 (Connection refused by server; retryable).',
  'PROXY_UNAVAILABLE': 'SMB localhost 代理不可用，可重试 (SMB localhost proxy unavailable; retryable).',
  'TLS_CERTIFICATE_INVALID': 'TLS 证书校验失败，不可恢复 (TLS certificate validation failed; not retryable).',
  'HTTP_AUTH_REQUIRED': '媒体服务认证失败，需重新认证 (Media server authentication failed; re-authentication required).',
  'HTTP_NOT_FOUND': '媒体资源不存在或已失效 (Media resource not found or expired).',
  'FORMAT_UNSUPPORTED': '媒体格式不受支持 (Media format is not supported).'
};

export function classifyNetworkFailure(code: string, detail?: string): PlayerFailure {
  const known = RETRYABLE_NETWORK_CODES.indexOf(code) >= 0 || UNRECOVERABLE_NETWORK_CODES.indexOf(code) >= 0;
  // 未知错误默认按可重试处理：宁可让消费者多一次重试机会，也不把瞬时问题误判为不可恢复。
  const retryable = known ? RETRYABLE_NETWORK_CODES.indexOf(code) >= 0 : true;
  const message = known ? NETWORK_FAILURE_MESSAGES[code] : `网络播放失败（${code}），可重试 (Network playback failed; retryable).`;
  const context: Record<string, string | number | boolean> = {};
  if (detail !== undefined && detail.length > 0) {
    context.detail = detail;
  }
  const error: PlayerError = {
    domain: 'network',
    code: code,
    message: message,
    retryable: retryable,
    context: context
  };
  return new PlayerFailure(error);
}

// 会话级恢复控制器：记录最近一次失败并保证重试前旧状态已被清理。
export class NetworkRecoveryController {
  private lastFailure?: PlayerFailure;

  recordFailure(failure: PlayerFailure): void {
    this.lastFailure = failure;
  }

  clear(): void {
    this.lastFailure = undefined;
  }

  canRetry(): boolean {
    return this.lastFailure !== undefined && this.lastFailure.playerError.retryable;
  }

  lastError(): PlayerError | undefined {
    return this.lastFailure?.playerError;
  }
}
