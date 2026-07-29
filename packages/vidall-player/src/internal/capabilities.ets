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
  private readonly apiLevelProvider: ApiLevelProvider;

  constructor(apiLevelProvider: ApiLevelProvider) {
    this.apiLevelProvider = apiLevelProvider;
  }

  evaluate(name: string, minimumApi: number, fallback: 'rejected' | 'no-op' | 'software-fallback'): CapabilityDecision {
    const currentApi = this.apiLevelProvider.getApiLevel();
    return {
      name,
      minimumApi,
      currentApi,
      outcome: currentApi >= minimumApi ? 'supported' : fallback
    };
  }
}
