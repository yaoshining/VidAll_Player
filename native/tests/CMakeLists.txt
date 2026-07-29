cmake_minimum_required(VERSION 3.16)
project(vidall_native_contract_tests LANGUAGES CXX)

add_executable(session_lifecycle_test session_lifecycle_test.cpp ../session/session_lifecycle.cpp)
target_include_directories(session_lifecycle_test PRIVATE ../session)
target_compile_features(session_lifecycle_test PRIVATE cxx_std_17)

add_executable(localhost_proxy_lease_test localhost_proxy_lease_test.cpp ../media/proxy_lease_manager.cpp)

add_executable(player_session_test player_session_test.cpp ../session/player_session.cpp)
target_include_directories(player_session_test PRIVATE ../session)
target_compile_features(player_session_test PRIVATE cxx_std_17)

add_executable(surface_renderer_test surface_renderer_test.cpp ../render/surface_renderer.cpp)
target_include_directories(surface_renderer_test PRIVATE ../render)
target_compile_features(surface_renderer_test PRIVATE cxx_std_17)

add_executable(event_dispatcher_test event_dispatcher_test.cpp ../bridge/event_dispatcher.cpp)
target_include_directories(event_dispatcher_test PRIVATE ../bridge)
target_compile_features(event_dispatcher_test PRIVATE cxx_std_17)
target_include_directories(localhost_proxy_lease_test PRIVATE ../media)
target_compile_features(localhost_proxy_lease_test PRIVATE cxx_std_17)

enable_testing()
add_test(NAME session_lifecycle_test COMMAND session_lifecycle_test)
add_test(NAME localhost_proxy_lease_test COMMAND localhost_proxy_lease_test)
add_test(NAME player_session_test COMMAND player_session_test)
add_test(NAME surface_renderer_test COMMAND surface_renderer_test)
add_test(NAME event_dispatcher_test COMMAND event_dispatcher_test)
