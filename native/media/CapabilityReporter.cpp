#include "CapabilityReporter.h"

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

bool contains(const std::array<const char*, 5>& values, const std::string& value)
{
    return std::any_of(values.begin(), values.end(), [&value](const char* candidate) {
        return value == candidate;
    });
}
} // namespace

namespace vidall {

CapabilityReport CapabilityReporter::report(const CapabilityObservation& observation)
{
    const std::string decoder = lower(observation.decoder);
    const bool hardwareActive = observation.hardwareDecodingRequested &&
        (decoder.find("videotoolbox") != std::string::npos ||
         decoder.find("mediacodec") != std::string::npos ||
         decoder.find("ohos") != std::string::npos);
    const bool softwareDecoder = !decoder.empty() && !hardwareActive;
    const std::array<const char*, 5> containers = {"mp4", "mkv", "ts", "avi", "flv"};
    const std::array<const char*, 5> protocols = {"file", "http", "https", "hls", "dash"};

    return {observation.decoder,
        hardwareActive ? HardwareDecoding::Active :
            (softwareDecoder ? HardwareDecoding::Fallback : HardwareDecoding::Unavailable),
        contains(containers, lower(observation.container)),
        contains(protocols, lower(observation.protocol))};
}

} // namespace vidall
