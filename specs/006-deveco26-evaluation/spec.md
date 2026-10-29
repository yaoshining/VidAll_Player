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

真机、签名发布、物理HDR/低API设备及旧候选替换不在本轮。短期签名URL不能代表未来无人值守来源；不上传SDK或自动配置长期Secret。本轮首跑经用户单独批准创建临时下载Secret，验证后已删除并回读确认，见下方结果记录。

## 已审查的必要范围增量

新增deveco26 target及模块映射、默认OFF的固定runtime构建开关；只在显式目标中绑定原libc++，产品API/signing/model与八库字节不变。原因与先报告/审查记录见analysis.md。

## 本次验证完成与后续范围

精确提交 `610dd1f6e83fa844a7096de20ce591b72e48e9da` 的官方ARM64独立push运行40110834301成功；实际下载、目标构建、公开artifact回读和临时资源清理已完成。云端41项契约、21项准备/清理、6项真实CMake/目标Clang、13项结构变异及完整目标流程有[持久证据](evidence/ci-40110834301/README.md)；本地历史actionlint、47项宿主回归及RED另在validation分列，不冒称该云端run执行。此结果不是PR #82 merge或consumer/真机验收。

2026-10-25获准的后续工作仅为本轮文档收尾及[接入/来源方案](integration-plan.md)。不修改workflow、脚本、产品配置、旧锁、旧封存或远端设置；未来新profile组合接线、consumer构建、来源配置、GitHub规则启用须分阶段批准。原门禁名含“必需”，但当前GitHub ruleset为disabled，不能混称已强制。
