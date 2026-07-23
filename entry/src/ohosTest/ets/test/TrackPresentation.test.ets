import { describe, expect, it } from '@ohos/hypium';
import { splitTracks, trackLabel } from '../../../main/ets/player/TrackPresentation';

export default function trackPresentationTest(): void {
  describe('TrackPresentationTest', () => {
    it('separates audio and subtitle tracks while omitting unsupported entries', 0, () => {
      const tracks = splitTracks([
        { id: 1, type: 'audio', lang: 'zh', title: '国语', selected: true },
        { id: 2, type: 'sub', lang: 'en', title: 'English', selected: false },
        { id: 3, type: 'video', title: 'H.264', selected: true }
      ]);

      expect(tracks.audio.length).assertEqual(1);
      expect(tracks.audio[0].id).assertEqual(1);
      expect(tracks.subtitle.length).assertEqual(1);
      expect(tracks.subtitle[0].id).assertEqual(2);
    });

    it('uses title, language, and id fallback labels for tracks', 0, () => {
      expect(trackLabel({ id: 1, type: 'audio', lang: 'zh', title: '国语' })).assertEqual('国语 (zh)');
      expect(trackLabel({ id: 2, type: 'sub', lang: 'en' })).assertEqual('en');
      expect(trackLabel({ id: 3, type: 'audio' })).assertEqual('轨道 3');
    });
  });
}
