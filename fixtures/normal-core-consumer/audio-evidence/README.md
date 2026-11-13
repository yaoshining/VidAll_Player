# 独立系统内录验收页

将本目录全部 `.ets` 文件复制到独立 HAR 消费工程的 `entry/src/main/ets/pages/`，使用原始 iMac CI HAR 和原有30秒 H.264/AAC 440Hz素材。完整构建 release HAP；不修改 HAR，不混入旧桥。目标声明 tv/tablet，当前原生交付仅 ARM64。

点击“开始系统内录回归”，在系统授权面板确认后才开始播放。录制使用 API12 起提供的 AVScreenCaptureRecorder，不开启麦克风，不豁免隐私窗口。若设备不支持录屏/拒绝授权，应记录失败，不能降级成输入 PCM 或日志伪装声音证据。

本页覆盖坏片报错后开正常视频、暂停/手动恢复、seek、正常关闭后静音、重新打开另一会话后有音以及最终关闭静音。所有区间仍使用同一440Hz素材；**本页不证明故障旧音隔离**。关闭/全局故障须使用下述独立探针。

“系统打断与手动恢复内录”模式创建1320Hz Alarm流并设为 INDEPENDENT_MODE，由系统管理竞争。流程不会调用 Player.pause 来制造打断：必须观察 paused 和进度静止、竞争流实际请求数据；释放 Alarm 后等待“手动继续播放”，才调用 Player.play 并核对进度。仍须从同轮系统日志证明焦点事件，并审阅内录的声音/静音区间；这些宿主断言不证明实机焦点或可听声音。

`filesDir/phase17-audio/` 保存 `capture.mp4` 与 `events.jsonl`。导出后按 scripts/test/audio-evidence/README.md 提取实际音轨，与画面及事件校准区间；录制开始通知的时刻不能直接当作精确的编码音轨零点。不得凭页面“内录完成”标记整体通过。

录制一次性且不自动重试；提前停止、系统错误、被抢占或隐私窗口均使证据失败。初始化尚未归还时，退出请求等待原调用完成后清理，不并发释放；release 未确认时保留 recorder/fd，不强关。平台调用永久挂起属于验收工具阻塞，不能报成功或反复创建录制实例。

## 两组故障探针录制

在保留 T044 对应诊断 HAR、素材与签名配置的独立工程中执行：

```sh
python3 scripts/test/audio-evidence/prepare.py --probe recovery-fence --project /tmp/vidall-t045-fence-audio-tablet
python3 scripts/test/audio-evidence/prepare.py --probe recovery-terminal --project /tmp/vidall-t045-global-audio-tablet
```

脚本只改消费页面，不替换HAR。源码接入点发生漂移即拒绝；保留原四/三Surface、故障归属、硬件资格、手动返回与晚关闭日志确认。开始按钮等待系统内录授权后才运行原流程，结束后再记录2.5秒静音。全局探针保持 hardware-first；故障前880Hz、恢复后440Hz。原诊断README的PID/原生日志检查仍全部适用。

完整当前包及逐库/页面哈希见 `specs/017-host-survival/device-evidence/t045-full-audio-preparation.json`。三包使用不同版本号和名称以便云端辨认，均为本地消费HAP；正常HAR来源为iMac CI，诊断HAR沿用本地T044已绑定来源。其中1.0.45已在API24云平板执行并暴露两项失败；见T045设备记录。1.0.46/47未确认上传或执行，不能与此前初版内录包混淆。

T047在普通/焦点页显示最近12条录制阶段/状态，每行最多160字符，便于云端日志不可取时定位。create/init/start等调用返回与系统STARTED分别记录；不能把start-returned视为录制成功。没有改变原始HAR、15秒期限或声音验收门槛。

T048 将同样的有界阶段显示加入两组生成的故障页，并从 T046 当前生产输入重新构建诊断核心及完整 HAR。后续使用 1.0.50/1.0.51，来源与九库记录见 `specs/017-host-survival/device-evidence/t048-current-probes/`；上面的 T044/T045 包只保留为历史证据。新包尚未完成设备验收。

T052：云端授权及操作往返超过原15秒窗口时会使诊断提前失败。独立工具现在最多等60秒真实STARTED，参数限制1–60000毫秒；逾时、拒绝及迟到事件仍失败，不改HAR或生产故障截止。

T054：录制关闭后，可显式点“复制事件”或“复制内录”，使用云调试“剪贴板同步 → 从远程真机获取”接收 JSON。仅访问本应用固定目录的 `events.jsonl` / `capture.mp4`，文件上限16MiB，每块256KiB，附总长度、SHA-256、块数和序号；“下一块”前确认当前块已保存，失败用“重发本块”。不读取系统剪贴板，不调用外部上传服务；录制中、离页后或文件变化时拒绝导出。此入口只属于验收页面，HAR不变。

接收文件按序保存为 `chunk-000.json` 等，再运行：

```sh
python3 scripts/test/audio-evidence/receive.py --out /tmp/capture.mp4 /tmp/chunk-*.json
```

接收端验证版本、类型、边界、顺序、长度与完整SHA-256；相同重发允许，冲突/缺失/截断均失败。全部验证通过才创建目标文件，不覆盖已有证据。传输通过仅证明文件完整，音轨仍需与同轮事件时间和PID对齐分析；实际平台传输能力须单独记录。
