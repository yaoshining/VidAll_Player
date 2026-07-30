#ifndef VIDALL_MEDIA_LOADER_H
#define VIDALL_MEDIA_LOADER_H

#include <cstdint>
#include <string>
#include <vector>

namespace vidall {

enum class MediaKind {
    LocalFile,
    Http,
    Https,
    Hls,
    Dash,
    LocalhostProxy,
    Smb,
};

enum class MediaLoadResult {
    Accepted,
    RejectedInvalidUri,
    RejectedFileNotFound,
    RejectedPermissionDenied,
    RejectedTlsFailed,
    RejectedRangeNotSatisfiable,
    RejectedInvalidLocalFileUri,
    RejectedProtocolNotVerified,
    RejectedUrlUserinfoForbidden,
    RejectedKindMismatch,
};

struct MediaLoadError {
    std::string domain;
    std::string code;
    std::string message;
    bool retryable;
};

struct HeaderEntry {
    std::string name;
    std::string value;
};

struct MediaLoadRequest {
    MediaKind kind;
    std::string uri;
    std::vector<HeaderEntry> headers;
};

class MediaLoader {
public:
    MediaLoadResult load(const MediaLoadRequest& request);
    MediaLoadError lastError() const;

private:
    MediaLoadError lastError_;

    static bool isLocalFileUri(const std::string& uri);
    static bool parseUriAuthority(const std::string& uri, std::string& authority);
    static bool hasUserinfo(const std::string& authority);
    MediaLoadResult validateLocalFile(const MediaLoadRequest& request);
    MediaLoadResult validateNetworkUri(const MediaLoadRequest& request);
};

} // namespace vidall
#endif