# 受控网络夹具

此目录提供仅绑定 loopback 的确定性 HTTP/WebDAV 夹具，用于本地协议测试，不会连接外部服务或读取真实媒体。固定 Basic Authorization 值 `fixture:credential` 仅用于本夹具，不能用于产品、示例或任何真实服务；不得提交真实账号、Cookie、Authorization、私有地址或媒体。

```bash
bash scripts/test/network-fixtures/network-fixtures.test.sh
docker compose -f scripts/test/network-fixtures/docker-compose.yml up --build
```

容器启动后提供以下入口：

- `http://127.0.0.1:18080/media/sample.mp4`：确定性媒体字节和 `Range: bytes=0-3`。
- `/redirect/same`：同源重定向；`/redirect/cross`：跨端口重定向，用于确认认证头被剥离。
- `/timeout`：固定 `504` 超时失败路径；`/chunked`：chunked 响应。
- `/webdav/media/sample.mp4`：需要 fixture Basic Authorization 的 WebDAV 媒体。
- `PROPFIND` 和 `OPTIONS /webdav/`：需要 fixture Basic Authorization，返回 WebDAV `DAV: 1` 能力信息。

该夹具只建立 T004 的受控服务基础，不构成 WebDAV 播放、认证头转发或真机行为已经通过的证据；缺少后续真实实现和设备证据时，相关任务必须保持未完成。
