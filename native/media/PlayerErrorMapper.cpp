#include "PlayerErrorMapper.h"

namespace vidall {

MappedError PlayerErrorMapper::mapLoadResult(MediaLoadResult result)
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

MappedError PlayerErrorMapper::mapMpvError(int mpvErrorCode, const std::string& context)
{
    // libmpv error codes (MPV_ERROR_*): map common ones to structured errors.
    // Context is sanitized before use in messages — no credentials or full paths.
    switch (mpvErrorCode) {
        case -2:  // MPV_ERROR_INVALID_PARAMETER
            return {"native", "INVALID_PARAMETER", "Invalid parameter passed to libmpv.", false};
        case -4:  // MPV_ERROR_UNSUPPORTED
            return {"media", "UNSUPPORTED", "Unsupported media format or feature.", false};
        case -5:  // MPV_ERROR_NOTHING_TO_PLAY
            return {"media", "NOTHING_TO_PLAY", "No playable content found.", false};
        case -7:  // MPV_ERROR_LOADING_FAILED
            return {"media", "LOADING_FAILED", "Failed to load media: " + context, true};
        case -10: // MPV_ERROR_AUDIO_ERROR
            return {"media", "AUDIO_ERROR", "Audio decoding or output error.", true};
        default:
            return {"native", "MPV_ERROR", "libmpv error code " + std::to_string(mpvErrorCode), true};
    }
}

MappedError PlayerErrorMapper::mapTlsError(const std::string& detail)
{
    // detail is already sanitized by the caller
    return {"network", "TLS_FAILED",
        "TLS error: " + detail, false};
}

MappedError PlayerErrorMapper::mapRangeError()
{
    return {"network", "RANGE_NOT_SATISFIABLE",
        "Server cannot satisfy the requested Range.", true};
}

MappedError PlayerErrorMapper::mapFileNotFound(const std::string& sanitizedPath)
{
    // sanitizedPath is already redacted — no full filesystem path
    return {"media", "FILE_NOT_FOUND",
        "Media file not found: " + sanitizedPath, false};
}

MappedError PlayerErrorMapper::mapPermissionDenied()
{
    return {"media", "PERMISSION_DENIED",
        "Permission denied for media file.", false};
}

} // namespace vidall