import { ExternalSubtitle, MediaSource } from '../public/types';
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

function validateSubtitle(subtitle: ExternalSubtitle): void {
  parseUri(subtitle.uri);
}

function isLoopbackAuthority(authority: string): boolean {
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(authority) ||
    /^\[::1\](?::\d+)?$/.test(authority);
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
    if (source.kind === 'http' && parsed.scheme !== 'http') {
      throw inputFailure('URI_KIND_MISMATCH', 'HTTP media source requires an HTTP URI.');
    }
    if ((source.kind === 'hls' || source.kind === 'dash') && parsed.scheme !== 'http' && parsed.scheme !== 'https') {
      throw inputFailure('URI_KIND_MISMATCH', 'Adaptive media source requires an HTTP or HTTPS URI.');
    }
    if (source.kind === 'https' && parsed.scheme !== 'https') {
      throw inputFailure('URI_KIND_MISMATCH', 'HTTPS media source requires an HTTPS URI.');
    }
    if (source.kind === 'localhostProxy' && !isLoopbackAuthority(parsed.authority)) {
      throw inputFailure('INVALID_LOCALHOST_PROXY', 'Localhost proxy source must target localhost.');
    }
  }
  validateHeaders(source.headers);
  if (source.externalSubtitles !== undefined) {
    for (let index = 0; index < source.externalSubtitles.length; index++) {
      validateSubtitle(source.externalSubtitles[index]);
    }
  }
}

export function canForwardAuthorization(fromUri: string, redirectUri: string): boolean {
  const from = parseUri(fromUri);
  const target = parseUri(redirectUri);
  return from.scheme === target.scheme && from.authority === target.authority;
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
