import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

const CONFIG_KEY = 'configuration';

export interface SmbConfig {
  host: string;
  share: string;
  path: string;
  username: string;
  password: string;
}

function encodePathPart(value: string): string {
  return encodeURIComponent(value);
}

function normalizePath(value: string): string {
  const parts = value.trim().split('/');
  const normalized: string[] = [];
  for (let index = 0; index < parts.length; index++) {
    const part = parts[index].trim();
    if (part.length === 0 || part === '.') {
      continue;
    }
    if (part === '..') {
      throw new Error('SMB 文件路径不能包含上级目录。');
    }
    normalized.push(part);
  }
  return normalized.join('/');
}

function validateHost(value: string): string {
  const host = value.trim();
  if (host.length === 0 || /[\\/@?#\s]/.test(host)) {
    throw new Error('SMB 服务器地址无效。');
  }
  return host;
}

export function sanitizeSmbConfig(config: SmbConfig): SmbConfig {
  return {
    host: config.host.trim(),
    share: config.share.trim(),
    path: config.path.trim(),
    username: config.username.trim(),
    password: ''
  };
}

export function buildSmbMediaUri(config: SmbConfig): string {
  const host = validateHost(config.host);
  const share = config.share.trim();
  if (share.length === 0 || share.indexOf('/') >= 0 || /[\\@?#]/.test(share)) {
    throw new Error('SMB 共享名无效。');
  }
  const path = normalizePath(config.path);
  const segments: string[] = [encodePathPart(share)];
  if (path.length > 0) {
    const pathParts = path.split('/');
    for (let index = 0; index < pathParts.length; index++) {
      segments.push(encodePathPart(pathParts[index]));
    }
  }
  return `smb://${host}/${segments.join('/')}`;
}

export class SmbService {
  private readonly context: common.Context;

  constructor(context: common.Context) {
    this.context = context;
  }

  async loadSavedConfig(): Promise<SmbConfig> {
    const store = await preferences.getPreferences(this.context, 'smb');
    const text = store.getSync(CONFIG_KEY, '') as string;
    if (text.length === 0) {
      return { host: '', share: '', path: '', username: '', password: '' };
    }
    try {
      return sanitizeSmbConfig(JSON.parse(text) as SmbConfig);
    } catch (_) {
      return { host: '', share: '', path: '', username: '', password: '' };
    }
  }

  async saveConfig(config: SmbConfig): Promise<void> {
    const store = await preferences.getPreferences(this.context, 'smb');
    store.putSync(CONFIG_KEY, JSON.stringify(sanitizeSmbConfig(config)));
    await store.flush();
  }
}
