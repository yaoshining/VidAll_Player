# 实际 HAP 签名者辅助验证

辅助程序复用精确锁定的官方 `hap-sign-tool.jar`，不自行实现密码学/ASN.1，也不从 `outCertChain` 的排列或成员关系猜签名者。

官方 `VerifyHap.verifyHap(path)` 返回真实 `VerifyResult`。程序要求验签成功、恰一个 `SignerInformation`，使用其 `getSID()` 从 `getCertificateHolderStore()` 唯一选出 `X509CertificateHolder`，用实际系统时间核其 NotBefore/NotAfter，再计算证书 DER SHA256，与**外部批准**的应用证书摘要精确匹配。官方 `verify-app`、`verify-profile` 与 profile 的 bundle/证书/设备/有效期检查仍由执行器完成，不能由本辅助程序取代。证书有效期与 profile 有效期分别验证，不假定官方返回成功就已覆盖二者。

普通官方证书链输出是每个 SubjectDN 文本行接 PEM；列表不承诺叶子顺序，可能携带非 signer 证书。helper 拒绝“真实 signer B、额外附带批准 A”场景。当前 jar 固定为 SHA256 `a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d`，运行时还核对实际加载 `VerifyHap` 所在 jar。

## 构建与执行边界

只在本地开发机或云端编译 class，**iMac 不调用 build.py/javac**。iMac 使用外部受信锁定的 class SHA、同 jar SHA 与已锁 Java 执行。build 清单不是自批准，执行器必须从独立批准配置核对它，不能从受测 PR/artifact 取得后自动信任。

```sh
python3 -B scripts/test/device-execution/signer-helper/build.py \
  --jar /absolute/locked/hap-sign-tool.jar \
  --javac /absolute/jdk/bin/javac --out /absolute/new/helper-dir
```

等价核心编译命令为 `javac --release 17 -cp <locked-jar> -d <new-dir> ActualSigner.java`。输出仅 `ActualSigner.class` 和 `helper-build.json`；清单绑定源码、class、官方 jar、javac 摘要/版本及 release 17。

```sh
/absolute/locked/java -cp /absolute/helper-dir:/absolute/locked/hap-sign-tool.jar \
  ActualSigner /absolute/private/signed.hap <approved-signed-HAP-SHA256> <approved-app-cert-DER-SHA256>
```

成功只输出一行 JSON：`schemaVersion=1`、`signedHAP_SHA256`、`actualSignerDER_SHA256`、`signerCount=1`、`verified=true`。失败返回非零、`verified=false`，不输出证书、路径或第三方日志。helper 对受限大小普通文件读取一次，在 signed HAP 所属的本次私有会话目录中建立私有快照，验签前后核摘要，finally 删除快照；宿主强停时由执行器清理整个本次会话目录，不把随机残留散落在全局临时目录。执行器仍需对实际安装路径再次核对摘要，helper 不安装任何包。

## 测试与限制

```sh
python3 -B scripts/test/device-execution/signer-helper/test.py \
  --jar /absolute/locked/hap-sign-tool.jar --javac /absolute/jdk/bin/javac \
  --java /absolute/java --out /absolute/new/evidence-dir
```

测试证书/密钥由官方 jar 携带的 Bouncy Castle API 在内存临时生成，不落盘、不上传。12 个真实 SID 选择函数测试包括正常 signer、打乱附加证书、批准证书仅为非 signer 成员、错误批准证书、多个/缺失 signer、SID 无匹配/重复匹配、官方失败、非法摘要、过期及尚未生效证书。测试再运行故意把 Store 成员误认 signer 的变异体，必须精确拒绝；同时覆盖无效实际 HAP、错 HAP 摘要、符号链接、构建输入失败和双目录 class 一致性。

这些测试不包含受信任的真实 HAP 成功签名路径，更不是真机结果。合成 CMS fixture 中 `verified=true` 仅是 SID 函数的单元测试前提，`realHapVerified=false`、`deviceVerified=false`、`formalArtifactAllowed=false` 必须保留。实际官方成功 HAP 验签和设备执行由后续授权闭环完成。
