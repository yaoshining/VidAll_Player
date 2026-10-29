# 固定 unsigned 的官方页面元数据派生 helper

`ExpectedPages` 只生成 `.pages.info` 的预期字节，不签名、不读取私钥、不访问设备。它把批准 unsigned 的全部字节冻结到本地 0700 临时目录中的 0600 快照，校验实际加载的官方 JAR SHA，然后调用同锁 JAR 的 `Zip.alignment(4)` 和 `PageInfoGenerator.generateBitMap()`。`signCode=1` 表示对应的签名配置要求；helper 本身不运行签名操作。

接口：

```text
java -cp CLASSES:LOCKED_JAR ExpectedPages UNSIGNED_HAP EXPECTED_UNSIGNED_SHA256 NEW_OUTPUT_FILE
```

成功输出一行 JSON：`schemaVersion=1`、`derived=true`、`unsignedHAP_SHA256`、`alignment=4`、`signCode=1`、`pagesSHA256`、`pagesBytes`。输出文件以 0600 创建，拒绝覆盖既有文件/符号链接。失败非零退出，仅输出 `{"schemaVersion":1,"derived":false}`，不输出归档成员名或原始内容。临时快照在正常返回或异常时清理；强制终止后的会话目录清理由外层 executor 负责。

拒绝错误输入摘要、输入符号链接、运行时 JAR 身份不同、unsigned 已含 `.pages.info`、重复成员、目录/文件同名，以及 `.`/`..`、绝对路径、反斜杠、空路径段、冒号、控制字符等歧义名称。输入文件上限 128 MiB、成员数 4096、单名称 4096 字符、输出 bitmap 上限 1 MiB；未知或不适用输入失败关闭。

## 编译与测试

本地或云端执行 `build.py --jar LOCKED_JAR --javac JAVAC --out NEW_CLASSES_DIR`，以 `--release 17` 编译并生成源码、class、JAR 和编译器 SHA 清单。iMac 只执行审查批准的 class，不现场编译，不执行 PR 提供的构建脚本。

执行 `test.py --jar LOCKED_JAR --javac JAVAC --java JAVA17 --artifact FROZEN_ARTIFACT_ZIP --out NEW_EVIDENCE_DIR`。测试只接受本轮冻结 unsigned（SHA `bda840a7843dcad69241d06d907c8dce40479bdb969c9227b53c5f3bf21fa5b1`），核验预期 bitmap 为 6680 字节、SHA `4364749b8c09d61a99ffa507ca0acd5f794c2d2bfc388243c54a15d4b9f09738`。负例基于同一真实 HAP 加入非法成员；删除名称门禁的变异必须被检出。输入与临时输出在测试结束后清理。

本 helper 的通过不构成官方签名验证、实际签后成员一致或真机验收；这些仍由 executor 的独立验证链完成。冻结 artifact、HAP、生成 class、临时输出均不放入源码目录。
