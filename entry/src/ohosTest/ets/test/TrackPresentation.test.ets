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

    // 回归测试：验证 selected 状态在 splitTracks 后保持正确，
    // 对应 C++ GetTracks 用 aid/sid 自行计算 selected 的修复。
    it('preserves selected state per track after splitting', 0, () => {
      const tracks = splitTracks([
        { id: 1, type: 'audio', lang: 'zh', selected: true },
        { id: 2, type: 'audio', lang: 'ja', selected: false },
        { id: 3, type: 'sub', lang: 'zh', selected: false },
        { id: 4, type: 'sub', lang: 'en', selected: true }
      ]);

      expect(tracks.audio.length).assertEqual(2);
      expect(tracks.audio[0].selected).assertTrue();
      expect(tracks.audio[1].selected).assertFalse();
      expect(tracks.subtitle.length).assertEqual(2);
      expect(tracks.subtitle[0].selected).assertFalse();
      expect(tracks.subtitle[1].selected).assertTrue();
    });

    // 回归测试：切换音轨后只有新选中轨道 selected=true，
    // 模拟 aid/sid 计算覆盖 track-list/selected 的场景。
    it('reflects track switch by updating selected to new track', 0, () => {
      // 初始状态：aid=1 选中
      const before = splitTracks([
        { id: 1, type: 'audio', lang: 'zh', selected: true },
        { id: 2, type: 'audio', lang: 'en', selected: false }
      ]);
      expect(before.audio[0].selected).assertTrue();
      expect(before.audio[1].selected).assertFalse();

      // 切换后：aid=2 选中（模拟 GetTracks 重新读 aid/sid 计算 selected）
      const after = splitTracks([
        { id: 1, type: 'audio', lang: 'zh', selected: false },
        { id: 2, type: 'audio', lang: 'en', selected: true }
      ]);
      expect(after.audio[0].selected).assertFalse();
      expect(after.audio[1].selected).assertTrue();
    });

    // 回归测试：关闭字幕后所有字幕轨 selected=false
    it('marks all subtitle tracks unselected when subtitle is off', 0, () => {
      const tracks = splitTracks([
        { id: 1, type: 'audio', lang: 'zh', selected: true },
        { id: 2, type: 'sub', lang: 'en', selected: false },
        { id: 3, type: 'sub', lang: 'zh', selected: false }
      ]);

      expect(tracks.subtitle.every(t => t.selected === false)).assertTrue();
    });

    it('skips tracks with missing or invalid id', 0, () => {
      const tracks = splitTracks([
        { id: 0, type: 'audio', lang: 'zh' },
        { id: -1, type: 'sub', lang: 'en' },
        { id: 1, type: 'audio', lang: 'ja', selected: true }
      ]);

      expect(tracks.audio.length).assertEqual(1);
      expect(tracks.audio[0].id).assertEqual(1);
      expect(tracks.subtitle.length).assertEqual(0);
    });
  });
}
