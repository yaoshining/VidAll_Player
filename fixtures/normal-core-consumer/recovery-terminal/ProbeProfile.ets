import { ProbeProfile } from './ProbeChecks';

// 真机默认必须证明 OHCodec/Vulkan；模拟器对照需显式替换配置并独立记录。
export const PROBE_PROFILE: ProbeProfile = 'hardware-first';
