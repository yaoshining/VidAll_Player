#!/usr/bin/env python3
"""S38核心流程页：复用已有手动返回门槛，保持原始CI HAR不变。"""
import argparse, hashlib, shutil
from pathlib import Path
from prepare_anchor import transform as add_anchor
ROOT = Path(__file__).resolve().parents[3]
def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('验收页位置漂移：' + before)
    return text.replace(before, after, 1)
def prepare(project):
    har = project / 'entry/libs/current.har'
    digest = hashlib.sha256(har.read_bytes()).hexdigest()
    pages = project / 'entry/src/main/ets/pages'
    for source in (ROOT / 'fixtures/normal-core-consumer/audio-evidence').glob('*.ets'):
        shutil.copyfile(source, pages / source.name)
    source = (pages / 'Index.ets').read_text()
    original = (ROOT / 'fixtures/normal-core-consumer/recovery-terminal/Index.ets').read_text()
    begin = original.index('  private chooseRecovery(')
    end = original.index('  private async finish()', begin)
    source = once(source, 'struct Index {', "struct Index {\n  @State navigation: string = '';")
    source = once(source, '  private async finish()', original[begin:end] + '  private async finish()')
    source = once(source, "    this.record('bad-media-returned'); this.errors = 0;", "    await this.waitForRecoveryNavigation();\n    this.record('bad-media-returned'); this.errors = 0;")
    source = once(source, "    this.active();\n    await initializePlayerRuntime", """    const otherData = await this.context.resourceManager.getRawFileContent('second_video.mp4');
    const otherFile = fs.openSync(this.root + '/second_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try { fs.writeSync(otherFile.fd, otherData.buffer); } finally { fs.closeSync(otherFile); }
    this.active();
    await initializePlayerRuntime""")
    source = once(source, "uri: 'file://' + this.root + '/test_video.mp4' },", "uri: 'file://' + this.root + (generation === 1 ? '/test_video.mp4' : '/second_video.mp4') },")
    source = once(source, "    this.record('open-diagnostics', JSON.stringify(await player.getDiagnostics()));", """    const qualified = await player.getDiagnostics();
    this.record('open-diagnostics', JSON.stringify(qualified));
    if (qualified.fields.hardwareDecoder.value !== 'ohcodec' || qualified.fields.renderBackend.value !== 'vulkan') throw new Error('HARDWARE_PATH_MISSING');""")
    source = once(source, "    await first.seekPercent(200 / 3);", "    this.record('seek-request'); await first.seekPercent(200 / 3);")
    source = once(source, "    await first.release(); this.record('release-ok');", "    await this.delay(5000); this.record('release-request');\n    await first.release(); this.record('release-ok');")
    source = once(source, "    await second.release(); this.record('reopen-release-ok');", "    this.record('reopen-release-request');\n    await second.release(); this.record('reopen-release-ok');")
    source = once(source, "      await this.capture.finish();\n      this.status = '内录完成", "      await this.capture.finish();\n      this.record('capture-flow-completed');\n      this.status = '内录完成")
    manual = """      if (this.awaitingManualResume) {
        Button('手动继续播放').id('audio-manual-resume').defaultFocus(true).onClick(() => { this.acceptManualResume(); })
      }
"""
    source = once(source, manual, '')
    source = once(source, '      Column() {', '      if (!this.captureBusy) {\n      Column() {')
    source = once(source, "    }.width('100%').height('100%').backgroundColor(Color.Black)", """      }
""" + manual + """      if (this.navigation === 'failed') {
        Button('返回视频列表').margin({ top: 300 }).onClick(() => { this.chooseRecovery('return'); })
      }
      if (this.navigation === 'list') {
        Button('播放另一部视频').margin({ top: 300 }).onClick(() => { this.chooseRecovery('open'); })
      }
    }.width('100%').height('100%').backgroundColor(Color.Black)""")
    capture = pages / 'AudioCapture.ets'
    capture.write_text(once(capture.read_text(), 'videoBitrate: 1500000', 'videoBitrate: 400000'))
    source = source.replace("'/phase17-audio'", "'/phase17-core'")
    (pages / 'Index.ets').write_text(add_anchor(source, 'normal'))
    assert hashlib.sha256(har.read_bytes()).hexdigest() == digest
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    prepare(parser.parse_args().project)
