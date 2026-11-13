"""证据接收器：完整性失败不得产生可误用的音轨。"""
import base64
import copy
import hashlib
import unittest
from receive import assemble


def packets(data=b'x' * 600000):
    return [dict(version='spec017-evidence-v1', kind='capture', bytes=len(data),
                 sha256=hashlib.sha256(data).hexdigest(), chunks=(len(data)+262143)//262144,
                 index=i//262144, data=base64.b64encode(data[i:i+262144]).decode())
            for i in range(0, len(data), 262144)]


class ReceiveTest(unittest.TestCase):
    def test_round_trip_boundary_and_identical_retry(self):
        for size in [1, 262144, 262145, 600000]:
            data=bytes(range(256))*(size//256)+bytes(range(size%256))
            p=packets(data)
            self.assertEqual(assemble([p[0]]+p), data)

    def test_missing_reordered_conflicting_replay(self):
        p=packets()
        bad=copy.deepcopy(p[0]);bad['data']='YQ=='
        for values in [[], p[:-1], p[1:], [p[1],p[0],p[2]], [p[0],bad]+p[1:]]:
            with self.assertRaises(ValueError): assemble(values)

    def test_bad_metadata_hash_payload_and_size(self):
        for key,value in [('version','old'),('kind','../secret'),('bytes',16777217),
                          ('bytes',True),('index',True),('chunks',1),('sha256','0'*64),
                          ('data','@@@'),('data','YQ==')]:
            p=packets();p[0][key]=value
            with self.assertRaises(ValueError,msg=key): assemble(p)
        p=packets();p[1]['kind']='events'
        with self.assertRaises(ValueError): assemble(p)


if __name__=='__main__': unittest.main()
