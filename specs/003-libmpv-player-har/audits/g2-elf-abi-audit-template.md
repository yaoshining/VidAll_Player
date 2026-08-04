# G2 ELF/ABI 联合审计模板

- `candidateId`：待填写
- `sourceCommit`：待填写
- 目标 ABI：待负责人确认
- 产物路径与 SHA-256：待填写
- 审计工具和版本：待填写

| 类别 | 记录 | 结论 |
| --- | --- | --- |
| ELF 头与 ABI | `Class`、`Machine`、`OS/ABI` | 待审计 |
| `NEEDED` | 所有动态依赖及版本 | 待审计 |
| 导出符号 | 公共/未预期符号清单 | 待审计 |
| allowlist | 经批准的动态依赖 | 待负责人确认 |
| denylist | 禁止依赖，包括 `AVPlayer` 相关库或回退 | 待负责人确认 |
| 加载边界 | HAR 或私有层的位置、顺序、失败语义 | 待审计 |
| 材料关联 | 源码、许可证、NOTICE、SBOM、manifest | 待审计 |
| 可复现性 | 两次构建摘要和差异 | 待审计 |

任何 ABI、依赖、符号、加载边界或材料关联异常均为 No-Go。
