# 云端构建与设备职责边界

默认构建入口是 `.github/workflows/deveco26-pr82-gates.yml`：官方 Ubuntu 完整47项正常核心检查（含来源/许可证/资源/头文件变异）、原14项CTest与2项诊断JS、固定producer交付门禁；官方macOS ARM64执行严格DevEco26锁、HAR、实际HAR消费者及九套Hypium无签名编译。目标任务继续要求精确事件SHA与受保护环境，未授权/缺证不能汇总为成功。

`hypium.py`仅在临时工程复制原测试及其相对导入demo源码，消费当次HAR，验证真实entry_test字节码、九库、API和依赖解析。没有签名、安装或运行测试。SDK要求ohosTest不映射到product；模块自身保留ohosTest目标。旧9套测试的运行契约、初始化适配及网络模拟仍待验，编译成功不等于真机通过。

`producer-input.py`固定当前004正常核心交付；它和47项完整输入审计共同构成门禁，不能单独代替许可证/头文件/资源核验。任何八库/清单变化都须另行提出producer精确源码、补丁、工具链、完整目标构建及来源证据，不能只更新本地lock放行。producer #7/#8既有官方云端源构建可追溯；最新normal组合完整云端目标重建仍待验，不由#9宿主绿灯替代。

历史Player源码生产workflow完整原文保存在Spec010/history，旧配方/SDK锁和所有构建脚本仍保留；活动调度退役其两条self-hosted生产job，保留原来源、SBOM、许可证、打包及精确cargo版本契约。旧normal-core workflow仅手动运行云端宿主检查，不再派发旧SDK目标或产生旧组合结果。

设备前置控制器见 `../device-execution/README.md`。已实现固定签名/官方验签/HDC适配器及独立bundle合成媒体包，禁止复用旧NAS配置。冻结云端制品已构建并核验；Round7签名/安装身份通过、短测及原清理门禁未通过，最新持久诊断修复仅本地验证。宿主测试、云端构建和真机结论分别记录，详见执行器汇总。iMac标签和服务未改；main切换云端且旧任务结束后才可按独立审批移除deveco构建标签，保留harmonyos-test。
