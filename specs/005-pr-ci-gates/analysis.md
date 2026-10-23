# Spec Kit 一致性分析

2026-10-24，只读分析 spec/plan/tasks 与当前实现；未改旧001—004封存。`.specify/extensions.yml` 不存在，无扩展钩子。现有 prerequisites 接受 `--json --require-tasks --include-tasks`，另核对 spec.md 存在；未使用不支持的 --require-spec。

| 要求 | 实现/测试 | 任务 |
| --- | --- | --- |
| FR01 | workflow、ci-context、真实 Git merge/错SHA/错父回归 | T002/T004 |
| FR02 | 原 run.py 47项完整调用；无原规则变化 | T006 |
| FR03 | ci-target 固定输入审计、真实 clean/HAR、九库和编译命令核验 | T003/T005 |
| FR04 | CLI只读选择、API24 metadata+工具hash、实际clang/sysroot、缺失/漂移负例 | T003/T005 |
| FR05 | 同仓self-hosted条件、fork拒绝汇总、无签名/设备 | T002/T004 |
| FR06 | prepare/always finish/assess、context与前后源码、完整文本索引 | T002/T003/T006 |
| FR07 | 本文件、validation、精确候选/外部重放预览 | T007/T008/T009 |

未发现规格/计划/任务遗漏。旧 source-lock 重建不启用、不作为当前核心证据；目标输入仍是原八库。main 指向已核对的951343基线时为当前分支祖先，最终预览需记录祖先/组合树核对。merge_group仅有事件门禁测试，是否配置远端队列不在此宣称。

真实目标构建和精确SHA重放在本地候选冻结后执行；结果写仓库外精确预览，避免为嵌入自身SHA反复更改提交。新远端CI必须等用户批准精确SHA，T009仍未完成。
