export type CapabilityFallback = 'supported' | 'rejected' | 'no-op' | 'software-fallback';

export interface CapabilityDecision {
  name: string;
  minimumApi: number;
  currentApi: number;
  outcome: CapabilityFallback;
}

export interface ApiLevelProvider {
  getApiLevel(): number;
}

export class CapabilityProbe {
  constructor(private readonly apiLevelProvider: ApiLevelProvider) {}

  evaluate(name: string, minimumApi: number, fallback: Exclude<CapabilityFallback, 'supported'>): CapabilityDecision {
    const currentApi = this.apiLevelProvider.getApiLevel();
    return {
      name,
      minimumApi,
      currentApi,
      outcome: currentApi >= minimumApi ? 'supported' : fallback
    };
  }
}
