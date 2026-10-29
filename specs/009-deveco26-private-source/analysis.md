# 一致性审查

| 要求 | 实现与证据 | 边界 |
|---|---|---|
| R1 精确来源 | release-source-lock 独立固定 repo/release/tag/commit/3 assets/manifest；旧 archive-lock SHA 单独绑定 | 不改旧官方长期源状态 |
| R2 传输 | urllib 禁止自动跟随；认证仅 api.github.com；精确 release-assets.githubusercontent.com 新请求无 token/cookie | 临时 Location 仅内存；不扩泛域 |
| R3 输入文件 | 独占目录、顺序部分写入、摘要后原子改名，inode 与外来文件检查 | 外来文件不删，cleanup 失败传递失败 |
| R4 准备与清理 | 原 bootstrap --archive；四个凭据变量不进入子环境；拒绝旧成功文件 | wrapper 只删自己 ZIP；原 SDK cleanup 仍执行 |
| R5 CI | actual SHA/ref 与环境信任门禁保持；finish 绑定来源锁和当前源码，拒 mock | consumer/九库/API 校验和旧 workflow 不变 |
| R6 验证 | 实际函数 TDD；冻结后一次本地原包集成；两份独立审批预览 | 无远端配置/推送/新 CI/播放器构建 |

根审查已通过规格、下载主路径、helper、旧输入逐字节比较。根已独立运行 source/gates/workflow 测试；新增模拟证明拒绝也已复审。009 不改写 006–008 的历史验证范围。TV 既有外部 HEAD 漂移仍保留原报告，本轮只核没有新增写入，不能把旧基线改成全绿。
