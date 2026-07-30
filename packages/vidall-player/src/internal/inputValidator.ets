import { ExternalAudio, ExternalSubtitle, MediaSource } from '../public/types';
import { PlayerFailure } from './playerFailure';

const AUTHORIZATION_HEADER = 'authorization';
const ALLOWED_HEADER_NAMES: string[] = [
  'accept', 'accept-language', 'authorization', 'cookie', 'referer', 'user-agent'
];

export interface ParsedUri {
  scheme: string;
  authority: string;
  path: string;
}

function inputFailure(code: string, message: string): PlayerFailure {
  return new PlayerFailure({
    domain: 'input',
    code,
    message,
    retryable: false,
    context: {}
  });
}

export function parseUri(uri: string): ParsedUri {
  const match = /^([a-z][a-z0-9+.-]*):\/\/([^/?#]*)([^?#]*)?(?:\?[^#]*)?(?:#.*)?$/i.exec(uri);
  if (match === null) {
    throw inputFailure('INVALID_URI', 'Media URI must be an absolute URI.');
  }
  const authority = match[2];
  if (authority.indexOf('@') >= 0) {
    throw inputFailure('URL_USERINFO_FORBIDDEN', 'Media URI must not contain user information.');
  }
  if (authority.length === 0) {
    throw inputFailure('INVALID_URI', 'Network media URI must include a host.');
  }
  return { scheme: match[1].toLowerCase(), authority: authority.toLowerCase(), path: match[3] ?? '' };
}

function validateHeaders(headers?: Record<string, string>): void {
  if (headers === undefined) {
    return;
  }
  const names = Object.keys(headers);
  for (let index = 0; index < names.length; index++) {
    const name = names[index];
    const normalizedName = name.toLowerCase();
    if (ALLOWED_HEADER_NAMES.indexOf(normalizedName) < 0) {
      throw inputFailure('HEADER_NOT_ALLOWED', `Header '${name}' is not allowed.`);
    }
    if (headers[name].indexOf('\r') >= 0 || headers[name].indexOf('\n') >= 0) {
      throw inputFailure('INVALID_HEADER_VALUE', `Header '${name}' contains an invalid line break.`);
    }
  }
}

const SUPPORTED_SUBTITLE_FORMATS: string[] = [
  'srt', 'ass', 'ssa', 'webvtt', 'pgs', 'vobsub'
];

export function validateExternalAudio(audio: ExternalAudio): void {
  if (audio.uri.length === 0) {
    throw inputFailure('INVALID_EXTERNAL_AUDIO', 'External audio URI must not be empty.');
  }
  const uri = parseUri(audio.uri);
  if (uri.scheme !== 'http' && uri.scheme !== 'https') {
    throw inputFailure('UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL',
      '外挂音频仅支持 HTTP/HTTPS (External audio only supports HTTP/HTTPS).');
  }
}

export function validateExternalSubtitle(subtitle: ExternalSubtitle): void {
  if (subtitle.uri.indexOf('file://') === 0) {
    // 本地缓存字幕：业务层先把网络字幕下载到缓存目录，再以 file URI 加载。
    // 仅放行 file:///abs/path（空 authority）与 file://localhost/abs/path，
    // 拒绝 file://evilhost/path、file://relative 等非本地形式，避免原生层按
    // 不可预期的 authority 解析路径。
    const authorityAndPath = subtitle.uri.substring('file://'.length);
    const separatorIndex = authorityAndPath.indexOf('/');
    const authority = separatorIndex >= 0 ? authorityAndPath.substring(0, separatorIndex) : authorityAndPath;
    if (authority.indexOf('@') >= 0) {
      throw inputFailure('URL_USERINFO_FORBIDDEN', 'Media URI must not contain user information.');
    }
    const path = separatorIndex >= 0 ? authorityAndPath.substring(separatorIndex) : '';
    const isLocalAuthority = authority.length === 0 || authority === 'localhost';
    if (!isLocalAuthority || path.indexOf('/') !== 0) {
      throw inputFailure('UNSUPPORTED_SUBTITLE_PROTOCOL',
        '外挂字幕 file URI 仅支持本地绝对路径 file:/// 或 file://localhost/ (External subtitle file URI must be a local absolute path).');
    }
  } else {
    const uri = parseUri(subtitle.uri);
    if (uri.scheme !== 'http' && uri.scheme !== 'https') {
      throw inputFailure('UNSUPPORTED_SUBTITLE_PROTOCOL',
        '外挂字幕仅支持 HTTP/HTTPS 或本地缓存文件协议 (External subtitle only supports HTTP/HTTPS or cached file URIs).');
    }
  }
  if (subtitle.format !== undefined && SUPPORTED_SUBTITLE_FORMATS.indexOf(subtitle.format) < 0) {
    throw inputFailure('UNSUPPORTED_SUBTITLE_FORMAT',
      '不支持的外挂字幕格式 (Unsupported external subtitle format).');
  }
}

function isLoopbackAuthority(authority: string): boolean {
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(authority) ||
    /^\[::1\](?::\d+)?$/.test(authority);
}

// RTSP/UDP/SRT/RTMP 尚未完成单独真机验证，只能列为可选支持；
// 在输入校验直接拒绝并给出稳定错误码，避免静默失败或误导消费者宣称支持。
const UNVERIFIED_OPTIONAL_PROTOCOLS: string[] = ['rtsp', 'rtmp', 'udp', 'srt'];

// direct SMB 已由受控 ARM64 libmpv 制品提供，并在 CI 中完成 ELF 与符号审计。
function isDirectSmbAvailable(): boolean {
  return true;
}

function validateSmbUri(parsed: ParsedUri): void {
  const authority = parsed.authority;
  const hostEnd = authority.indexOf(':');
  const host = (hostEnd >= 0 ? authority.substring(0, hostEnd) : authority).trim();
  if (host.length === 0 || parsed.path.indexOf('/') !== 0) {
    throw inputFailure('INVALID_SMB_URI', 'SMB media URI must include a host and share path.');
  }

  const segments = parsed.path.substring(1).split('/');
  if (segments.length === 0 || segments[0].length === 0) {
    throw inputFailure('INVALID_SMB_URI', 'SMB media URI must include a share name.');
  }
  for (let index = 0; index < segments.length; index++) {
    let decoded: string;
    try {
      decoded = decodeURIComponent(segments[index]);
    } catch (_) {
      throw inputFailure('INVALID_SMB_URI', 'SMB media URI contains invalid path encoding.');
    }
    if (decoded.length === 0 || decoded === '.' || decoded === '..' || decoded.indexOf('/') >= 0 || decoded.indexOf('\\') >= 0) {
      throw inputFailure('INVALID_SMB_URI', 'SMB media URI must not contain unsafe path segments.');
    }
  }
}

export function validateMediaSource(source: MediaSource): void {
  if (source.uri.length === 0) {
    throw inputFailure('INVALID_URI', 'Media URI must not be empty.');
  }
  if (source.kind === 'localFile') {
    if (source.uri.indexOf('file://') !== 0) {
      throw inputFailure('INVALID_LOCAL_FILE_URI', 'Local media must use a file URI without user information.');
    }
    const authorityAndPath = source.uri.substring('file://'.length);
    const separatorIndex = authorityAndPath.indexOf('/');
    const authority = separatorIndex >= 0 ? authorityAndPath.substring(0, separatorIndex) : authorityAndPath;
    if (authority.indexOf('@') >= 0) {
      throw inputFailure('URL_USERINFO_FORBIDDEN', 'Media URI must not contain user information.');
    }
  } else {
    const parsed = parseUri(source.uri);
    if (UNVERIFIED_OPTIONAL_PROTOCOLS.indexOf(parsed.scheme) >= 0) {
      throw inputFailure('PROTOCOL_NOT_VERIFIED',
        `可选协议 ${parsed.scheme} 尚未完成真机验证 (Optional protocol ${parsed.scheme} is not verified on device).`);
    }
    if (source.kind === 'http' && parsed.scheme !== 'http') {
      throw inputFailure('URI_KIND_MISMATCH', 'HTTP media source requires an HTTP URI.');
    }
    if ((source.kind === 'hls' || source.kind === 'dash') && parsed.scheme !== 'http' && parsed.scheme !== 'https') {
      throw inputFailure('URI_KIND_MISMATCH', 'Adaptive media source requires an HTTP or HTTPS URI.');
    }
    if (source.kind === 'https' && parsed.scheme !== 'https') {
      throw inputFailure('URI_KIND_MISMATCH', 'HTTPS media source requires an HTTPS URI.');
    }
    if (source.kind === 'smb' && parsed.scheme !== 'smb') {
      throw inputFailure('URI_KIND_MISMATCH', 'SMB media source requires an SMB URI.');
    }
    if (source.kind === 'smb') {
      validateSmbUri(parsed);
    }
    if (source.kind === 'smb' && !isDirectSmbAvailable()) {
      throw inputFailure('PROTOCOL_NOT_AVAILABLE',
        'Direct SMB is unavailable because the controlled native capability is not verified.');
    }
    if (source.kind === 'localhostProxy' && parsed.scheme !== 'http') {
      throw inputFailure('URI_KIND_MISMATCH',
        'SMB localhost 代理仅支持明文 HTTP 环回地址 (Localhost proxy requires a plain HTTP loopback URI).');
    }
    if (source.kind === 'localhostProxy' && !isLoopbackAuthority(parsed.authority)) {
      throw inputFailure('INVALID_LOCALHOST_PROXY', 'Localhost proxy source must target localhost.');
    }
  }
  validateHeaders(source.headers);
  if (source.externalAudio !== undefined) {
    for (let index = 0; index < source.externalAudio.length; index++) {
      validateExternalAudio(source.externalAudio[index]);
    }
  }
  if (source.externalSubtitles !== undefined) {
    for (let index = 0; index < source.externalSubtitles.length; index++) {
      validateExternalSubtitle(source.externalSubtitles[index]);
    }
  }
}

function normalizeAuthority(scheme: string, authority: string): string {
  const hostEnd = authority.indexOf(':');
  if (hostEnd >= 0) {
    return authority.toLowerCase();
  }
  // 无显式端口时补全默认端口，使 scheme+host 匹配更严格：
  // https 默认 443，http 默认 80，其他协议保持原样。
  if (scheme === 'https') {
    return `${authority.toLowerCase()}:443`;
  }
  if (scheme === 'http') {
    return `${authority.toLowerCase()}:80`;
  }
  return authority.toLowerCase();
}

export function canForwardAuthorization(fromUri: string, redirectUri: string): boolean {
  const from = parseUri(fromUri);
  const target = parseUri(redirectUri);
  return from.scheme === target.scheme &&
    normalizeAuthority(from.scheme, from.authority) === normalizeAuthority(target.scheme, target.authority);
}

export function authorizationHeadersForRedirect(
  headers: Record<string, string> | undefined,
  fromUri: string,
  redirectUri: string
): Record<string, string> | undefined {
  if (headers === undefined || canForwardAuthorization(fromUri, redirectUri)) {
    return headers;
  }
  const filtered: Record<string, string> = {};
  const names = Object.keys(headers);
  for (let index = 0; index < names.length; index++) {
    const name = names[index];
    if (name.toLowerCase() !== AUTHORIZATION_HEADER && name.toLowerCase() !== 'cookie') {
      filtered[name] = headers[name];
    }
  }
  return filtered;
}
