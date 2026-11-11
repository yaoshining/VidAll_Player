import struct
from portable_elf import named_registry

def inspect_ohcodec_registration(reader,address,size,executable_ranges,expected_device_type=14):
    rows=named_registry(reader,address,size)
    found=[r for r in rows if r['name']=='ohcodec']
    if len(found)!=1:raise ValueError('OHCodec is not registered exactly once in the bound driver table')
    descriptor=found[0]['descriptor']
    device_type=struct.unpack('<i',reader.at(descriptor+28,4))[0]
    if device_type!=expected_device_type:raise ValueError('wrong hardware device type')
    mapper=reader.ptr(descriptor+48)
    if not mapper:raise ValueError('registered driver has no mapper')
    callbacks={'driverInit':reader.ptr(descriptor+32),'mapperInit':reader.ptr(mapper+8),'mapperMap':reader.ptr(mapper+24)}
    for name,pointer in callbacks.items():
        if not pointer or not any(start<=pointer<end for start,end in executable_ranges):
            raise ValueError(name+' is not in a bound executable section')
    return {'registered':True,'name':'ohcodec','descriptor':descriptor,'deviceType':device_type,'mapper':mapper,'callbacks':callbacks,'runtimeVerified':False}
