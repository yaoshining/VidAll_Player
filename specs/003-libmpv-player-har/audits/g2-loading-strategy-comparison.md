# G2 加载策略比较

> 更新说明（2026-08-05）：曾实测到当前 HAR `package/libs/arm64-v8a/` 仅含 `libvidall_player_native.so`（8.6KB probe）+ `libc++_shared.so` 且未打包 libmpv.so。**根因是 8 月 2 日过时的 `default@PackageHar` 缓存**。执行 `devecocli build clean` 全量重建后，HAR 已正确纳入 `libmpv.so`(53MB) + `libvidall_player_native.so`(176KB)，native `NEEDED` 含 `libmpv.so`、`UND mpv_*` 14 个 → 真实播放内核已就位。

| 候选策略 | HAR 边界 | 加载顺序与失败语义 | ABI/ELF 范围 | GPL 与审计风险 | 当前结论 |
| --- | --- | --- | --- | --- | --- |
| `har-bundled` | HAR 随包携带 libmpv.so | 必须记录解包/定位/加载顺序及每步失败；**重建后 HAR 已真实携带 libmpv.so**，下一步需补真机加载记录 | HAR 内 libmpv.so 及全部动态依赖（已完成 ELF 审计，passed） | 必须证明随包二进制、源码、NOTICE、SBOM 一一对应 | **候选策略（待真机验证）** |
| `private-native-layer` | HAR 仅经受控私有边界访问 libmpv | 必须记录提供者、边界调用、加载位置及失败 | 私有层、libmpv 和全部动态依赖 | 必须证明交付边界不遗漏对应源码或许可证责任 | 备选，需设计 |
| `reject` | 不交付候选 | 不加载原生产物 | 无准入产物 | 材料或审计链不完整时唯一安全结论 | 作为兜底保留 |

负责人必须基于同一候选的完整材料、真实加载记录、ABI/ELF 结果和 GPL 审计选择策略。不得以 probe、单库加载或构建成功替代本审计。

**当前状态**：重建 HAR 已含真实 libmpv 播放内核且加载链路完整，`har-bundled` 成为候选策略。已验证 libmpv.so SHA-256 跨 HAR/HAP/独立构建一致（可复现），NEEDED denylist 通过。**待补**：真机加载/首帧证据（G1/G3）、受控源码树、NOTICE 法务复核与负责人书面选型；补齐前门禁仍 No-Go。
