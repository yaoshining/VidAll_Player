# 受控网络夹具

此目录只提供本地 HTTP、重定向、Range 和超时的无凭据测试入口。任何测试账号、Cookie、Authorization、私有地址或媒体均不得提交。

```bash
docker compose -f scripts/test/network-fixtures/docker-compose.yml up --wait
```

- `http://127.0.0.1:18080/media/sample.mp4`：静态媒体和 Range。
- `/redirect/same`：同源重定向。
- `/redirect/cross`：跨端口重定向，用于确认认证头被剥离。
- `/timeout`：超时失败路径。

WebDAV、chunked 与认证场景须使用运行时注入的受控服务；未配置夹具时，测试必须明确跳过或失败，不得伪造通过。
