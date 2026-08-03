// 演示层媒体类型识别：根据 URI 的扩展名与主机推断 MediaSource.kind，
// 与 @vidall/player 的输入校验规则保持一致（localhostProxy 仅限环回明文 HTTP）。
export type DetectedMediaKind = 'hls' | 'dash' | 'localhostProxy' | 'smb' | 'https' | 'http';

function pathWithoutQuery(uri: string): string {
  const schemeIndex = uri.indexOf('://');
  const rest = schemeIndex >= 0 ? uri.substring(schemeIndex + 3) : uri;
  const slashIndex = rest.indexOf('/');
  if (slashIndex < 0) {
    return '';
  }
  let path = rest.substring(slashIndex);
  const queryIndex = path.indexOf('?');
  if (queryIndex >= 0) {
    path = path.substring(0, queryIndex);
  }
  const fragmentIndex = path.indexOf('#');
  if (fragmentIndex >= 0) {
    path = path.substring(0, fragmentIndex);
  }
  return path.toLowerCase();
}

function hostOf(uri: string): string {
  const schemeIndex = uri.indexOf('://');
  const rest = schemeIndex >= 0 ? uri.substring(schemeIndex + 3) : uri;
  let authority = rest;
  for (let index = 0; index < authority.length; index++) {
    const char = authority.charAt(index);
    if (char === '/' || char === '?' || char === '#') {
      authority = authority.substring(0, index);
      break;
    }
  }
  authority = authority.toLowerCase();
  if (authority.charAt(0) === '[') {
    const bracketIndex = authority.indexOf(']');
    return bracketIndex >= 0 ? authority.substring(0, bracketIndex + 1) : authority;
  }
  const colonIndex = authority.indexOf(':');
  return colonIndex >= 0 ? authority.substring(0, colonIndex) : authority;
}

function isLoopbackHost(host: string): boolean {
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

export function detectMediaKind(uri: string): DetectedMediaKind {
  const path = pathWithoutQuery(uri);
  if (path.endsWith('.m3u8')) {
    return 'hls';
  }
  if (path.endsWith('.mpd')) {
    return 'dash';
  }
  const lowerUri = uri.toLowerCase();
  if (lowerUri.indexOf('http://') === 0 && isLoopbackHost(hostOf(uri))) {
    return 'localhostProxy';
  }
  if (lowerUri.indexOf('smb://') === 0) {
    return 'smb';
  }
  return lowerUri.indexOf('https://') === 0 ? 'https' : 'http';
}

// 直连 SMB（smb://）在 @vidall/player 中被永久 gate 住：nativeBridge.getDirectSmbCapability()
// 恒返回 { available: false }，因为 libmpv.so 尚未交叉编译 libsmbclient（GPLv3 受控发布门禁，
// 见 docs/controlled-libmpv-release.md、docs/smb-localhost-http-proxy.md 的 Issue #41 说明）。
// 演示层必须在提交加载前拦截这条路径，否则用户只会看到 SDK 内部的
// HEADER_NOT_ALLOWED / PROTOCOL_NOT_AVAILABLE 校验错误码，无法理解真正原因。
export const SMB_UNSUPPORTED_MESSAGE =
  'SMB 直连暂不支持：需要交叉编译 libsmbclient 到 libmpv.so（受控发布门禁，Issue #41），' +
  '当前请改用 WebDAV 或本地文件播放。';

export function isSmbDirectPlaybackSupported(): boolean {
  return false;
}

let leaseSequence: number = 0;

// 演示层为每次 SMB 代理加载生成唯一租约 ID，供 SDK 关联与清理。
export function newProxyLeaseId(): string {
  leaseSequence += 1;
  return `lease-${Date.now().toString(36)}-${leaseSequence.toString(36)}`;
}
