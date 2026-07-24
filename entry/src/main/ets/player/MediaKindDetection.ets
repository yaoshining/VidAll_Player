// 演示层媒体类型识别：根据 URI 的扩展名与主机推断 MediaSource.kind，
// 与 @vidall/player 的输入校验规则保持一致（localhostProxy 仅限环回明文 HTTP）。
export type DetectedMediaKind = 'hls' | 'dash' | 'localhostProxy' | 'https' | 'http';

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
  return lowerUri.indexOf('https://') === 0 ? 'https' : 'http';
}

let leaseSequence: number = 0;

// 演示层为每次 SMB 代理加载生成唯一租约 ID，供 SDK 关联与清理。
export function newProxyLeaseId(): string {
  leaseSequence += 1;
  return `lease-${Date.now().toString(36)}-${leaseSequence.toString(36)}`;
}
