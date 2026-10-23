# 独立 HAR 消费工程

只从 `@vidall/player` 根入口消费。构建前将本轮规范化 HAR 复制到 entry/libs/vidall_player.har，将仓库 entry/src/main/resources/rawfile/test_video.mp4 复制到同名 rawfile。使用既有独立测试 bundle，签名需在本机私有配置注入；仓库配置不含签名。

通过 devecocli build/run 构建安装。默认短场景包含初始化、两次首帧、暂停位置稳定、恢复推进、已知 20 秒关键帧 seek 与继续推进、关闭重开、保屏回读 false。

可选 SMB：通过 HDC 官方 `file send -b` 将包含 uri/username/password 的私有 JSON 传到应用 filesDir/phase32-consumer/credentials.json。源码/HAP 不包含凭据；读取后立即删除，公开 MediaSource 的 authorization Basic 转到 SDK 原有鉴权链，不把 userinfo 放 URL。未提供文件时仅跳过 SMB，不能声称 SMB 已通过。

正常 HAR 禁止终局注入。另行复制测试 checkout 并应用 terminal-fixture.cpp 和 CMake 链接接缝，仅验证宿主接管；它不等于真实 GPU 故障。8 个核心库必须逐字节保持正常组合。
