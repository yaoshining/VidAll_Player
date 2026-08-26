// SMB 凭据转发回归测试：本会话早前把 entry 从自有原生模块（entry/src/main/cpp/napi_bridge.cpp，
// 已用 demuxer-lavf-o/stream-lavf-o 的 username=/password= 选项实现真实可用的认证 SMB）
// 迁移到 @vidall/player HAR 时，遗漏了移植 SMB 凭据注入逻辑，导致 gate 已开、原生库也支持
// libsmbclient，但凭据永远传不到 mpv。这里覆盖 extractSmbCredentials() 从
// MediaSource.headers.authorization（"Basic <base64>"）解码用户名/密码的行为，
// 确保修复后不再回归。
//
// TDD：先写测试固定预期行为，再验证 nativeBridge.ets 的实现使其通过。

import { util } from '@kit.ArkTS';
import { MediaSource } from '@vidall/player';
import { extractSmbCredentials, SmbCredentials } from '../../src/main/ets/native/nativeBridge';

function basicAuthorization(username: string, password: string): string {
  const bytes = new util.TextEncoder('utf-8').encode(`${username}:${password}`);
  return `Basic ${new util.Base64Helper().encodeToStringSync(bytes)}`;
}

function assertCredentials(actual: SmbCredentials, expectedUsername: string, expectedPassword: string, context: string): void {
  if (actual.username !== expectedUsername || actual.password !== expectedPassword) {
    throw new Error(
      `${context}: expected username=${expectedUsername} password=${expectedPassword}, got username=${actual.username} password=${actual.password}`
    );
  }
}

// ══════════════════════════════════════════════════════════════════
// 1. 非 SMB 源（https）：即便携带 authorization header 也不应被当作 SMB 凭据解析
// ══════════════════════════════════════════════════════════════════
export async function extractSmbCredentials_nonSmbSourceReturnsEmpty(): Promise<void> {
  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/video.mp4',
    headers: { authorization: basicAuthorization('alice', 'secret') }
  };
  assertCredentials(extractSmbCredentials(source), '', '', 'non-smb source');
}

// ══════════════════════════════════════════════════════════════════
// 2. 匿名 SMB：无 headers 时视为匿名共享，不报错，返回空用户名/密码
// ══════════════════════════════════════════════════════════════════
export async function extractSmbCredentials_anonymousSmbReturnsEmpty(): Promise<void> {
  const source: MediaSource = { kind: 'smb', uri: 'smb://fixture.invalid/share/video.mp4' };
  assertCredentials(extractSmbCredentials(source), '', '', 'anonymous smb without headers');
}

// ══════════════════════════════════════════════════════════════════
// 3. 认证 SMB：从 Basic Authorization header 正确解码出用户名/密码
// ══════════════════════════════════════════════════════════════════
export async function extractSmbCredentials_decodesBasicAuthorization(): Promise<void> {
  const source: MediaSource = {
    kind: 'smb',
    uri: 'smb://fixture.invalid/share/video.mp4',
    headers: { authorization: basicAuthorization('nasuser', 'nas:pass') }
  };
  assertCredentials(extractSmbCredentials(source), 'nasuser', 'nas:pass', 'authenticated smb');
}

// ══════════════════════════════════════════════════════════════════
// 4. header 名称大小写不敏感（"Authorization" 与 "authorization" 等价）
// ══════════════════════════════════════════════════════════════════
export async function extractSmbCredentials_headerNameCaseInsensitive(): Promise<void> {
  const source: MediaSource = {
    kind: 'smb',
    uri: 'smb://fixture.invalid/share/video.mp4',
    headers: { Authorization: basicAuthorization('bob', 'hunter2') }
  };
  assertCredentials(extractSmbCredentials(source), 'bob', 'hunter2', 'case-insensitive header lookup');
}

// ══════════════════════════════════════════════════════════════════
// 5. 非法 Basic Authorization（无法 Base64 解码/无冒号分隔）应安全降级为匿名，
//    而不是抛出异常导致 load() 失败
// ══════════════════════════════════════════════════════════════════
export async function extractSmbCredentials_malformedAuthorizationFallsBackToAnonymous(): Promise<void> {
  const missingColon: MediaSource = {
    kind: 'smb',
    uri: 'smb://fixture.invalid/share/video.mp4',
    headers: { authorization: `Basic ${new util.Base64Helper().encodeToStringSync(new util.TextEncoder('utf-8').encode('nocolonhere'))}` }
  };
  assertCredentials(extractSmbCredentials(missingColon), '', '', 'missing colon separator');

  const notBasicScheme: MediaSource = {
    kind: 'smb',
    uri: 'smb://fixture.invalid/share/video.mp4',
    headers: { authorization: 'Bearer some-token' }
  };
  assertCredentials(extractSmbCredentials(notBasicScheme), '', '', 'non-Basic scheme');

  const invalidBase64: MediaSource = {
    kind: 'smb',
    uri: 'smb://fixture.invalid/share/video.mp4',
    headers: { authorization: 'Basic ***not-valid-base64***' }
  };
  assertCredentials(extractSmbCredentials(invalidBase64), '', '', 'invalid base64 payload');
}
