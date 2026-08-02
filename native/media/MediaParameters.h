#ifndef VIDALL_MEDIA_PARAMETERS_H
#define VIDALL_MEDIA_PARAMETERS_H

#include <cstdint>
#include <string>

namespace vidall {

struct VideoObservation {
    int32_t width = 0;
    int32_t height = 0;
    std::string pixelFormat;
    int32_t rotation = 0;
    int32_t pixelAspectNumerator = 1;
    int32_t pixelAspectDenominator = 1;
    std::string decoder;
    bool sdr = true;
};

struct VideoParameterReport {
    int32_t width = 0;
    int32_t height = 0;
    std::string pixelFormat;
    int32_t rotation = 0;
    std::string pixelAspectRatio;
    std::string decoder;
    std::string colorBaseline;
};

struct AudioObservation {
    int32_t sampleRate = 0;
    int32_t channels = 0;
    std::string channelLayout;
    std::string codec;
};

struct AudioParameterReport {
    int32_t sampleRate = 0;
    int32_t channels = 0;
    std::string channelLayout;
    std::string codec;
};

class MediaParameters {
public:
    static VideoParameterReport video(const VideoObservation& observation);
    static AudioParameterReport audio(const AudioObservation& observation);
    static bool isUnsupported(const std::string& feature);
};

} // namespace vidall
#endif
