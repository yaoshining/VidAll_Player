# 当前覆盖与迁移映射（894f0feb只读盘点）

| 现有任务 | 现有实际检查 | 去向/最小阶段 | 未完成不能声称 |
|---|---|---|---|
| normal-core.yml host-contracts | 47 checks、上下文/schema/工作流失败契约 | 已在DevEco26 host执行；A阶段保持同等集合并验证 | 合并两个workflow名字不等于复验 |
| normal-core.yml target-har + result，self-hosted | 旧SDK严格锁、default单clean/HAR、AND汇总；当前唯一Studio选择失败 | A阶段退役旧自动目标路线；保留ci-toolchain-lock/ci-target及历史证据；唯一默认云端结果使用deveco26的host+target+consumer+新Hypium AND | 不能修改旧锁冒充新SDK或OR任一个target成功 |
| deveco26-pr82-gates.yml macos-26 | 私有Release精确输入、实际SDK、显式target、公共API负例、consumer同HAR九库/API与清理 | A阶段正式默认CI路线（保留文件路径/精确来源门禁，新增Hypium编译证明） | 不把旧default目标/双ABI宣称已验证 |
| test-player.yml build-test-module，self-hosted | 完整native CMake/CTest、diagnostics-session JS、diagnostics-device JS、default HAR；仅发现本机签名才编ohosTest | A阶段14项CTest迁ubuntu云端，诊断JS保留并用已锁TS路径；Hypium改官方ARM64临时unsigned工程，使用本轮HAR，不依赖本机证书 | 现有signing_ready=true不能推出built=true；缺签名不应免编译 |
| build-libmpv.yml native-contracts、clean-environment | capability/契约/受控发布/补丁/来源/许可证/打包测试，双平台元数据审计 | 云端继续保留；现有检查要求同步TDD，不删断言以迎合迁移 | 元数据/宿主替身不是目标交叉编译 |
| build-libmpv.yml build-libmpv-external-ffmpeg，self-hosted | LAN镜像+旧sources.lock：Samba→FFmpeg→mpv、ELF嵌入符号/体积、许可证/runtime制品 | B阶段明确由producer云端构建/发布输入负责；先锁定当前组合源码补丁及可消费的run/artifact契约 | #7/#8历史云端成功不能自动覆盖#9完整目标或当前004八库 |
| build-libmpv.yml cross-build-prerequisites，self-hosted | 手动任意宿主来源/pkgconfig目录，闭包状态、--skip-compile审计 | B阶段改固定来源/制品契约云端审计或作为有明确继任的历史入口退役；禁止携任意本机路径到iMac | 此任务本身不是完整源码重建，不可伪称替代上行自动构建 |
| deveco26-evaluation.yml macos-26 | 006独立实验与官方签名URL准备 | 旧实验/来源锁保留为历史入口，不作为默认/长期private下载路线 | 006绿灯不覆盖新010 |
| 尚无设备workflow | diagnostics79人工脚本/旧Hypium测试入口 | C阶段已签云端包→手动可信控制器→iMac专用设备执行 | 当前SDK已装/端口可达不等于包签名或用例就绪 |

## 独有native集合

CMake中14项：ohcodec_runtime、session_lifecycle、localhost_proxy_lease、player_session、surface_renderer、event_dispatcher、media_loader、tracks_subtitles、subtitle_rendering、adaptive_streaming、capability_report、media_parameters、render_backend_policy、diagnostics。新47checks只明确复用diagnostics native及两个诊断JS，不足以删除其他12项C++和runtime脚本覆盖。

## 当前Hypium/设备差异

`entry/src/ohosTest/ets/test/List.test.ets`汇入9个suite，16个ohosTest文件；TestAbility直接调用Hypium，没有normal initializePlayerRuntime/onPlayerTerminal。PlayerSession/StreamingSession部分测试直接load/play `example.com` / `files.example` 并断言旧同步固定事件，这些实际播放测试不能直接作为受控真机夹具；URL语法/隐私负例中的example.com仍有效，不需凭空替换。

`DiagnosticsProbe.ets`和旧EntryAbility也未建立normal初始化/terminal策略。已有normal-core-consumer有新公共根初始化，但只证明unsigned构建；不覆盖旧9suite真机执行。旧entry的libentry.so/native桥与HAR新桥应在临时编译工程中明确区分，不能把旧entry.so/旧mpv重复混包说成当前九库。

## 签名/设备来源缺口

旧test-player从runner ~/.ohos/config自动找任意同basename cer/p12/p7b，这是本机约定，不是已批准的云端签名输入。尚无固定云端签名身份/有效期/profile设备授权/Hypium test包匹配的审定契约；目前仅已验证unsigned consumer。C阶段先核签名方案，不复用开发密文或自动复制签名材料。

root只读证据已确认iMac为x86_64、现runner21，沿runner PATH可用CLI1.2.0发现192.168.3.85:5555 MateTVPro；HDC已有精确工具SHA。此信息只供选定设备执行工具，不授权新增标签/安装/构建。producer当前具体映射以root并行审计为准，未证实之处不补成通过。

补充实证：原test-player run40127384289 的签名Hypium构建 step6 被跳过，不能将该run绿色解释为Hypium编译通过。normal-core-consumer实际读取rawfile/test_video.mp4，而fixture与当前consumer.py均未注入此媒体；旧consumer是编译夹具，不能直接发设备。设备package staging必须注入可追溯短合成媒体，绑定生成器/参数/实际媒体SHA、许可与期望路径。

producer根并行审计：#7 FFmpeg闭包39995276876/Phase17双clean39995276834、#8 Phase18依赖mpv39998335430/Phase20target39998335365为历史官方云端目标证据；#9 head68b3422仅宿主矩阵40005479235，不证明Phase30正常库完整新目标重建。最小可退役Player历史生产入口并明确producer独占生产，但须新增硬门禁仅允许现有004精确输入，任何核心更新未有精确producer产物/来源/功能证据即拒绝；保留全部native契约/许可证/来源测试。详细证据在本轮producer-audit/REPORT.md。
