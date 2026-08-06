import { PlayerTrack } from '@vidall/player';

export type NativeTrack = PlayerTrack;

export interface TrackGroups {
  audio: NativeTrack[];
  subtitle: NativeTrack[];
  video: NativeTrack[];
}

export function splitTracks(tracks: NativeTrack[]): TrackGroups {
  const audio: NativeTrack[] = [];
  const subtitle: NativeTrack[] = [];
  const video: NativeTrack[] = [];
  for (let index = 0; index < tracks.length; index++) {
    const track = tracks[index];
    if (track.id === undefined || track.id <= 0) {
      continue;
    }
    if (track.kind === 'audio') {
      audio.push(track);
    } else if (track.kind === 'subtitle') {
      subtitle.push(track);
    } else if (track.kind === 'video') {
      video.push(track);
    }
  }
  return { audio, subtitle, video };
}

export function trackLabel(track: NativeTrack): string {
  const title = track.title?.trim() ?? '';
  const language = track.language?.trim() ?? '';
  // 构建扩展信息：编码/配置文件/码率等
  const extras: string[] = [];
  if (track.codec !== undefined && track.codec.length > 0) {
    extras.push(track.codec);
  }
  if (track.profile !== undefined && track.profile.length > 0) {
    extras.push(track.profile);
  }
  if (track.sampleRate !== undefined) {
    extras.push(`${track.sampleRate}Hz`);
  }
  if (track.channels !== undefined) {
    extras.push(`${track.channels}ch`);
  }
  if (track.bitrate !== undefined && track.bitrate > 0) {
    extras.push(`${Math.round(track.bitrate / 1000)}kbps`);
  }
  if (track.fps !== undefined) {
    extras.push(`${track.fps}fps`);
  }
  if (track.resolution !== undefined) {
    extras.push(track.resolution);
  }
  const extraStr = extras.length > 0 ? ` [${extras.join(' ')}]` : '';
  if (title.length > 0 && language.length > 0) {
    return `${title} (${language})${extraStr}`;
  }
  if (title.length > 0) {
    return `${title}${extraStr}`;
  }
  if (language.length > 0) {
    return `${language}${extraStr}`;
  }
  return `轨道 ${track.id ?? '?'}${extraStr}`;
}
