#include "PlayerErrorMapper.h"

#include <algorithm>

namespace {

// Sanitize a context string: remove userinfo (user:pass@) and strip full
// filesystem paths, leaving only a safe summary for error messages.
std::string sanitizeContext(const std::string& raw)
{
    std::string result = raw;

    // Strip userinfo: anything before '@' in authority-like segments
    const std::size_t atPos = result.find('@');
    if (atPos != std::string::npos) {
        const std::size_t schemeEnd = result.find("://");
        if (schemeEnd != std::string::npos && atPos > schemeEnd) {
            result = result.substr(0, schemeEnd + 3) + result.substr(atPos + 1);
        } else {
            result = result.substr(atPos + 1);
        }
    }

    // Redact absolute filesystem paths: /data/... or /storage/... → [REDACTED_PATH]
    std::size_t pathStart = result.find("/data/");
    if (pathStart == std::string::npos) {
        pathStart = result.find("/storage/");
    }
    if (pathStart != std::string::npos) {
        result = result.substr(0, pathStart) + "[REDACTED_PATH]";
    }

    return result;
}

} // namespace

namespace vidall {

MediaLoadError PlayerErrorMapper::mapLoadResult(MediaLoadResult result)
{
    switch (result) {
        case MediaLoadResult::Accepted:
            return {};
        case MediaLoadResult::RejectedInvalidUri:
            return {"input", "INVALID_URI", "Media URI is invalid or empty.", false};
        case MediaLoadResult::RejectedFileNotFound:
            return {"media", "FILE_NOT_FOUND", "Media file not found.", false};
        case MediaLoadResult::RejectedPermissionDenied:
            return {"media", "PERMISSION_DENIED", "Permission denied for media file.", false};
        case MediaLoadResult::RejectedTlsFailed:
            return {"network", "TLS_FAILED", "TLS handshake or certificate verification failed.", false};
        case MediaLoadResult::RejectedRangeNotSatisfiable:
            return {"network", "RANGE_NOT_SATISFIABLE", "Requested Range cannot be satisfied.", false};
        case MediaLoadResult::RejectedInvalidLocalFileUri:
            return {"input", "INVALID_LOCAL_FILE_URI",
                "Local media must use a file URI without user information.", false};
        case MediaLoadResult::RejectedProtocolNotVerified:
            return {"input", "PROTOCOL_NOT_VERIFIED",
                "Optional protocol is not verified on device.", false};
        case MediaLoadResult::RejectedUrlUserinfoForbidden:
            return {"input", "URL_USERINFO_FORBIDDEN",
                "Media URI must not contain user information.", false};
        case MediaLoadResult::RejectedKindMismatch:
            return {"input", "URI_KIND_MISMATCH",
                "Media source kind does not match URI scheme.", false};
    }
    return {"native", "UNKNOWN", "Unknown media load error.", false};
}

MediaLoadError PlayerErrorMapper::mapMpvError(int mpvErrorCode, const std::string& context)
{
    // Sanitize context before embedding in error message
    const std::string safe = sanitizeContext(context);
    switch (mpvErrorCode) {
        case -2:  // MPV_ERROR_INVALID_PARAMETER
            return {"native", "INVALID_PARAMETER", "Invalid parameter passed to libmpv.", false};
        case -4:  // MPV_ERROR_UNSUPPORTED
            return {"media", "UNSUPPORTED", "Unsupported media format or feature.", false};
        case -5:  // MPV_ERROR_NOTHING_TO_PLAY
            return {"media", "NOTHING_TO_PLAY", "No playable content found.", false};
        case -7:  // MPV_ERROR_LOADING_FAILED
            return {"media", "LOADING_FAILED", "Failed to load media: " + safe, true};
        case -10: // MPV_ERROR_AUDIO_ERROR
            return {"media", "AUDIO_ERROR", "Audio decoding or output error.", true};
        default:
            return {"native", "MPV_ERROR", "libmpv error code " + std::to_string(mpvErrorCode), true};
    }
}

MediaLoadError PlayerErrorMapper::mapTlsError(const std::string& detail)
{
    // Sanitize detail to remove any credentials or paths
    const std::string safe = sanitizeContext(detail);
    return {"network", "TLS_FAILED",
        "TLS error: " + safe, false};
}

MediaLoadError PlayerErrorMapper::mapRangeError()
{
    return {"network", "RANGE_NOT_SATISFIABLE",
        "Server cannot satisfy the requested Range.", true};
}

MediaLoadError PlayerErrorMapper::mapFileNotFound(const std::string& sanitizedPath)
{
    // Sanitize again defensively — do not trust caller to have redacted
    const std::string safe = sanitizeContext(sanitizedPath);
    return {"media", "FILE_NOT_FOUND",
        "Media file not found: " + safe, false};
}

MediaLoadError PlayerErrorMapper::mapPermissionDenied()
{
    return {"media", "PERMISSION_DENIED",
        "Permission denied for media file.", false};
}

} // namespace vidall