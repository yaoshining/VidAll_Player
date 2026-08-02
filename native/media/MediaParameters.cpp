#include "MediaParameters.h"

#include <algorithm>
#include <array>
#include <cctype>

namespace {
std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return value;
}
} // namespace

namespace vidall {

VideoParameterReport MediaParameters::video(const VideoObservation& observation)
{
    const int32_t numerator = observation.pixelAspectNumerator > 0 ? observation.pixelAspectNumerator : 1;
    const int32_t denominator = observation.pixelAspectDenominator > 0 ? observation.pixelAspectDenominator : 1;
    return {observation.width, observation.height, observation.pixelFormat, observation.rotation,
        std::to_string(numerator) + ":" + std::to_string(denominator), observation.decoder,
        observation.sdr ? "sdr" : "unverified"};
}

AudioParameterReport MediaParameters::audio(const AudioObservation& observation)
{
    return {observation.sampleRate, observation.channels, observation.channelLayout, observation.codec};
}

bool MediaParameters::isUnsupported(const std::string& feature)
{
    static const std::array<const char*, 3> unsupported = {"crop", "deinterlace", "screenshot"};
    const std::string normalized = lower(feature);
    return std::any_of(unsupported.begin(), unsupported.end(), [&normalized](const char* candidate) {
        return normalized == candidate;
    });
}

} // namespace vidall
