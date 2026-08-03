# G1--G3 门禁审查汇总

- 审查日期：2026-08-03T00:54:17+08:00
- 当前候选：未分配；`deliveryStatus: blocked`
- 建议：No-Go

| 门禁 | 所需材料 | 当前结果 | 缺口 | 建议 |
| --- | --- | --- | --- | --- |
| G1：TV/API/复现 | 具名 ARM64 TV、API、样本、跨设备规则、真机运行记录 | 未关闭；仅有模拟器开发期 6 项 Hypium 回归 | 负责人确认和全部真机记录 | No-Go |
| G2：libmpv 联合审计 | 来源、源码、GPL、NOTICE、构建、SBOM、ABI/ELF、加载边界 | 未关闭；仅有自动化拒绝路径校验 | 同一候选的全部材料和签收 | No-Go |
| G3：画面/线程/输入 | Surface 生命周期、线程、NativeWindow/EGL/GLES、样本闭集和 spike | 未关闭；仅有 XComponent 生命周期边界回归 | 指定真机、样本、spike 和签收 | No-Go |

三个门禁未同时获得书面 Go。已实现的 HAR、原生产物、NAPI bridge、播放器和 fixture 仅供受控开发验证；不得交付、上传 OHPM 或将任意能力标为已支持。
