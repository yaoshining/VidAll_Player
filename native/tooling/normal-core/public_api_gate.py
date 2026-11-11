"""正式与内部诊断核心共用的公开 ABI 契约。"""

EXTENSION_SYMBOLS = frozenset({
    'mpv_ohcodec_terminal_api_version', 'mpv_ohcodec_terminal_register',
    'mpv_ohcodec_terminal_enable', 'mpv_ohcodec_terminal_snapshot',
    'mpv_host_recovery_api_version', 'mpv_host_recovery_generation',
    'mpv_host_recovery_audio_pending', 'mpv_host_recovery_stop_audio',
    'mpv_host_loadfile_async', 'mpv_host_fault_snapshot',
})


def require_public_api(exports, baseline):
    baseline = list(baseline)
    if len(baseline) != 54 or len(set(baseline)) != 54:
        raise ValueError('基线公开 ABI 必须为 54 个独立符号')
    exports = {name.split('@')[0] for name in exports}
    if any(name.startswith(('mp_host_', 'mp_ohcodec_terminal_', 'host_probe_')) for name in exports):
        raise ValueError('内部恢复或诊断符号不得导出')
    public = {name for name in exports if name.startswith('mpv_')}
    expected = set(baseline) | EXTENSION_SYMBOLS
    if len(expected) != 64 or public != expected:
        raise ValueError(f'公开 ABI 不匹配：缺失 {sorted(expected-public)}，多余 {sorted(public-expected)}')
    return set(EXTENSION_SYMBOLS)
