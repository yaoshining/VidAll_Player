#ifndef VIDALL_PLAYER_ERROR_MAPPER_H
#define VIDALL_PLAYER_ERROR_MAPPER_H

#include "MediaLoader.h"
#include <string>

namespace vidall {

// Maps libmpv and media-level error conditions to structured MediaLoadError
// equivalents for cross-layer propagation. Errors must be sanitized
// (no credentials, full paths or sensitive query parameters).

class PlayerErrorMapper {
public:
    static MediaLoadError mapLoadResult(MediaLoadResult result);
    static MediaLoadError mapMpvError(int mpvErrorCode, const std::string& context);
    static MediaLoadError mapTlsError(const std::string& detail);
    static MediaLoadError mapRangeError();
    static MediaLoadError mapFileNotFound(const std::string& sanitizedPath);
    static MediaLoadError mapPermissionDenied();
};

} // namespace vidall
#endif