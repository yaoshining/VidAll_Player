#ifndef OHCODEC_SMB_RUNTIME_H
#define OHCODEC_SMB_RUNTIME_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
struct ohcodec_smb_runtime_v1 {
    size_t struct_size;
    const char *config_file, *state_root, *cache_root, *resource_root;
};
/* Call before any SMB context is created. 0 succeeds, -1 sets errno.
 * Strings are copied. Caller owns the files/directories for process lifetime.
 * No reset, directory creation or environment mutation is performed. */
int ohcodec_smb_runtime_configure_v1(const struct ohcodec_smb_runtime_v1 *);
#ifdef __cplusplus
}
#endif
#endif
