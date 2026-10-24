# 离线使用与下一阶段

在受审 checkout 运行 `python3 -B scripts/test/deveco26-assets/prepare.test.py`。真实生产 CLI 的尺寸和旧来源锁固定，没有任意 URL、网络或上传参数。

```sh
python3 -B scripts/test/deveco26-assets/prepare.py prepare --source "$ARCHIVE_PATH" --out "$NEW_ASSET_DIRECTORY"
python3 -B scripts/test/deveco26-assets/prepare.py verify --out "$NEW_ASSET_DIRECTORY"
```

输入与输出使用不存在 symlink 的真实路径；输出目录必须尚未存在，父目录必须存在。prepare 失败仅清理本轮新建目录，不覆盖既有内容。verify 流式拼接核 SHA，不输出新 ZIP。生产资产 2 片加 947 字节清单；它们存放在源码仓库外，禁止提交 Git。

私有元数据候选只含 README.md、SOURCE.json 和同一清单，无工作流/SDK/二进制。上传者写权限与消费者单仓 Contents read token 分离。建议仓库 `yaoshining/vidall-toolchain-cache` 尚未创建；只读 API 404 仅代表本次连接未找到或无权访问，不保证名字可用。

下一次精确审批才可覆盖新建 private 仓库、仅元数据 commit/tag、启用未来 Release immutability、draft/上传/核验/publish。许可及内部 CI 使用范围须明确，当前不自判允许或禁止。真实 repo/Release/asset IDs 产生后，未来下载器来源锁、Player 提交/推送与 Secret/环境/精确事件变量单独预览审批，不能沿用旧 merge SHA。
