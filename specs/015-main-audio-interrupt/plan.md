# 实施计划与宪章检查

使用主线 Phase30 A 的封存 mpv 源树和正常构建配置，在独立临时目录重建参考核心，核对主线输入后仅应用 #90 的 mpv 补丁。保留已有 FFmpeg、运行库、公共头和终局 ABI。新的目标库、来源绑定、编译证据和 CI 输入锁必须一致。

旧系统用 API 10 的同一组回调注册写入与中断，版本查询自 API 10 可用；新系统继续走已验证的媒体会话。音频线程投递 AO 事件，播放线程负责文件局部 pause，文件结束时销毁旧 AO。无新增权限和 UI。宿主回归、主线输入变异检查、分支 iMac 的 HAR/独立消费者及 API 19/20 模拟器分别记录；PR 验证使用主线的合并预览。

## 可复查的核心重建

1. 准备 Phase30 A 封存输入，核对 `package.json` 的 SHA-256 为 `ba6747a77f6d4a18d2cd004f0301b2cb6f1aa940be1fa2bad0b1bd38bcd78fc4`。本次按清单逐文件恢复了全部 2,350 个输入，FFmpeg 使用主线现成的六库。
2. 使用封存的 `build-runtime/fresh_build.py`（SHA 见主线 `provenance/mpv-script-identity.json`），指定 input-root、全新 run-root、SDK、Meson、Ninja、pkg-config，传入 `--stable-prefix /usr/local --handoff-trace`。该入口编译 libplacebo 和 mpv，链接已存在的共享 FFmpeg。参考结果与原主线 `1a469850…` 逐字节一致。
3. 运行 `python3 native/scripts/prepare-normal-mpv-input.py <原输入目录> <新临时目录>`，再将第 2 步的 input-root 改为该副本，使用新的 run-root。最终核心、编译及链接记录进入 `release/inputs/004-normal-core`；来源锁保留原输入身份并新增补丁与派生输入哈希。本地工具链与历史封存版本有差异，实际工具摘要已随构建记录更新。
4. 运行 `python3 scripts/audit/normal-core-verify.py` 和 `python3 native/tests/normal-core-input.test.py`。有封存材料时设置 `VIDALL_MPV_BUILD_ROOT` 为当前修复构建的 run-root，再用 `--verify-external` 校验外部来源和静态库。

## 自动审查补充

注册旧系统回调时分配永不复用的整数标识，AO 仅在持有注册表读锁时可访问。注销取得写锁等候已进入的回调，在释放系统渲染器前移除标识。用户设置 pause=no 时原子取走此前排队的 PAUSE，后续 PAUSE 继续生效。宿主替身运行实际文件卸载条件，覆盖 gapless、编码模式、已注销的写入/打断和并发回调。受控缓存的 mpv 单独检出来源锁版本。

逐帧回归直接编译 mpv 的内部暂停与增益处理函数，覆盖缓存暂停、静音逐帧、系统打断和显式恢复的先后顺序。持有 Phase30 A 归档时，设置 `VIDALL_PHASE30_INPUT` 并运行 `python3 native/tests/audio-interrupt/prepare.test.py`，以仓内来源锁核对真实派生清单。
