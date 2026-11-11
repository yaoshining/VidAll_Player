# API 19 兼容基础探针

将本目录 Index.ets 覆盖到独立消费工程的测试页面，消费同一完整 HAR。该探针显式使用 preserve-host + compatible，验证坏片报错/释放、正常首帧、手动暂停恢复、seek、关闭重开、身份回执与软件路径诊断。它没有注入全局故障，不是 TV 正式文件入口，也不能凭状态日志证明可听音频。

需向测试工程 rawfile 提供 30 秒、每秒关键帧的合成素材：

```sh
ffmpeg -f lavfi -i 'testsrc2=size=1280x720:rate=30' \
  -f lavfi -i 'sine=frequency=440:sample_rate=48000' -t 30 \
  -c:v libx264 -preset ultrafast -crf 28 -pix_fmt yuv420p \
  -g 30 -keyint_min 30 -sc_threshold 0 -c:a aac -b:a 128k \
  -movflags +faststart test_video.mp4
```

坏片由测试在沙盒中生成。seekPercent 沿用现有关键帧跳转语义；不可用任意长 GOP 文件冒充这里定义的素材。保留日志 PID、HAR/HAP/素材与九库哈希，单独记录每轮失败及后续修复。
