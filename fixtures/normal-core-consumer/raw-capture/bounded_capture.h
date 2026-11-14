#pragma once
#include <cstdint>
#include <cstring>
#include <vector>

// 仅收集当前授权实验；媒体时间按轨检查，不用回调到达时刻替换。
class RawCaptureBuffer {
    std::vector<uint8_t> data_;
    size_t limit_, maxRecords_, records_=0;
    int64_t last_[2]={0,0};
    bool failed_=false, strict_;
    unsigned anomalies_=0;
public:
    RawCaptureBuffer(size_t limit, size_t records,bool strict=true):limit_(limit),maxRecords_(records),strict_(strict) {data_.reserve(limit);}
    bool append(uint32_t type,int64_t timestamp,int64_t arrival,const uint8_t* bytes,size_t size) {
        if(failed_)return false;
        if(type<1||type>2||timestamp<=0||arrival<=0||!bytes||!size||size>UINT32_MAX||
           records_>=maxRecords_||data_.size()>limit_||limit_-data_.size()<24||
           size>limit_-data_.size()-24)return !(failed_=true);
        if(timestamp<=last_[type-1]){++anomalies_;if(strict_)return !(failed_=true);}
        // 文件格式固定小端，目标ARM64及宿主Mac同为小端；不依赖结构体填充。
        auto put=[&](uint64_t value,unsigned n){for(unsigned i=0;i<n;++i)data_.push_back((value>>(i*8))&255);};
        put(type,4);put(size,4);put(timestamp,8);put(arrival,8);
        data_.insert(data_.end(),bytes,bytes+size);last_[type-1]=timestamp;++records_;return true;
    }
    bool error()const{return failed_;}
    unsigned anomalies()const{return anomalies_;}
    size_t records()const{return records_;}
    const std::vector<uint8_t>& bytes()const{return data_;}
};
