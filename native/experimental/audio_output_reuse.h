#pragma once
// S36协议实验：尚未接入OHAudio。ConfirmDrain必须来自真实排空确认，
// 不能直接传入“已提交硬件”的位置，更不能用超时/估计延迟代替。
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <limits>
namespace vidall::experimental {
class AudioOutputReuse {
public:
    struct Format {
        unsigned rate, stride, sampleFormat, route;
        uint64_t channelLayout;
        bool operator==(const Format& b) const {
            return rate==b.rate && stride==b.stride && sampleFormat==b.sampleFormat && route==b.route && channelLayout==b.channelLayout;
        }
    };
private:
    static constexpr unsigned Capacity=2048, MaxStride=32;
    std::array<unsigned char,Capacity*MaxStride> bytes_{};
    std::atomic_flag lock_=ATOMIC_FLAG_INIT;
    // 每次平台回调均计数，包括争用/欠载的静音帧。平台须保证单回调消费者。
    std::atomic<uint64_t> submitted_{0};
    Format format_;
    uint64_t serial_=0, owner_=0, lastAudioEnd_=0, drainEnd_=0;
    unsigned head_=0, queued_=0;
    bool draining_=false, invalid_=false;
    class Guard {
        AudioOutputReuse& out_;
    public:
        bool acquired;
        explicit Guard(AudioOutputReuse& out):out_(out),acquired(!out.lock_.test_and_set(std::memory_order_acquire)){}
        ~Guard(){if(acquired)out_.lock_.clear(std::memory_order_release);}
    };
public:
    explicit AudioOutputReuse(Format format):format_(format) {
        invalid_=!format.rate || !format.stride || format.stride>MaxStride || !format.route || !format.channelLayout || (format.sampleFormat!=1 && format.sampleFormat!=2);
    }
    uint64_t Attach(Format format) {
        Guard g(*this);
        if(!g.acquired || invalid_ || owner_ || draining_ || !(format==format_) || serial_==UINT64_MAX)return 0;
        lastAudioEnd_=0;
        return owner_=++serial_;
    }
    bool Write(uint64_t token,const void* data,unsigned frames) {
        Guard g(*this);
        if(!g.acquired || invalid_ || !token || token!=owner_ || !data || frames>Capacity-queued_)return false;
        const auto* src=static_cast<const unsigned char*>(data);
        for(unsigned i=0;i<frames;i++)std::memcpy(&bytes_[((head_+queued_+i)%Capacity)*format_.stride],src+i*format_.stride,format_.stride);
        queued_+=frames;return true;
    }
    // 只读固定容量PCM，不访问mpv、平台API、不等待锁，不持有AO/会话指针。
    unsigned Callback(void* data,unsigned frames) {
        if(!data || frames>Capacity || !format_.stride || format_.stride>MaxStride)return 0;
        std::memset(data,0,frames*format_.stride); // 原型仅支持零为静音的PCM；U8/直通未接入。
        auto begin=submitted_.load();
        if(begin>UINT64_MAX-frames)return 0;
        submitted_.store(begin+frames);
        Guard g(*this);
        if(!g.acquired || invalid_ || !owner_)return 0;
        unsigned n=std::min(frames,queued_);auto* dst=static_cast<unsigned char*>(data);
        for(unsigned i=0;i<n;i++)std::memcpy(dst+i*format_.stride,&bytes_[((head_+i)%Capacity)*format_.stride],format_.stride);
        head_=(head_+n)%Capacity;queued_-=n;
        if(n)lastAudioEnd_=begin+n;
        return n;
    }
    bool Retire(uint64_t token) {
        Guard g(*this);
        if(!g.acquired || !token || token!=owner_)return false;
        owner_=0;queued_=0;head_=0;drainEnd_=lastAudioEnd_;draining_=true;return true;
    }
    bool ConfirmDrain(unsigned route,uint64_t playedThrough) {
        Guard g(*this);
        if(!g.acquired || invalid_ || route!=format_.route || !draining_ || playedThrough<drainEnd_ || playedThrough>submitted_.load())return false;
        draining_=false;return true;
    }
    int64_t DelayFrames(uint64_t token,unsigned route,uint64_t playedThrough) {
        Guard g(*this);
        if(!g.acquired || invalid_ || !token || token!=owner_ || route!=format_.route || playedThrough>submitted_.load())return -1;
        uint64_t pending=lastAudioEnd_>playedThrough?lastAudioEnd_-playedThrough:0;
        if(pending>INT64_MAX-queued_)return -1;
        return static_cast<int64_t>(pending+queued_);
    }
    bool Invalidate() {
        Guard g(*this);if(!g.acquired)return false;
        invalid_=true;owner_=0;queued_=0;return true;
    }
};
}
