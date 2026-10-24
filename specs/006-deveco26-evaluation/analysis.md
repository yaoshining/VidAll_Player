# 一致性分析与必要范围调整

旧规格005继续描述旧API24门禁；新规格006只负责独立26评估，不替代005的通过条件或封存证据。独立分支的活动规格指针切换006，原checkout未改。

## 构建差异与最小处理

1. 新SDK默认将自己的libc++_shared.so（965803c3…）打入HAR；七个其他核心库仍匹配。固定输入9b671470…未变，门禁正确拒绝。已先向用户报告，并由审查agent批准新增显式deveco26目标及默认OFF的CMake选项。该目标使用OHOS_STL=none，并按固定SHA导入原runtime用于链接与打包。没有HAR后处理或SDK覆盖。
2. 通用libc++头使用__1，OHOS目标头使用__n1。保留错误链接记录；按该SDK编译器实际目标搜索目录选择libcxx-ohos头，锁定__config与__config_site，不手改ABI宏。
3. 官方Hvigor clean对各product/target执行ninja clean，仅删除CMakeCache，保留compile_commands等metadata。CLI1.3.4 clean不转发module参数。补充清理仅限当前隔离checkout的未跟踪 .cxx/default/deveco26，逐组件拒绝符号链接/路径逃逸，拒绝tracked文件；default目标不动，原严格旧输出检查保留。
4. CLI wrapper/common包自身不构成完整运行依赖；新增精确npm锁及common显式必需依赖，防止optional失败后静默仅安装wrapper。Node路径仅作用于构建子进程。

## 保护边界

根build-profile只新增vidall_player的deveco26 target映射；所有products、targetSdkVersion、compatibleSdkVersion、signingConfigs保持原值。模块build-profile只新增target，旧default不变。Hvigor modelVersion、旧SDK锁、旧workflow、固定八库及来源清单原字节保持。新增CMake逻辑默认OFF；不声称旧default在新SDK下通过（其默认runtime打包差异已保留为失败）。

## 宪章与验收

无新HarmonyOS业务API、界面、权限或媒体行为变更；运行时和设备兼容不能由静态构建推出。产品target22/compatible15保持不代表API15已真机验收。formalArtifactAllowed=false。

5. 首次精确重放构建通过，但CLI留下daemon导致卸载失败。本地收尾误把手工steps_ok=True传给publish，形成无效通过汇总；已封存为invalid并纠正失败，不能作为验收。修复从clean前即设置独立HVIGOR_USER_HOME（不修改HOME），收尾以同一目录和锁定Node调用官方当前项目--stop-daemon再卸载。最终重放统一采集每步真实exit生成CI_STEPS，禁止手工填通过。

6. 官方stop发出终止请求后会先返回，daemon仍可能短暂占用DMG。保留第二次完整重放的cleanup失败；新增90秒总期限，仅等待本轮隔离registry且cwd匹配的已停止PID退出。只对明确资源忙且退出16的detach最多重试5次，不force、不额外kill；每次命令日志/退出码独立留存，退出0后仍核挂载已消失。进程查询权限失败不能视作退出。

## 官方首跑与门禁状态复核（2026-10-25）

真实官方macos-26-arm64运行40110834301已完成精确610dd1f的准备/构建/卸载；ZIP digest及33项索引由两次独立下载核验。此前本地错误/EOF记录不删除，CI本身只执行这一轮，没有用重跑掩盖失败。见[持久证据](evidence/ci-40110834301/README.md)。

新事实：云端HAR/bridge与本地摘要不同，原因未单独归因，不宣称跨主机可重复；固定八库/API仍一致。首跑临时Secret经单独授权创建，结束已删除；不能从这个例外推出永久Secret或SDK镜像上传授权。

#82当前head/merge不是610dd1f，旧default目标也不是deveco26目标；独立push绿色不证明旧目标或#82组合通过。当前main required-status接口404、规则集disabled，与workflow里“必需”名称不同。以上差异已先向用户报告；[方案](integration-plan.md)明确需要未来实际merge、consumer和独立规则授权，不修改本轮代码或远端设置。
