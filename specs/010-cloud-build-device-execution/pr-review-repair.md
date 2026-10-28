# Round20：合并前限定返修

范围仅 #82 的 Monitor enable 失败退出、PlayerSession 同步终局事件顺序、旧 HAR 门禁对齐当前异步 API 与 ARM64 固定八库+NAPI 合同。producer #7 另仓修复输入集合。

先运行真实 RED，再最小实现 GREEN；保留正常终局独立 deadline=86、重复终局只通知一次、缺库/错库/额外架构/异常归档拒绝。旧打包入口加入匹配云端宿主检查。产品修改后用现有 DevEco26 做隔离 clean HAR→unsigned consumer，不重编八库。

- [x] 真实 RED 与最小修复
- [x] 匹配回归/负例和独立审查
- [x] 隔离目标构建与精确提交预览

未推送、未运行新远端 CI、未签名或真机执行。TV、候选、八库及系统不改，formalArtifactAllowed=false。

本地修复和匹配验证已完成，证据见 evidence/pr-review-repair/summary.json。精确提交预览在仓外生成，推送须另批；远端 CI、合并与真机不在本轮完成声明内。
