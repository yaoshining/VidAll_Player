# 独立测试包的可控签名材料

当前专用手动材料已完成CSR/调试证书/profile及单电视范围核验，官方交互签名和完整验签已通过。Round7实际安装身份通过、短测终态事件验收失败、原清理联合门禁未确认；后验设备无残留，原失败保留。材料和密码不入仓库，已有成功不授权再次迁移、签名或安装。

以下是历史采用的手动准备步骤，供重建专用材料时参考，不要求用户再次生成。此前自动材料没有用户可输入的已知密码；不解密IDE密码，不覆盖自动材料或Player/TV材料。

确需重新准备材料并获授权时，用户可完成以下步骤，密码不发到聊天或提交仓库：

1. 在独立测试工程打开 **Build > Generate Key and CSR**，新建单独测试 `.p12`；选择新文件名/目录，自行设置并妥善保存 **Key store password** 与 **Alias**。保留现有自动材料和Player/TV材料。
2. 保存该密钥生成的 `.csr`，在 AppGallery Connect 申请对应的**调试证书** `.cer`。
3. 为 `com.yaoshining.vidalldeviceprobe` 申请**调试 Profile** `.p7b`，选择上一步证书及已核对的电视设备。新密钥不能混用旧证书/profile。
4. 只提供这次 `.p12/.cer/.p7b` 的本机路径和alias；不提供密码。我们先核公开证书/profile、设备范围和有效期，再提交材料迁移、工具与执行的精确预览。
5. 最终执行获批后，用户通过官方工具的交互终端输入密码；签名仅接受已核云端HAP，不重新编译。本次不要求把密码配置到GitHub Secret，长期iMac无人值守取密另行设计和批准。

目前官方“对已有HAP签名”说明使用 `hap-sign-tool.jar sign-app -inFile`，仍需密钥/密钥库密码。已安装Hvigor的 `SignHap` 依赖 `PackageHap`，从工程build目录取包；未证实一个公开的“自动材料免输入密码、对任意云HAP独立签名”入口。不采用替换中间产物或私有hook，也不把IDE重新编译包当成本次云端包。

依据：官方devecocli文档 `开发指南/配置调试签名/手动签名/ide-signing-manual` 与 `FAQ/签名服务/通过DevEco_Studio对HAP_APP包进行签名/faqs-signature-service-17`；在线入口为[华为手动签名指南](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing-manual)。准备材料不等于批准迁移、签名、安装或播放。
