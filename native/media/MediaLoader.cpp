#include "MediaLoader.h"

#include <algorithm>
#include <cctype>

namespace {

std::string toLower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

} // namespace

namespace vidall {

MediaLoadResult MediaLoader::load(const MediaLoadRequest& request)
{
    if (request.uri.empty()) {
        lastError_ = {"input", "INVALID_URI", "Media URI must not be empty.", false};
        return MediaLoadResult::RejectedInvalidUri;
    }

    if (request.kind == MediaKind::LocalFile) {
        return validateLocalFile(request);
    }
    return validateNetworkUri(request);
}

MediaLoadError MediaLoader::lastError() const
{
    return lastError_;
}

bool MediaLoader::isLocalFileUri(const std::string& uri)
{
    const std::string prefix = "file://";
    return uri.size() > prefix.size() &&
        toLower(uri.substr(0, prefix.size())) == prefix;
}

bool MediaLoader::parseUriAuthority(const std::string& uri, std::string& authority)
{
    // Extract scheme://authority from URI
    const std::size_t schemeEnd = uri.find("://");
    if (schemeEnd == std::string::npos) {
        return false;
    }
    const std::size_t authorityStart = schemeEnd + 3;
    const std::size_t authorityEnd = uri.find_first_of("/?#", authorityStart);
    if (authorityEnd == std::string::npos) {
        authority = uri.substr(authorityStart);
    } else {
        authority = uri.substr(authorityStart, authorityEnd - authorityStart);
    }
    return !authority.empty();
}

bool MediaLoader::hasUserinfo(const std::string& authority)
{
    return authority.find('@') != std::string::npos;
}

MediaLoadResult MediaLoader::validateLocalFile(const MediaLoadRequest& request)
{
    if (!isLocalFileUri(request.uri)) {
        lastError_ = {"input", "INVALID_LOCAL_FILE_URI",
            "Local media must use a file URI without user information.", false};
        return MediaLoadResult::RejectedInvalidLocalFileUri;
    }
    // Check for userinfo in authority
    const std::string prefix = "file://";
    const std::string afterPrefix = request.uri.substr(prefix.size());
    const std::size_t slashPos = afterPrefix.find('/');
    const std::string authority = (slashPos == std::string::npos)
        ? afterPrefix : afterPrefix.substr(0, slashPos);
    if (hasUserinfo(authority)) {
        lastError_ = {"input", "URL_USERINFO_FORBIDDEN",
            "Media URI must not contain user information.", false};
        return MediaLoadResult::RejectedUrlUserinfoForbidden;
    }
    // Path must start with / — when there is no slash, the authority is
    // followed directly by a relative path (e.g. file://localhostrelative),
    // which is not a valid local file URI.
    if (slashPos == std::string::npos) {
        lastError_ = {"input", "INVALID_LOCAL_FILE_URI",
            "Local file URI must contain an absolute path.", false};
        return MediaLoadResult::RejectedInvalidLocalFileUri;
    }
    const std::string authorityPart = afterPrefix.substr(0, slashPos);
    const std::string path = afterPrefix.substr(slashPos);
    // Authority must be empty or "localhost" for local file URIs
    const std::string normalizedAuth = toLower(authorityPart);
    if (!normalizedAuth.empty() && normalizedAuth != "localhost") {
        lastError_ = {"input", "INVALID_LOCAL_FILE_URI",
            "Local file URI must use empty or localhost authority.", false};
        return MediaLoadResult::RejectedInvalidLocalFileUri;
    }
    if (path.empty() || path[0] != '/') {
        lastError_ = {"input", "INVALID_LOCAL_FILE_URI",
            "Local file URI must contain an absolute path.", false};
        return MediaLoadResult::RejectedInvalidLocalFileUri;
    }

    lastError_ = {};
    return MediaLoadResult::Accepted;
}

MediaLoadResult MediaLoader::validateNetworkUri(const MediaLoadRequest& request)
{
    const std::size_t schemeEnd = request.uri.find("://");
    if (schemeEnd == std::string::npos) {
        lastError_ = {"input", "INVALID_URI", "Media URI must be an absolute URI.", false};
        return MediaLoadResult::RejectedInvalidUri;
    }
    const std::string scheme = toLower(request.uri.substr(0, schemeEnd));

    // Check for userinfo first — applies to all network URIs
    std::string authority;
    if (parseUriAuthority(request.uri, authority)) {
        if (hasUserinfo(authority)) {
            lastError_ = {"input", "URL_USERINFO_FORBIDDEN",
                "Media URI must not contain user information.", false};
            return MediaLoadResult::RejectedUrlUserinfoForbidden;
        }
    }

    // Unverified protocols take priority over kind mismatch — the consumer
    // used a protocol that hasn't passed device verification regardless of kind.
    static const std::vector<std::string> unverified = {"rtsp", "rtmp", "udp", "srt"};
    for (const auto& proto : unverified) {
        if (scheme == proto) {
            lastError_ = {"input", "PROTOCOL_NOT_VERIFIED",
                "Optional protocol " + scheme + " is not verified on device.", false};
            return MediaLoadResult::RejectedProtocolNotVerified;
        }
    }

    // Verify kind/scheme consistency
    if (request.kind == MediaKind::Http && scheme != "http") {
        lastError_ = {"input", "URI_KIND_MISMATCH",
            "HTTP media source requires an HTTP URI.", false};
        return MediaLoadResult::RejectedKindMismatch;
    }
    if (request.kind == MediaKind::Https && scheme != "https") {
        lastError_ = {"input", "URI_KIND_MISMATCH",
            "HTTPS media source requires an HTTPS URI.", false};
        return MediaLoadResult::RejectedKindMismatch;
    }

    lastError_ = {};
    return MediaLoadResult::Accepted;
}

} // namespace vidall