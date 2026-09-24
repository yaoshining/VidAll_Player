# SDK 真机诊断验收探针

探针使用公开 `@vidall/player` API，只有以字符串 Want 参数 `diagnostics79=true` 启动 entry 时进入；正常启动仍是原 demo。每次运行会覆盖 **SDK demo** 模块 files 目录的 `diagnostics79.json`。不要在其它任务占用设备时运行，不要安装或清理消费端 VidAll_TV 包。

1. 用 `generate-fixtures.sh` 生成合成媒体；用 ffprobe 保留参数和 SHA-256。
2. 通过 `devecocli build --modules entry@default` 构建、`devecocli run --module entry --device SERIAL --skip-build` 安装 SDK demo。
3. 用 `hdc -t SERIAL file send -b com.yaoshining.vidallplayer LOCAL data/storage/el2/base/haps/entry/cache/NAME` 将三份素材放到模块缓存（不是 app base/cache）。
4. 在本机 127.0.0.1:18779 启动仅提供合成媒体的 HTTP server，并建立 `hdc -t SERIAL rport tcp:18779 tcp:18779`。
5. 将 dual.mp4 的第一视频/音轨 remux 为 MPEG-TS（不转码），在 18780 用 `serve-live.py` 提供无长度持续流，再建立对应 reverse TCP。该路径是受控网络协议验证，不等同于公网、SMB 或 Wi-Fi 稳定性验证。
6. 用 `hdc -t SERIAL shell aa force-stop com.yaoshining.vidallplayer` 停止 demo，再用 `hdc -t SERIAL shell aa start -a EntryAbility -b com.yaoshining.vidallplayer --ps diagnostics79 true` 启动探针。
7. `devecocli log --device SERIAL --keyword Diagnostics79 --from 3m --tail 30` 查看进展；完成后用 `hdc file recv -b` 导出 `data/storage/el2/base/haps/entry/files/diagnostics79.json`，保留完整字段值与采样窗口。
8. 结束后仅停止本次启动的 demo/HTTP 服务、移除本次 reverse TCP 规则和 diagnostics79* 缓存，不重启全局 hdc。

生成无长度流输入：

```sh
ffmpeg -i /tmp/diagnostics79-fixtures/diagnostics79-dual.mp4 \
  -map 0:v -map 0:a:0 -c copy -f mpegts /tmp/diagnostics79-fixtures/live.ts
python3 scripts/test/diagnostics79/serve-live.py /tmp/diagnostics79-fixtures/live.ts
```

探针检查正常输入、1Hz 采样前/中/后各 15 秒、暂停位置稳定、恢复、seek、音轨切换、缓存字段、停止时在途请求、无音/视频轨道、直播无时长/大小、重复重开、表面代际和 release 后拒绝。切源中返回 `DIAGNOSTICS_STALE` 时按契约重试。性能窗口保留全部 CPU/PSS 样本与采样耗时，不据短时低负载结果承诺 4K/DV 性能或长期无泄漏。
