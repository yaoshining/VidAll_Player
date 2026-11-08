# G2 加载边界：arm64-v8a 绑定 libmpv 原生产物（VIDALL_MPV_AVAILABLE=1），
# x86_64 仅 NAPI probe（VIDALL_MPV_AVAILABLE=0），不表述为真实播放能力。
# libmpv.so SHA-256 见 scripts/test/legacy83-ci/inputs.json
# 详细边界见 release/manifests/candidate-003-libmpv-player-har.json
cmake_minimum_required(VERSION 3.4.1)
set(LEGACY_RUNTIME "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../entry/libs/${OHOS_ARCH}/libc++_shared.so")
include("${CMAKE_CURRENT_SOURCE_DIR}/../../../../../native/cmake/legacy-cxx-runtime.cmake")
vidall_check_legacy_runtime("${LEGACY_RUNTIME}" "${OHOS_ARCH}" "${OHOS_STL}")
project(vidall_player_native)

set(CMAKE_SKIP_RPATH TRUE)

add_library(vidall_player_native SHARED
  napi_init.cpp
  ../../../../../native/render/render_backend_policy.cpp
)
target_include_directories(vidall_player_native PRIVATE ../../../../../native/render)
target_compile_features(vidall_player_native PRIVATE cxx_std_17)
target_link_libraries(vidall_player_native PUBLIC libace_napi.z.so libace_ndk.z.so libhilog_ndk.z.so)

if(OHOS_ARCH STREQUAL "arm64-v8a")
  set(LIBMPV_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../../entry/src/main/cpp/third_party/libmpv/arm64-v8a)
  add_library(mpv SHARED IMPORTED)
  set_target_properties(mpv PROPERTIES IMPORTED_LOCATION ${LIBMPV_ROOT}/libmpv.so)
  target_include_directories(vidall_player_native PRIVATE ${LIBMPV_ROOT}/include)
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=1)
  target_link_libraries(vidall_player_native PRIVATE mpv native_window EGL GLESv3)
else()
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=0)
endif()

# SDK 只提供编译器和头文件；最终链接、打包使用已核对的旧运行库。
add_library(vidall_legacy_cxx SHARED IMPORTED)
set_target_properties(vidall_legacy_cxx PROPERTIES IMPORTED_LOCATION "${LEGACY_RUNTIME}")
target_include_directories(vidall_player_native SYSTEM PRIVATE "${OHOS_SDK_NATIVE}/llvm/include/libcxx-ohos/include/c++/v1")
target_link_libraries(vidall_player_native PRIVATE vidall_legacy_cxx)
