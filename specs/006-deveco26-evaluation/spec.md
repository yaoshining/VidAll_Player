# 006：DevEco26 独立构建评估

## 范围

在99b2固定八库与产品target22/compatible15/modelVersion6.0.2不变的前提下，用Studio26.0.0.851/API26构建unsigned HAR。旧API24锁、旧workflow与候选保持原字节。结果仅为实验，formalArtifactAllowed=false。

## 验收

- E01：clean前验证明确Studio/Node/CLI和新SDK身份；实际clean/build必须同一路径；拒绝混合SDK或架构。
- E02：完整GET允许200；仅Range要求206且Content-Range准确。完整归档大小/hash必须匹配，缺失hash、截断、错误状态或来源拒绝。日志不输出query或HTTP异常repr。
- E03：固定八库、产品API及旧default配置、源码HEAD/tree/tracked快照不漂移；真实编译器/sysroot与新锁一致；旧锁保持。
- E04：新bridge包内身份正确，检查其动态依赖和未定义符号与固定libc++集合；HAR target/min字段保持，compileSdk记录新值；静态结果不能冒充低API/真机验证。
- E05：下载+解包峰值预检；只读挂载DMG，不安装、裁剪SDK、删系统组件；无空间/OOM/超时失败留证；缓存也完整核hash。
- E06：官方固定macos-26评估，与旧门禁分离；一切失败或缺证保持红色；新SHA需批准后才推送/运行。

## 未覆盖

真机、签名发布、物理HDR/低API设备及旧候选替换不在本轮。短期签名URL不能代表未来无人值守来源；不修改Secrets或上传SDK。

## 已审查的必要范围增量

新增deveco26 target及模块映射、默认OFF的固定runtime构建开关；只在显式目标中绑定原libc++，产品API/signing/model与八库字节不变。原因与先报告/审查记录见analysis.md。
