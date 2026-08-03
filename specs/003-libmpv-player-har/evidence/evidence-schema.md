# 证据通用字段

每份 G1--G3 证据必须使用相同候选关联字段，并对日志、媒体地址、设备序列号和人员身份执行脱敏。

| 字段 | 要求 |
| --- | --- |
| `candidateId` | 必填；未准入候选使用可追踪的草案标识。 |
| `sourceCommit` | 必填；记录精确 Git 提交。 |
| `recordedAt` | 必填；使用含时区的 ISO 8601 时间。 |
| `executor` | 必填；使用脱敏角色或标识。 |
| `environment` | 必填；工具链、设备 ABI、系统/API 和相关配置摘要。 |
| `deviceRef` | G1/G3 必填；使用匿名设备引用和型号摘要。 |
| `sampleRef` | G1/G3 必填；使用批准媒体样本 ID 与不可逆摘要，不记录完整地址。 |
| `evidenceRefs` | 必填；日志、截图、录像、审计或命令输出的仓库内引用。 |
| `capabilityStatus` | 必填；仅限 `已通过真机样本`、`已构建待验证`、`不支持或暂缓`。 |
| `limitations` | 必填；列明未覆盖能力、失败或环境限制。 |
| `approvalRef` | Go 或支持声明必填；当前必须为空或标为待负责人确认。 |

当前所有记录的 `capabilityStatus` 只能为 `已构建待验证` 或 `不支持或暂缓`，`deliveryStatus` 只能为 `draft` 或 `blocked`。
