# HarmonyOS 签名证书占位目录

本目录用于存放 HarmonyOS 应用签名证书文件：
- default.cer：HarmonyOS 应用证书
- default.p12：PKCS#12 密钥库文件
- default.p7b：Provisioning profile（描述文件）

本地开发时，从 `~/.ohos/config/` 复制证书文件到本目录。
CI 环境中，证书应由受控 runner 提供，不应提交到代码仓库。
