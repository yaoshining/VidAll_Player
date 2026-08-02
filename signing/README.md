# HarmonyOS 多环境签名材料

本目录只保存本机或受控 runner 在构建期间注入的 HarmonyOS 签名材料；所有证书、密钥库、描述文件和密码均不得提交到仓库。

## 环境与产物

| 构建产品 | 签名配置 | 本地材料目录 | 用途 |
| --- | --- | --- | --- |
| `default` | `development` | `signing/development/` | 开发调试 |
| `ci` | `ci` | `signing/ci/` | CI 测试 HAP |

每个目录均使用固定文件名：`app.cer`、`app.p12`、`app.p7b`，并包含 DevEco Studio 创建的 `material/` 辅助材料。当前 CI 使用从开发环境复制出的独立材料副本，密码采用同一套 DevEco Studio 生成的密文，因此可直接构建测试 HAP。

`signing/` 下的材料均被 Git 忽略，不得提交。后续如需更换 CI 证书，只替换 `signing/ci/` 中的内容，并同步更新 `build-profile.json5` 的 `ci` 密文密码；不要修改开发环境材料。
