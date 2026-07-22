import { PlayerError } from '../public/types';

const SENSITIVE_QUERY_NAMES: string[] = ['access_token', 'apikey', 'api_key', 'auth', 'password', 'token'];

function isSensitiveName(name: string): boolean {
  const normalized = name.toLowerCase();
  return SENSITIVE_QUERY_NAMES.indexOf(normalized) >= 0 || normalized.indexOf('token') >= 0;
}

export function redactText(value: string): string {
  let redacted = value.replace(/(authorization\s*[:=]\s*)([^\s,;]+)/gi, '$1[REDACTED]');
  redacted = redacted.replace(/(password\s*[:=]\s*)([^\s,;]+)/gi, '$1[REDACTED]');
  redacted = redacted.replace(/([?&](?:access_token|apikey|api_key|auth|password|token)=[^&#\s]*)/gi, '[REDACTED_QUERY]');
  redacted = redacted.replace(/file:\/\/[^\s'"?]+/gi, 'file://[REDACTED_PATH]');
  return redacted;
}

export function redactContext(context: Record<string, string | number | boolean>): Record<string, string | number | boolean> {
  const result: Record<string, string | number | boolean> = {};
  const keys = Object.keys(context);
  for (let index = 0; index < keys.length; index++) {
    const key = keys[index];
    const value = context[key];
    if (isSensitiveName(key) || key.toLowerCase() === 'authorization') {
      result[key] = '[REDACTED]';
    } else if (typeof value === 'string') {
      result[key] = redactText(value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

export function redactError(error: PlayerError): PlayerError {
  return {
    domain: error.domain,
    code: error.code,
    message: redactText(error.message),
    retryable: error.retryable,
    context: redactContext(error.context)
  };
}
