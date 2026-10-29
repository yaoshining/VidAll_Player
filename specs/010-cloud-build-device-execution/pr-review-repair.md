# Round20：合并前限定返修

范围仅 #82 的 Monitor enable 失败退出、PlayerSession 同步终局事件顺序、旧 HAR 门禁对齐当前异步 API 与 ARM64 固定八库+NAPI 合同。producer #7 另仓修复输入集合。

先运行真实 RED，再最小实现 GREEN；保留正常终局独立 deadline=86、重复终局只通知一次、缺库/错库/额外架构/异常归档拒绝。旧打包入口加入匹配云端宿主检查。产品修改后用现有 DevEco26 做隔离 clean HAR→unsigned consumer，不重编八库。

- [x] 真实 RED 与最小修复
- [x] 匹配回归/负例和独立审查
- [x] 隔离目标构建与精确提交预览

未推送、未运行新远端 CI、未签名或真机执行。TV、候选、八库及系统不改，formalArtifactAllowed=false。

本地修复和匹配验证已完成，证据见 evidence/pr-review-repair/summary.json。精确提交预览在仓外生成，推送须另批；远端 CI、合并与真机不在本轮完成声明内。

## 自然 CI 的宿主依赖返修

已批准的 54fa42b 推送后，run40671557712 的 Ubuntu runtime4项通过；打包静态入口因缺少 rg 失败，后续47项跳过，原失败完整保留。先增加依赖缺失断言（真实 RED），再在同一工作流补齐 Ubuntu apt ripgrep 与 macOS 缺失时 brew ripgrep，均记录版本；原工具链锁、产品与检查保持。26项工作流变异通过，实际 target bash 条件在隔离命令替身下覆盖已存在、缺失安装、安装失败三分支。

证据见 [依赖返修摘要](evidence/ci-ripgrep/summary.json)。这是宿主依赖准备修复，未重跑云端/目标构建/设备；新精确提交须批准后才推送，新 merge 的目标授权仍另批。
