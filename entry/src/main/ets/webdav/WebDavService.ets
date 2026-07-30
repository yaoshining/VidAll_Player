import { http } from '@kit.NetworkKit';
import { preferences } from '@kit.ArkData';
import { util } from '@kit.ArkTS';
import { common } from '@kit.AbilityKit';
import socket from '@ohos.net.socket';
import buffer from '@ohos.buffer';

const VIDEO_EXTENSIONS: string[] = [
  '3gp', 'asf', 'avi', 'flv', 'm2ts', 'm4v', 'mkv', 'mov', 'mp4', 'mpeg', 'mpg', 'mts', 'rmvb', 'ts', 'webm', 'wmv'
];
const CONFIG_KEY = 'configuration';
const PROPFIND_BODY = '<?xml version="1.0"?><propfind xmlns="DAV:"><prop><displayname/><resourcetype/><getcontentlength/></prop></propfind>';
const MAX_HTTP_RESPONSE_BYTES = 5 * 1024 * 1024;

function hasControlCharacters(value: string): boolean {
  return /[\x00-\x1F\x7F]/.test(value);
}

export function createPropfindRequestOptions(username: string, password: string): http.HttpRequestOptions {
  return {
    method: http.RequestMethod.POST,
    customMethod: 'PROPFIND',
    header: {
      'Authorization': buildBasicAuthorization(username, password),
      'Depth': '1',
      'Content-Type': 'text/xml; charset=utf-8'
    },
    // 当前 NetworkKit SDK 会把 POST 的 extraData 作为请求体发送。
    // OPTIONS 会把它拼接到 URL，因此先使用 POST 再由 customMethod 覆盖。
    extraData: PROPFIND_BODY,
    expectDataType: http.HttpDataType.STRING,
    connectTimeout: 15000,
    readTimeout: 30000,
    usingCache: false
  };
}

export interface WebDavConfig {
  endpoint: string;
  username: string;
  password: string;
}

export interface WebDavEntry {
  name: string;
  url: string;
  isDirectory: boolean;
  size: number;
}

export function sanitizeWebDavConfig(config: WebDavConfig): WebDavConfig {
  const endpoint = config.endpoint.trim();
  if (!isAbsoluteHttpUrl(endpoint)) {
    throw new Error('WebDAV 地址必须以 http:// 或 https:// 开头。');
  }
  // 拒绝包含 userinfo 的端点（如 http://user:pass@host），防止凭据被持久化到 preferences。
  const schemeEnd = endpoint.indexOf('://');
  const authority = endpoint.substring(schemeEnd + 3).split(/[/?#]/)[0];
  if (authority.indexOf('@') >= 0) {
    throw new Error('WebDAV 地址不得包含用户凭据（user:pass@host）。');
  }
  return { endpoint: endpoint, username: config.username.trim(), password: '' };
}

export function buildBasicAuthorization(username: string, password: string): string {
  const bytes = new util.TextEncoder('utf-8').encode(`${username}:${password}`);
  return `Basic ${new util.Base64Helper().encodeToStringSync(bytes)}`;
}

export function isSafeRedirect(fromUri: string, redirectUri: string): boolean {
  const fromSchemeEnd = fromUri.indexOf('://');
  const redirectSchemeEnd = redirectUri.indexOf('://');
  if (fromSchemeEnd < 0 || redirectSchemeEnd < 0) {
    return false;
  }
  const fromScheme = fromUri.substring(0, fromSchemeEnd).toLowerCase();
  const redirectScheme = redirectUri.substring(0, redirectSchemeEnd).toLowerCase();
  // 协议降级（HTTPS→HTTP）不安全
  if (fromScheme === 'https' && redirectScheme !== 'https') {
    return false;
  }
  if (fromScheme !== redirectScheme) {
    return false;
  }
  // 提取 host:port 并规范化比较
  const fromAuthority = extractAuthority(fromUri);
  const redirectAuthority = extractAuthority(redirectUri);
  return normalizeHostPort(fromScheme, fromAuthority) === normalizeHostPort(redirectScheme, redirectAuthority);
}

function extractAuthority(uri: string): string {
  const schemeEnd = uri.indexOf('://');
  if (schemeEnd < 0) {
    return '';
  }
  const rest = uri.substring(schemeEnd + 3);
  let authority = rest;
  for (let index = 0; index < authority.length; index++) {
    const char = authority.charAt(index);
    if (char === '/' || char === '?' || char === '#') {
      authority = authority.substring(0, index);
      break;
    }
  }
  return authority.toLowerCase();
}

function normalizeHostPort(scheme: string, authority: string): string {
  const colonIndex = authority.lastIndexOf(':');
  if (colonIndex >= 0 && authority.charAt(authority.length - 1) !== ']') {
    return authority;
  }
  if (scheme === 'https') {
    return `${authority}:443`;
  }
  if (scheme === 'http') {
    return `${authority}:80`;
  }
  return authority;
}

export function buildWebDavPlaybackHeaders(
  username: string,
  password: string,
  rangeStart?: number,
  rangeEnd?: number
): Record<string, string> {
  const headers: Record<string, string> = {};
  if (!(username.length === 0 && password.length === 0)) {
    headers['Authorization'] = buildBasicAuthorization(username, password);
  }
  if (rangeStart !== undefined && rangeStart >= 0) {
    if (rangeEnd !== undefined && rangeEnd >= rangeStart) {
      headers['Range'] = `bytes=${rangeStart}-${rangeEnd}`;
    } else {
      headers['Range'] = `bytes=${rangeStart}-`;
    }
  }
  return headers;
}

export function buildRawPropfindRequest(host: string, authorization: string): string {
  if (hasControlCharacters(host) || hasControlCharacters(authorization)) {
    throw new Error('WebDAV HTTP 请求包含无效字符。');
  }
  const bodyBytes = new util.TextEncoder('utf-8').encode(PROPFIND_BODY);
  return `PROPFIND / HTTP/1.1\r\nHost: ${host}\r\nAuthorization: ${authorization}\r\nDepth: 1\r\nContent-Type: text/xml; charset=utf-8\r\nContent-Length: ${bodyBytes.length}\r\nConnection: close\r\n\r\n${PROPFIND_BODY}`;
}

function utf8ByteLengthAt(value: string, position: number): number {
  const code = value.charCodeAt(position);
  if (code <= 0x7F) {
    return 1;
  }
  if (code <= 0x7FF) {
    return 2;
  }
  if (code >= 0xD800 && code <= 0xDBFF && position + 1 < value.length) {
    const next = value.charCodeAt(position + 1);
    if (next >= 0xDC00 && next <= 0xDFFF) {
      return 4;
    }
  }
  return 3;
}

// 从 position 起按字节预算消费完整 UTF-8 字符，返回数据结尾的字符下标。
// chunk 大小以字节计，而 body 已是解码后的字符串，逐字符累加字节长度，
// 在恰好消费 size 字节或即将切断某个字符时停止。
function stepChunkDataEnd(body: string, position: number, size: number): number {
  let index = position;
  let consumed = 0;
  while (index < body.length && consumed < size) {
    const charLen = utf8ByteLengthAt(body, index);
    if (consumed + charLen > size) {
      break;
    }
    consumed += charLen;
    const code = body.charCodeAt(index);
    index += code >= 0xD800 && code <= 0xDBFF && charLen === 4 ? 2 : 1;
  }
  return index;
}

export function parseRawHttpPropfindResponse(responseText: string): string {
  const separator = responseText.indexOf('\r\n\r\n');
  const status = /^HTTP\/\d(?:\.\d)?\s+(\d+)/.exec(responseText);
  if (separator < 0 || status === null) {
    throw new Error('WebDAV 响应格式无效。');
  }
  const statusCode = Number(status[1]);
  if (statusCode !== 207 && statusCode !== 200) {
    throw new Error(`WebDAV 请求失败（HTTP ${statusCode}）。`);
  }
  const headers = responseText.substring(0, separator).toLowerCase();
  const body = responseText.substring(separator + 4);
  if (!/(?:^|\r\n)transfer-encoding:\s*[^\r\n]*chunked/i.test(headers)) {
    return body;
  }
  let position = 0;
  let decoded = '';
  while (true) {
    const lineEnd = body.indexOf('\r\n', position);
    if (lineEnd < 0) {
      throw new Error('WebDAV 分块响应格式无效。');
    }
    const sizeText = body.substring(position, lineEnd).split(';')[0].trim();
    if (!/^[0-9a-f]+$/i.test(sizeText)) {
      throw new Error('WebDAV 分块响应长度无效。');
    }
    const size = parseInt(sizeText, 16);
    position = lineEnd + 2;
    if (size === 0) {
      return decoded;
    }
    // 按字节预算走到数据结尾，正常情况下 trailer \r\n 紧跟其后。
    let dataEnd = stepChunkDataEnd(body, position, size);
    let trailerPos = dataEnd;
    if (body.substring(trailerPos, trailerPos + 2) !== '\r\n') {
      // 声明字节数把 trailer 字节误算进数据，或切断了多字节序列：
      // 以数据区内最后一个 \r\n 为锚点，截断到其前的完整字符边界。
      const anchored = body.lastIndexOf('\r\n', dataEnd);
      if (anchored < position) {
        throw new Error('WebDAV 分块响应不完整。');
      }
      trailerPos = anchored;
    }
    decoded += body.substring(position, trailerPos);
    position = trailerPos + 2;
  }
}

function isAbsoluteHttpUrl(value: string): boolean {
  return /^https?:\/\/[^/?#]+(?:\/[^?#]*)?(?:\?[^#]*)?(?:#.*)?$/i.test(value);
}

function decodePath(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch (_) {
    return value;
  }
}

function encodePath(path: string): string {
  const segments = path.split('/');
  const encoded: string[] = [];
  for (let index = 0; index < segments.length; index++) {
    encoded.push(encodeURIComponent(decodePath(segments[index])));
  }
  return encoded.join('/');
}

export function joinWebDavUrl(baseUrl: string, relativePath: string): string {
  if (!isAbsoluteHttpUrl(baseUrl)) {
    return '';
  }
  if (isAbsoluteHttpUrl(relativePath)) {
    const schemeEnd = relativePath.indexOf('://') + 3;
    const firstPath = relativePath.indexOf('/', schemeEnd);
    const origin = firstPath < 0 ? relativePath : relativePath.substring(0, firstPath);
    const path = firstPath < 0 ? '/' : relativePath.substring(firstPath).split(/[?#]/)[0];
    return `${origin}${encodePath(path)}`;
  }
  const schemeEnd = baseUrl.indexOf('://') + 3;
  const firstPath = baseUrl.indexOf('/', schemeEnd);
  const origin = firstPath < 0 ? baseUrl : baseUrl.substring(0, firstPath);
  const rawBasePath = firstPath < 0 ? '/' : baseUrl.substring(firstPath).split(/[?#]/)[0];
  const path = relativePath.indexOf('/') === 0 ? relativePath : `${rawBasePath.endsWith('/') ? rawBasePath : `${rawBasePath}/`}${relativePath}`;
  const parts = path.split('/');
  const normalized: string[] = [];
  for (let index = 0; index < parts.length; index++) {
    const part = parts[index];
    if (part.length === 0 || part === '.') {
      continue;
    }
    if (part === '..') {
      normalized.pop();
    } else {
      normalized.push(part);
    }
  }
  const trailingSlash = relativePath.endsWith('/');
  return `${origin}/${encodePath(normalized.join('/'))}${trailingSlash ? '/' : ''}`;
}

function xmlValue(xml: string, name: string): string {
  const match = new RegExp(`<[^>]*:?${name}[^>]*>([\\s\\S]*?)<\\/[^>]*:?${name}>`, 'i').exec(xml);
  return match === null ? '' : decodePath(match[1].replace(/<[^>]+>/g, '').trim());
}

function isVideo(name: string): boolean {
  const dot = name.lastIndexOf('.');
  return dot >= 0 && VIDEO_EXTENSIONS.indexOf(name.substring(dot + 1).toLowerCase()) >= 0;
}

export function parseWebDavDirectory(xml: string, requestedUrl: string): WebDavEntry[] {
  const entries: WebDavEntry[] = [];
  const blocks = xml.match(/<[^>]*:?response[\s>][\s\S]*?<\/[^>]*:?response>/gi) ?? [];
  const currentPath = requestedUrl.replace(/^https?:\/\/[^/]+/i, '').replace(/\/$/, '');
  for (let index = 0; index < blocks.length; index++) {
    const block = blocks[index];
    const href = xmlValue(block, 'href');
    const isDirectory = /<[^>]*:?collection\b/i.test(block);
    const rawPath = href.replace(/^https?:\/\/[^/]+/i, '').replace(/\/$/, '');
    if (href.length === 0 || rawPath === currentPath) {
      continue;
    }
    const fallbackName = decodePath(rawPath.substring(rawPath.lastIndexOf('/') + 1));
    const name = xmlValue(block, 'displayname') || fallbackName;
    if (name.length === 0 || (!isDirectory && !isVideo(name))) {
      continue;
    }
    const sizeText = xmlValue(block, 'getcontentlength');
    const size = /^[0-9]+$/.test(sizeText) ? Number(sizeText) : 0;
    entries.push({ name, url: joinWebDavUrl(requestedUrl, href), isDirectory, size });
  }
  return entries.sort((left, right) => {
    if (left.isDirectory !== right.isDirectory) {
      return left.isDirectory ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });
}

export class WebDavService {
  private readonly context: common.Context;

  constructor(context: common.Context) {
    this.context = context;
  }

  async loadSavedConfig(): Promise<WebDavConfig> {
    const store = await preferences.getPreferences(this.context, 'webdav');
    const text = store.getSync(CONFIG_KEY, '') as string;
    if (text.length === 0) {
      return { endpoint: '', username: '', password: '' };
    }
    try {
      return sanitizeWebDavConfig(JSON.parse(text) as WebDavConfig);
    } catch (_) {
      return { endpoint: '', username: '', password: '' };
    }
  }

  async saveConfig(config: WebDavConfig): Promise<void> {
    const store = await preferences.getPreferences(this.context, 'webdav');
    try {
      store.putSync(CONFIG_KEY, JSON.stringify(sanitizeWebDavConfig(config)));
    } catch (_) {
      // endpoint 无效时保持已保存的配置不变，避免覆盖此前的有效配置
      return;
    }
    await store.flush();
  }

  async listDirectory(config: WebDavConfig, directoryUrl?: string): Promise<WebDavEntry[]> {
    const url = directoryUrl ?? config.endpoint;
    if (!isAbsoluteHttpUrl(url)) {
      throw new Error('WebDAV 地址必须以 http:// 或 https:// 开头。');
    }
    if (url.toLowerCase().startsWith('http://')) {
      return this.listHttpDirectory(url, config);
    }
    const request = http.createHttp();
    try {
      const response = await request.request(url, createPropfindRequestOptions(config.username, config.password));
      if (response.responseCode !== 207 && response.responseCode !== 200) {
        throw new Error(`WebDAV 请求失败（HTTP ${response.responseCode}）。`);
      }
      return parseWebDavDirectory(response.result as string, url);
    } finally {
      request.destroy();
    }
  }

  private async listHttpDirectory(url: string, config: WebDavConfig): Promise<WebDavEntry[]> {
    const match = /^http:\/\/([^/?#]+)(\/[^?#]*)?(?:\?[^#]*)?$/i.exec(url);
    if (match === null) {
      throw new Error('WebDAV HTTP 地址格式无效。');
    }
    const host = match[1];
    const portMatch = /:(\d+)$/.exec(host);
    const address: socket.NetAddress = {
      address: portMatch === null ? host : host.substring(0, host.length - portMatch[0].length),
      port: portMatch === null ? 80 : Number(portMatch[1]),
      family: 1
    };
    const path = match[2] ?? '/';
    if (hasControlCharacters(host) || hasControlCharacters(path)) {
      throw new Error('WebDAV HTTP 地址包含无效字符。');
    }
    const authorization = buildBasicAuthorization(config.username, config.password);
    const requestText = buildRawPropfindRequest(host, authorization).replace('PROPFIND / HTTP/1.1', `PROPFIND ${path} HTTP/1.1`);
    const tcp = socket.constructTCPSocketInstance();

    return new Promise<WebDavEntry[]>((resolve, reject) => {
      let responseText = '';
      let completed = false;
      const finish = (error?: Error): void => {
        if (completed) {
          return;
        }
        completed = true;
        clearTimeout(timeoutId);
        tcp.close();
        if (error !== undefined) {
          reject(error);
          return;
        }
        try {
          resolve(parseWebDavDirectory(parseRawHttpPropfindResponse(responseText), url));
        } catch (parseError) {
          reject(parseError instanceof Error ? parseError : new Error('WebDAV 响应解析失败。'));
        }
      };
      const timeoutId = setTimeout(() => finish(new Error('WebDAV 请求超时。')), 120000);

      tcp.on('message', (value: socket.SocketMessageInfo) => {
        if (value.message !== undefined && value.message !== null) {
          const chunk = buffer.from(value.message as ArrayBuffer).toString('utf-8');
          if (responseText.length + chunk.length > MAX_HTTP_RESPONSE_BYTES) {
            finish(new Error('WebDAV 响应过大。'));
            return;
          }
          responseText += chunk;
        }
      });
      tcp.on('close', () => finish());
      tcp.on('error', () => finish(new Error('WebDAV 网络连接失败。')));
      tcp.connect({ address, timeout: 90000 })
        .then(() => tcp.send({ data: buffer.from(requestText, 'utf-8').buffer }))
        .catch(() => finish(new Error('WebDAV 网络连接失败。')));
    });
  }
}
