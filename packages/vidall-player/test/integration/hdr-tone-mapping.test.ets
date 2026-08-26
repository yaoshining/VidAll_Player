import { resolveHdrComputePeak, resolveHdrToneMapping } from '../../src/main/ets/native/nativeBridge';

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

// issue #66：HDR tone mapping 选项必须被确定性映射为 mpv 选项字符串。
// 缺省曲线 bt.2390 是渲染 API 后端（vo_gpu）确定性支持、且 mpv "auto" 最终
// 也解析到 bt.2390 的曲线；显式缺省保证兜底路径不依赖平台 auto 猜测。
export function hdrToneMappingResolverDefaultsToBt2390(): void {
  assert(resolveHdrToneMapping(undefined) === 'bt.2390',
    `undefined hdrToneMapping should default to "bt.2390", got ${resolveHdrToneMapping(undefined)}`);
  assert(resolveHdrToneMapping('bt.2390') === 'bt.2390',
    `"bt.2390" should pass through, got ${resolveHdrToneMapping('bt.2390')}`);
  assert(resolveHdrToneMapping('mobius') === 'mobius',
    `"mobius" should pass through, got ${resolveHdrToneMapping('mobius')}`);
  assert(resolveHdrToneMapping('auto') === 'auto',
    `"auto" should pass through, got ${resolveHdrToneMapping('auto')}`);
  // 非法值必须回退默认曲线，绝不抛异常（兜底路径必须可用）。
  assert(resolveHdrToneMapping('unknown') === 'bt.2390',
    `unknown hdrToneMapping should fall back to "bt.2390", got ${resolveHdrToneMapping('unknown')}`);
}

// hdr-compute-peak：enabled→yes（从 sig-peak 计算峰值），disabled→no，缺省/未知→auto。
export function hdrComputePeakResolverMapsModes(): void {
  assert(resolveHdrComputePeak(undefined) === 'auto',
    `undefined hdrComputePeak should default to "auto", got ${resolveHdrComputePeak(undefined)}`);
  assert(resolveHdrComputePeak('enabled') === 'yes',
    `"enabled" should map to "yes", got ${resolveHdrComputePeak('enabled')}`);
  assert(resolveHdrComputePeak('disabled') === 'no',
    `"disabled" should map to "no", got ${resolveHdrComputePeak('disabled')}`);
  assert(resolveHdrComputePeak('auto') === 'auto',
    `"auto" should pass through, got ${resolveHdrComputePeak('auto')}`);
  assert(resolveHdrComputePeak('unknown') === 'auto',
    `unknown hdrComputePeak should fall back to "auto", got ${resolveHdrComputePeak('unknown')}`);
}
