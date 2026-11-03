# 任务：旧基线 Vulkan 尺寸通知与 CI HAR 交付

依据：[spec.md](spec.md)、[plan.md](plan.md)。顺序执行；本轮不安排并行产品实现。

## 阶段 1：规格、计划与追踪

- [x] T001 核对旧基线、#83 范围与 #84 顺序，在 `spec.md` 记录 FR-001～FR-008、SC-001～SC-004 及补建时序。
- [x] T002 在 `plan.md`、`research.md`、`data-model.md`、`contracts/delivery.md`、`quickstart.md` 完成设计及宪章检查。
- [x] T003 在 `checklists/requirements.md` 完成需求质量检查，并在 `analysis.md` 记录规格/计划/任务一致性。

## 阶段 2：US1 最小修复（已做工作如实追认）

- [x] T004 [US1] 先在 `native/tests/vulkan-size/resize.test.py` 复现旧实现通知缺失，覆盖正常、边界、失败和并发（FR-001/002，SC-001）。
- [x] T005 [US1] 在 `packages/vidall-player/src/main/cpp/napi_init.cpp` 仅修改 Vulkan Resize，确认其余源码和 ArkTS 不变（FR-001/002/003/006）。
- [x] T006 [US1] 固定 `native/cmake/legacy-cxx-runtime.cmake` 和原 runtime 输入，执行 `native/tests/legacy-runtime.test.py`；完成本地 HAR/隔离消费构建及 ABI 预验证（FR-003，SC-003）。

## 阶段 3：US2 CI 最终交付

- [x] T007 [US2] 先增加 `scripts/test/legacy83-ci/audit.test.py`、`workflow.test.cjs` 的正常/漂移/缺失/非 CI 身份/额外库失败断言，再实现 `audit.py` 和 `.github/workflows/test-player.yml`（FR-004/005，SC-002/003）。
- [x] T008 [US2] 将最终 CI 交付与 FFmpeg 职责写入 `AGENTS.md`，固定 `scripts/test/legacy83-ci/package-lock.json`（FR-004/005）。
- [x] T009 [US2] 推送本修复分支，取得同一提交的 iMac CI 临时测试、完整 HAR 构建与审计成功结果（SC-002/003）。
- [x] T010 [US2] 下载 CI 附件复核 run/commit/HAR/库哈希，保存 `evidence.md`，通知 TV 会话用 CI 包临时预验（后续已纠正为等待云端最终包）（FR-004/007）。

## 阶段 3 补正：云端 Mac 来源（FR-008）

- [x] T013 [US2] 先增加运行器负例，修复 `scripts/test/legacy83-ci/audit.py`、`workflow.test.cjs` 与 `.github/workflows/test-player.yml`，默认限定 `macos-26`；复用主线 SDK 准备脚本，更新 AGENTS 和契约。
- 已取消 T014 [US2]（用户 2026-11-04 改为普通分支 iMac CI，不计为完成）： 在 `deveco26-build` 既有保护下完成当前精确提交的云端完整 HAR 构建、清理和产物校验。
- 已取消 T015 [US2]（用户取消云端替代交付，不计为完成）： 下载云端附件，核验 GitHub runner 与产物哈希，记录 `cloud-evidence.md` 并通知 TV 会话替代 iMac 临时包。

- [x] T016 [US2] 按用户最新决定恢复普通分支 iMac CI；先更新 runner/工作流回归测试并验证失败，再恢复配置使其通过；同步规格、计划、交付契约与来源记录，通知 TV 继续使用现有 CI 哈希包。

## 阶段 4：消费端验收与后续

- [ ] T011 [US1] 由 TV 会话依次验证模拟器、云平板/TV，绑定本轮 CI 哈希并回传尺寸变化、退出/重进结果至 `evidence.md`（SC-004）。
- [ ] T012 在 `tasks.md`/`evidence.md` 记录 #83 验收结论；仅在 T011 完成反馈后继续 #84（FR-006/007）。

依赖：T001→T002→T003；已完成的 T004～T006 不伪称发生在规格之前。后续 T007/T008 的预验证完成后必须经 T003 一致性检查再推送。T009→T010→T016→T011→T012；T013 是历史云端配置工作，T014/T015 已取消；CI 成功只能完成 T009，不能代勾 T011/T012。
