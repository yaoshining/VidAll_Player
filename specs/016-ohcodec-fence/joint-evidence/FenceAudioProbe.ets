import audio from '@ohos.multimedia.audio';
import display from '@ohos.display';
import { VpeEnhancerUtil } from '../utils/VpeEnhancerUtil';

export class AudioOutputProbe {
  static capabilities(): string {
    const descriptors = audio.getAudioManager().getRoutingManager()
      .getPreferredOutputDeviceForRendererInfoSync({ usage: audio.StreamUsage.STREAM_USAGE_MOVIE, rendererFlags: 0 });
    const screen = display.getDefaultDisplaySync();
    return 'display=' + screen.width + 'x' + screen.height + ' hdr=' + JSON.stringify(screen.hdrFormats) +
      ' vpe=' + VpeEnhancerUtil.isSupported() + ' outputs=' +
      descriptors.map((d: audio.AudioDeviceDescriptor) => d.deviceType + '/' + d.channelCounts.join(',')).join('|');
  }

  static async peaks(): Promise<number[]> {
    const manager = audio.getAudioManager();
    const devices = manager.getRoutingManager().getPreferredOutputDeviceForRendererInfoSync({
      usage: audio.StreamUsage.STREAM_USAGE_MOVIE, rendererFlags: 0
    });
    if (!devices.length) { throw new Error('no output device'); }
    const group = await manager.getVolumeManager().getVolumeGroupManager(audio.DEFAULT_VOLUME_GROUP_ID);
    const peaks: number[] = [];
    for (let n = 0; n < 32; n++) {
      peaks.push(await group.getMaxAmplitudeForOutputDevice(devices[0]));
      await AudioOutputProbe.delay(50);
    }
    return peaks;
  }

  static delay(ms: number): Promise<void> {
    return new Promise<void>((resolve) => { setTimeout(resolve, ms); });
  }

  // 单独申请音频焦点，只输出零值，测得的非零振幅不会来自打断源。
  static async alarm(): Promise<audio.AudioRenderer> {
    const renderer = await audio.createAudioRenderer({
      streamInfo: { samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_48000,
        channels: audio.AudioChannel.CHANNEL_2, sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE,
        encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW },
      rendererInfo: { usage: audio.StreamUsage.STREAM_USAGE_ALARM, rendererFlags: 0 }
    });
    try {
      await renderer.setInterruptMode(audio.InterruptMode.INDEPENDENT_MODE);
      renderer.on('writeData', (buf: ArrayBuffer) => { new Uint8Array(buf).fill(0); });
      await renderer.start();
      return renderer;
    } catch (error) {
      await renderer.release();
      throw new Error('alarm could not start: ' + String(error));
    }
  }
}
