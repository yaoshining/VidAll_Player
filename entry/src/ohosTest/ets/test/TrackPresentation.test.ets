import { describe, expect, it } from '@ohos/hypium';
import { splitTracks, trackLabel, NativeTrack } from '../../../main/ets/player/TrackPresentation';

export default function trackPresentationTest(): void {
  describe('TrackPresentationTest', () => {
    it('separates audio and subtitle tracks while omitting unsupported entries', 0, () => {
      const tracks = splitTracks([
        { id: 1, kind: 'audio', language: 'zh', title: '国语', selected: true, recognitionStatus: 'recognized' },
        { id: 2, kind: 'subtitle', language: 'en', title: 'English', selected: false, recognitionStatus: 'recognized' },
        { id: 3, kind: 'video', title: 'H.264', selected: true, recognitionStatus: 'recognized' }
      ]);

      expect(tracks.audio.length).assertEqual(1);
      expect(tracks.audio[0].id).assertEqual(1);
      expect(tracks.subtitle.length).assertEqual(1);
      expect(tracks.subtitle[0].id).assertEqual(2);
    });

    it('uses title, language, and id fallback labels for tracks', 0, () => {
      expect(trackLabel({ id: 1, kind: 'audio', language: 'zh', title: '国语', recognitionStatus: 'recognized', selected: false })).assertEqual('国语 (zh)');
      expect(trackLabel({ id: 2, kind: 'subtitle', language: 'en', recognitionStatus: 'recognized', selected: false })).assertEqual('en');
      expect(trackLabel({ id: 3, kind: 'audio', recognitionStatus: 'recognized', selected: false })).assertEqual('轨道 3');
    });

    // 回归测试：验证 selected 状态在 splitTracks 后保持正确，
    // 对应 C++ GetTracks 用 aid/sid 自行计算 selected 的修复。
    it('preserves selected state per track after splitting', 0, () => {
      const tracks = splitTracks([
        { id: 1, kind: 'audio', language: 'zh', selected: true, recognitionStatus: 'recognized' },
        { id: 2, kind: 'audio', language: 'ja', selected: false, recognitionStatus: 'recognized' },
        { id: 3, kind: 'subtitle', language: 'zh', selected: false, recognitionStatus: 'recognized' },
        { id: 4, kind: 'subtitle', language: 'en', selected: true, recognitionStatus: 'recognized' }
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
        { id: 1, kind: 'audio', language: 'zh', selected: true, recognitionStatus: 'recognized' },
        { id: 2, kind: 'audio', language: 'en', selected: false, recognitionStatus: 'recognized' }
      ]);
      expect(before.audio[0].selected).assertTrue();
      expect(before.audio[1].selected).assertFalse();

      // 切换后：aid=2 选中（模拟 GetTracks 重新读 aid/sid 计算 selected）
      const after = splitTracks([
        { id: 1, kind: 'audio', language: 'zh', selected: false, recognitionStatus: 'recognized' },
        { id: 2, kind: 'audio', language: 'en', selected: true, recognitionStatus: 'recognized' }
      ]);
      expect(after.audio[0].selected).assertFalse();
      expect(after.audio[1].selected).assertTrue();
    });

    // 回归测试：关闭字幕后（会话层 selectTrack('subtitle', null) 已将各字幕轨
    // selected 置为 false）splitTracks 应保留该关闭状态，不重新选中任何字幕轨。
    // 状态转换本身由会话/原生契约测试覆盖，本测试只验证纯函数的保留语义。
    it('preserves the off state of all subtitle tracks', 0, () => {
      const tracks = splitTracks([
        { id: 1, kind: 'audio', language: 'zh', selected: true, recognitionStatus: 'recognized' },
        { id: 2, kind: 'subtitle', language: 'en', selected: false, recognitionStatus: 'recognized' },
        { id: 3, kind: 'subtitle', language: 'zh', selected: false, recognitionStatus: 'recognized' }
      ]);

      expect(tracks.subtitle.every(t => t.selected === false)).assertTrue();
    });

    it('skips tracks with missing or invalid id', 0, () => {
      const tracks = splitTracks([
        { id: 0, kind: 'audio', language: 'zh', recognitionStatus: 'recognized', selected: false },
        { id: -1, kind: 'subtitle', language: 'en', recognitionStatus: 'recognized', selected: false },
        { id: undefined, kind: 'subtitle', language: 'ko', selected: false, recognitionStatus: 'recognized' },
        { id: 1, kind: 'audio', language: 'ja', selected: true, recognitionStatus: 'recognized' }
      ] as NativeTrack[]);

      expect(tracks.audio.length).assertEqual(1);
      expect(tracks.audio[0].id).assertEqual(1);
      expect(tracks.subtitle.length).assertEqual(0);
    });
  });
}
