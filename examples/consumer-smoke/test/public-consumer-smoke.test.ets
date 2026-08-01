/*
 * Copyright (c) 2025 VidAll. All rights reserved.
 * Consumer smoke test that imports only the published public SDK surface.
 */

import { describe, it, expect } from '@ohos/hypium';
import { createPlayer, VidAllPlayer, PlayerEvent, PlayerSurface, MediaSource } from '@vidall/player';

const surface: PlayerSurface = {
  componentId: 'consumer-smoke-surface',
  generation: 1,
  width: 1920,
  height: 1080,
};
const source: MediaSource = { kind: 'localFile', uri: 'file:///data/test.mp4' };

export default function publicConsumerSmokeTest() {
  describe('PublicConsumerSmoke', () => {
    it('should_create_a_public_player', 0, () => {
      const player: VidAllPlayer = createPlayer();
      expect(player).assertNotUndefined();
      expect(typeof player.attachSurface).assertEqual('function');
      expect(typeof player.load).assertEqual('function');
      expect(typeof player.subscribe).assertEqual('function');
      player.release();
    });

    it('should_support_surface_load_and_subscription_contracts', 0, () => {
      const player = createPlayer();
      const events: PlayerEvent[] = [];
      const unsubscribe = player.subscribe((event: PlayerEvent) => events.push(event));
      expect(typeof unsubscribe).assertEqual('function');
      const attachPromise: Promise<void> = player.attachSurface(surface);
      const loadPromise: Promise<void> = player.load(source);
      expect(attachPromise).assertNotUndefined();
      expect(loadPromise).assertNotUndefined();
      unsubscribe();
      player.release();
    });

    it('should_create_a_new_player_after_release', 0, () => {
      const first = createPlayer();
      first.release();
      const rebuilt: VidAllPlayer = createPlayer();
      expect(rebuilt).assertNotUndefined();
      expect(typeof rebuilt.release).assertEqual('function');
      rebuilt.release();
    });
  });
}
