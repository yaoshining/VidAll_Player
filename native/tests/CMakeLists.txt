cmake_minimum_required(VERSION 3.16)
project(vidall_native_contract_tests LANGUAGES CXX)

add_executable(session_lifecycle_test session_lifecycle_test.cpp ../session/session_lifecycle.cpp)
target_include_directories(session_lifecycle_test PRIVATE ../session)
target_compile_features(session_lifecycle_test PRIVATE cxx_std_17)

enable_testing()
add_test(NAME session_lifecycle_test COMMAND session_lifecycle_test)
