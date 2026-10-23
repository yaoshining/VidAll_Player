/* VidAll isolated mpv extension: fatal OHCodec completion-unknown handling. */
#ifndef MPV_OHCODEC_TERMINAL_H_
#define MPV_OHCODEC_TERMINAL_H_
#include <stdint.h>
#include <mpv/client.h>
#ifdef __cplusplus
extern "C" {
#endif
#define MPV_OHCODEC_TERMINAL_ABI_VERSION 0x00010000u
enum mpv_ohcodec_terminal_stage {
    MPV_OHCODEC_TERMINAL_DRAIN = 1, /* first drain reports completion unknown */
    MPV_OHCODEC_TERMINAL_RETAINED = 2, /* owner/mapper already retained */
    MPV_OHCODEC_TERMINAL_LATE = 3 /* late teardown or creation completion */
};
/* This process-lifetime extension protects OHCodec/Vulkan owner creation.
 * It does not isolate a process or automatically gate all decoder/tasks.
 * Do not unload this library after registration. Application must reject a
 * failed registration/enable before playback and must not software-fallback.
 * size must cover v1. Future larger objects are accepted; unknown tail untouched.
 * abi_version must equal the supported version. All reserved fields must be 0.
 * owner_tag is opaque numeric identity, never dereference it. */
typedef struct mpv_ohcodec_terminal_record {
    uint32_t size;
    uint32_t abi_version;
    int32_t platform_error;
    uint32_t stage;
    uint64_t owner_tag;
    uint64_t reserved[4];
} mpv_ohcodec_terminal_record;
typedef void (*mpv_ohcodec_terminal_handler)(const mpv_ohcodec_terminal_record *, void *);
typedef struct mpv_ohcodec_terminal_config {
    uint32_t size;
    uint32_t abi_version;
    mpv_ohcodec_terminal_handler handler;
    void *opaque;
    uint64_t reserved[4];
} mpv_ohcodec_terminal_config;
/* Independent extension version; does not change MPV_CLIENT_API_VERSION. */
MPV_EXPORT uint32_t mpv_ohcodec_terminal_api_version(void);
/* Return 0 or negative mpv error. Copies config; code/opaque must live until
 * process exit. One registration, no unregister/reset. Never calls handler
 * synchronously. Handler runs once on an independent thread after terminal.
 * Do not query/stop/release mpv from handler. Use cached progress only.
 * A separate application deadline must supervise snapshot independently. */
MPV_EXPORT int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config *config);
MPV_EXPORT int mpv_ohcodec_terminal_enable(void);
/* Returns 0 healthy, 1 terminal, negative invalid input. Bounded copy of v1,
 * no mpv/core/VO locks. Initialize size/version and zero reserved first.
 * On success size reports v1 bytes written; unknown caller tail is untouched. */
MPV_EXPORT int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record *record);
#ifdef __cplusplus
}
#endif
#endif
