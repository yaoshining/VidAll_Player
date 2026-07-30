#ifndef VIDALL_PLAYER_ERROR_MAPPER_H
#define VIDALL_PLAYER_ERROR_MAPPER_H

#include "MediaLoader.h"
#include <string>

namespace vidall {

// Maps libmpv and media-level error conditions to structured PlayerError
// equivalents for cross-layer propagation. Errors must be sanitized
// (no credentials, full paths or sensitive query parameters).

struct MappedError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable;
};

class PlayerErrorMapper {
public:
    static MappedError mapLoadResult(MediaLoadResult result);
    static MappedError mapMpvError(int mpvErrorCode, const std::string& context);
    static MappedError mapTlsError(const std::string& detail);
    static MappedError mapRangeError();
    static MappedError mapFileNotFound(const std::string& sanitizedPath);
    static MappedError mapPermissionDenied();
};

} // namespace vidall
#endif