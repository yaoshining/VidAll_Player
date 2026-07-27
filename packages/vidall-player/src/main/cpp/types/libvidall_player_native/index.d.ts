export type ProbeCallback = (message: string) => void;

export interface HarNativePackagingProbe {
  ping(): string;
  setCallback(callback: ProbeCallback): string;
}

declare const probe: HarNativePackagingProbe;
export default probe;
