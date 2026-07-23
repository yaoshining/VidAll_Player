import { LibMpvTrack } from 'libentry.so';

export type NativeTrack = LibMpvTrack;

export interface TrackGroups {
  audio: NativeTrack[];
  subtitle: NativeTrack[];
}

export function splitTracks(tracks: NativeTrack[]): TrackGroups {
  const audio: NativeTrack[] = [];
  const subtitle: NativeTrack[] = [];
  for (let index = 0; index < tracks.length; index++) {
    const track = tracks[index];
    if (track.id === undefined || track.id <= 0) {
      continue;
    }
    if (track.type === 'audio') {
      audio.push(track);
    } else if (track.type === 'sub') {
      subtitle.push(track);
    }
  }
  return { audio, subtitle };
}

export function trackLabel(track: NativeTrack): string {
  const title = track.title?.trim() ?? '';
  const language = track.lang?.trim() ?? '';
  if (title.length > 0 && language.length > 0) {
    return `${title} (${language})`;
  }
  if (title.length > 0) {
    return title;
  }
  if (language.length > 0) {
    return language;
  }
  return `轨道 ${track.id ?? '?'}`;
}
