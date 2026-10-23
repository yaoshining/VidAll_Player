cmake_minimum_required(VERSION 3.4.1)
project(vidall_player_native)

set(CMAKE_SKIP_RPATH TRUE)

add_library(vidall_player_native SHARED
  napi_init.cpp
  ../../../../../native/runtime/process_runtime.cpp
  ../../../../../native/render/render_backend_policy.cpp
)
target_include_directories(vidall_player_native PRIVATE ../../../../../native/render ../../../../../native/runtime)
target_compile_features(vidall_player_native PRIVATE cxx_std_17)
target_link_libraries(vidall_player_native PUBLIC libace_napi.z.so libace_ndk.z.so libhilog_ndk.z.so)

if(OHOS_ARCH STREQUAL "arm64-v8a")
  set(CORE_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../../release/inputs/004-normal-core)
  set(LIBMPV_ROOT ${CORE_ROOT}/arm64-v8a)
  add_library(mpv SHARED IMPORTED)
  set_target_properties(mpv PROPERTIES IMPORTED_LOCATION ${LIBMPV_ROOT}/libmpv.so)
  target_include_directories(vidall_player_native PRIVATE ${CORE_ROOT}/include)
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=1)
  foreach(CORE_LIB avcodec.so.62 avformat.so.62 avfilter.so.11 avutil.so.60 swresample.so.6 swscale.so.9)
    add_library(${CORE_LIB} SHARED IMPORTED)
    set_target_properties(${CORE_LIB} PROPERTIES IMPORTED_LOCATION ${LIBMPV_ROOT}/lib${CORE_LIB})
    target_link_libraries(vidall_player_native PRIVATE ${CORE_LIB})
  endforeach()
  target_link_libraries(vidall_player_native PRIVATE mpv native_window EGL GLESv3)
else()
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=0)
endif()
