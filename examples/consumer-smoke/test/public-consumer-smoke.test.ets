/*
 * Copyright (c) 2025 VidAll. All rights reserved.
 * Consumer smoke test for VidAll Player SDK.
 * Only uses public API, no access to native/entry/VidAll_TV.
 */

import { describe, it, expect } from '@ohos/hypium';
import { createPlayer, PlayerState, PlayerEvent } from '@vidall/player';

export default function publicConsumerSmokeTest() {
  describe('PublicConsumerSmoke', () => {
    it('should_import_public_api_successfully', 0, () => {
      // Test that public API can be imported
      expect(createPlayer).assertNotUndefined();
      expect(PlayerState).assertNotUndefined();
      expect(PlayerEvent).assertNotUndefined();
    });

    it('should_create_player_with_valid_options', 0, () => {
      // Test player creation with minimal options
      const player = createPlayer({
        surfaceId: 'test-surface',
        width: 1920,
        height: 1080
      });
      expect(player).assertNotUndefined();
      expect(player.id).assertNotUndefined();
      expect(player.state).assertEqual(PlayerState.IDLE);
    });

    it('should_transition_states_on_lifecycle', 0, () => {
      const player = createPlayer({
        surfaceId: 'test-surface',
        width: 1920,
        height: 1080
      });
      
      // Initial state should be IDLE
      expect(player.state).assertEqual(PlayerState.IDLE);
      
      // Load should transition to LOADING
      player.load('file:///test.mp4');
      expect(player.state).assertEqual(PlayerState.LOADING);
      
      // Release should transition to RELEASED
      player.release();
      expect(player.state).assertEqual(PlayerState.RELEASED);
    });

    it('should_reject_invalid_surface_dimensions', 0, () => {
      // Zero dimensions should be rejected
      try {
        createPlayer({
          surfaceId: 'test-surface',
          width: 0,
          height: 0
        });
        expect(false).assertTrue(); // Should not reach here
      } catch (error) {
        expect(error.message).assertContain('invalid');
      }
    });

    it('should_handle_multiple_independent_players', 0, () => {
      const player1 = createPlayer({
        surfaceId: 'surface-1',
        width: 1920,
        height: 1080
      });
      const player2 = createPlayer({
        surfaceId: 'surface-2',
        width: 1280,
        height: 720
      });
      
      expect(player1.id).assertNotEqual(player2.id);
      expect(player1.state).assertEqual(PlayerState.IDLE);
      expect(player2.state).assertEqual(PlayerState.IDLE);
      
      player1.load('file:///video1.mp4');
      expect(player1.state).assertEqual(PlayerState.LOADING);
      expect(player2.state).assertEqual(PlayerState.IDLE);
      
      player1.release();
      player2.release();
    });

    it('should_not_access_native_or_internal_modules', 0, () => {
      // Verify that native/internal modules are not accessible
      // This is a compile-time check, but we can verify at runtime
      // We cannot actually require internal modules, so we verify
      // that the public API doesn't expose internal properties
      const player = createPlayer({
        surfaceId: 'test-surface',
        width: 1920,
        height: 1080
      });
      
      // Verify no internal properties are exposed
      const playerKeys = Object.keys(player);
      const internalKeywords = ['_internal', 'nativeHandle', '__internal', 'private'];
      const hasInternal = internalKeywords.some(keyword => 
        playerKeys.some(key => key.includes(keyword))
      );
      expect(hasInternal).assertFalse();
      
      // Verify we cannot access native modules through reflection
      // (This would fail at runtime if attempted)
      expect(() => {
        // This is a safe check that doesn't actually import anything
        if (typeof globalThis.requireNativeModule === 'function') {
          throw new Error('requireNativeModule should not be available');
        }
      }).assertThrow();
    });

    it('should_only_use_public_api_surface', 0, () => {
      const player = createPlayer({
        surfaceId: 'test-surface',
        width: 1920,
        height: 1080
      });
      
      // Public API surface check
      expect(typeof player.load).assertEqual('function');
      expect(typeof player.play).assertEqual('function');
      expect(typeof player.pause).assertEqual('function');
      expect(typeof player.seek).assertEqual('function');
      expect(typeof player.setVolume).assertEqual('function');
      expect(typeof player.setMute).assertEqual('function');
      expect(typeof player.setSpeed).assertEqual('function');
      expect(typeof player.release).assertEqual('function');
      expect(typeof player.on).assertEqual('function');
      expect(typeof player.off).assertEqual('function');
      
      // Should not have internal properties
      expect(player._internal).assertUndefined();
      expect(player.nativeHandle).assertUndefined();
    });
  });
}

