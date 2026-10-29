# 验证记录与冻结边界

本文件随候选冻结，尚不代表本提交已推送或远端 CI 已运行。候选的完整 SHA、tree、逐文件预览、精确 clean 重放和真实 unsigned HAR 结果由仓库外精确预览绑定；旧66e9/ca3a CI不计入本轮通过。

## TDD

- 先写实际 YAML 工作流检查与 helper 契约；旧工作流的 PR/main/merge_group、实际 target、汇总缺失产生 RED。最初 helper 尚不存在的 RED 明确是入口缺失，不伪称原产品语义缺陷。
- 扩展真实临时 Git、假 clean/build 子进程、编译命令和快照边界：RED 中 tracked dirty、旧 bridge/compile_commands、缺完整宿主证据可复现。旧 .15秒超时夹具启动过短造成空日志，保留原失败；扩大为1.5秒、子进程5秒等待后再验证超时输出。
- 收尾缺少 host 后快照的独立 RED：context 后修改真实 tracked 源码仍被接受。修复后拒绝该变化和同 tree 新空提交。
- 工作流初版测试漏掉删 always/删 assess/continue-on-error 三个负例；保存 RED，再强化实际 YAML 检查，六种变异全部拒绝。
- GREEN：25个Python测试、10项YAML语义检查、6种工作流变异拒绝。夹具 HAR/fake CLI 只验证失败路径，不是目标构建证明。
- 原宿主47项检查全部通过（含工具/编译步骤，不等于47测试用例）；嵌套ETS/native/parent场景保持原定义。

上述原始测试记录位于 [evidence](evidence/host-summary.json)。日志中的本机路径已脱敏，原失败不覆盖；目标构建未执行前不预填成功。

## 接口与产物边界

HEAD/tree/tracked字节必须在事件核验、目标执行前后及最终收尾一致；clean后仍有旧HAR、bridge、compile_commands会失败。HAR成员安全检查复用 normalize-har，重复名称与链接均拒绝；八库匹配既有锁，bridge匹配本次输出且为ARM64。actual compile_commands的clang/sysroot必须属于已核对SDK。

公共index包括context与完整host runner文本，不包含HAR、库、SDK、签名、凭据、媒体和原始设备日志。当前004默认SDK/产品API声明不变。producer来源闭包仍由原封存和独立producer PR验证，本门禁不重新生成核心库。

## 未验收

远端新head/PR merge CI、真实GPU永不返回、低API设备、物理HDR/主观声画及正式发布仍未因此关闭。60分钟长播不是接入前置；历史失败保留。formalArtifactAllowed=false。无设备/长播、无系统设置改变、无候选替换。
