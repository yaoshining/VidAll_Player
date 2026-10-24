#!/usr/bin/env python3
"""离线资产工具：小夹具覆盖与生产相同的流式算法。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('assets', Path(__file__).with_name('prepare.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class AssetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root/'studio.zip'
        self.data = b'abcdefghijk'
        self.source.write_bytes(self.data)
        self.lock = {'archive': {'urlWithoutQuery': 'https://vendor.example/fixed.zip', 'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest(), 'sha256Provenance': '测试固定来源', 'persistentSourceVerified': False}, 'formalArtifactAllowed': False}
        self.out = self.root/'assets'

    def prepare(self):
        return M.prepare(self.source, self.out, self.lock, chunk=5)

    def test_layout_and_production_boundary(self):
        self.assertEqual(M.layout(4078480294, 2097152000), [2097152000, 1981328294])
        self.assertEqual(M.layout(10,5), [5,5])
        self.assertEqual(M.layout(1,5), [1])
        self.assertEqual(M.layout(2147483647,2147483647), [2147483647])
        for size,chunk in [(0,5),(-1,5),(5,0),(5,2147483648),(True,5),(5,True)]:
            with self.subTest(size=size,chunk=chunk), self.assertRaises(ValueError): M.layout(size,chunk)

    def test_normal_and_deterministic_manifest(self):
        first=self.prepare()
        self.assertEqual(first['archive'], self.lock['archive'])
        self.assertEqual([p['bytes'] for p in first['parts']], [5,5,1])
        self.assertEqual([p['offset'] for p in first['parts']], [0,5,10])
        self.assertFalse(first['formalArtifactAllowed'])
        result=M.verify(self.out,self.lock,chunk=5)
        self.assertTrue(result['passed'])
        self.assertEqual(result['archiveSHA256'],self.lock['archive']['sha256'])
        self.assertEqual(self.source.read_bytes(),self.data)
        second=self.root/'other';M.prepare(self.source,second,self.lock,chunk=5)
        self.assertEqual((self.out/'deveco26-archive-manifest.json').read_bytes(),(second/'deveco26-archive-manifest.json').read_bytes())

    def test_wrong_complete_hash_and_size_cleanup(self):
        for field,value in [('sha256','0'*64),('bytes',12),('bytes',10)]:
            bad=json.loads(json.dumps(self.lock));bad['archive'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):M.prepare(self.source,self.out,bad,chunk=5)
            self.assertFalse(self.out.exists())
            self.assertEqual(self.source.read_bytes(),self.data)

    def test_output_is_exclusive(self):
        self.out.mkdir(); keep=self.out/'mine';keep.write_text('unchanged')
        with self.assertRaises((ValueError,FileExistsError)):self.prepare()
        self.assertEqual(list(self.out.iterdir()),[keep]);self.assertEqual(keep.read_text(),'unchanged')

    def test_partial_write_cleanup(self):
        def fail(src,dest,size,whole):
            dest.write_bytes(b'partial');raise OSError('injected-write-failure')
        with patch.object(M,'write_piece',fail),self.assertRaises(OSError):self.prepare()
        self.assertFalse(self.out.exists());self.assertEqual(self.source.read_bytes(),self.data)

    def test_source_and_parent_symlinks_rejected(self):
        link=self.root/'alias';link.symlink_to(self.source)
        with self.assertRaises(ValueError):M.prepare(link,self.out,self.lock,chunk=5)
        self.assertFalse(self.out.exists())
        parent=self.root/'parent-alias';parent.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):M.prepare(self.source,parent/'target',self.lock,chunk=5)
        self.assertFalse((self.root/'target').exists())

    def test_dotdot_and_nonregular_input_rejected(self):
        directory=self.root/'dir';directory.mkdir()
        with self.assertRaises(ValueError):M.prepare(self.source,directory/'..'/'escape',self.lock,chunk=5)
        with self.assertRaises(ValueError):M.prepare(directory,self.out,self.lock,chunk=5)
        self.assertFalse(self.out.exists());self.assertFalse((self.root/'escape').exists())

    def test_missing_extra_tampered_or_symlink_part_rejected(self):
        for mode in ['missing','extra','tampered','symlink']:
            with self.subTest(mode=mode):
                dest=self.root/mode;M.prepare(self.source,dest,self.lock,chunk=5)
                part=dest/'studio26.zip.part001'
                if mode=='missing':part.unlink()
                elif mode=='extra':(dest/'extra').write_text('x')
                elif mode=='tampered':part.write_bytes(b'xxxxx')
                else:part.unlink();part.symlink_to(self.source)
                with self.assertRaises(ValueError):M.verify(dest,self.lock,chunk=5)

    def test_manifest_order_duplicate_offset_size_and_hash_rejected(self):
        for mode in ['order','duplicate','offset','size','hash','whole','path','chunk','extra-key']:
            with self.subTest(mode=mode):
                dest=self.root/mode;M.prepare(self.source,dest,self.lock,chunk=5)
                path=dest/'deveco26-archive-manifest.json';m=json.loads(path.read_text())
                if mode=='order':m['parts'].reverse()
                elif mode=='duplicate':m['parts'][1]=m['parts'][0]
                elif mode=='offset':m['parts'][1]['offset']=0
                elif mode=='size':m['parts'][0]['bytes']+=1
                elif mode=='hash':m['parts'][0]['sha256']='0'*64
                elif mode=='whole':m['archive']['sha256']='0'*64
                elif mode=='path':m['parts'][0]['name']='../studio.zip'
                elif mode=='chunk':m['chunkBytes']=6
                else:m['untrusted']='extra'
                path.write_text(json.dumps(m))
                with self.assertRaises(ValueError):M.verify(dest,self.lock,chunk=5)

    def test_manifest_cannot_redefine_trusted_complete_identity(self):
        self.prepare();manifest=self.out/'deveco26-archive-manifest.json';m=json.loads(manifest.read_text())
        replacement=b'XXXXXXXXXXX'
        for row in m['parts']:
            data=replacement[row['offset']:row['offset']+row['bytes']]
            (self.out/row['name']).write_bytes(data);row['sha256']=hashlib.sha256(data).hexdigest()
        m['archive']['sha256']=hashlib.sha256(replacement).hexdigest();manifest.write_text(json.dumps(m))
        with self.assertRaises(ValueError):M.verify(self.out,self.lock,chunk=5)

    def test_manifest_symlink_and_duplicate_json_keys_rejected(self):
        self.prepare();p=self.out/'deveco26-archive-manifest.json';raw=p.read_text();p.unlink();outside=self.root/'manifest';outside.write_text(raw);p.symlink_to(outside)
        with self.assertRaises(ValueError):M.verify(self.out,self.lock,chunk=5)
        p.unlink();p.write_text(raw.replace('"schemaVersion": 1','"schemaVersion": 1, "schemaVersion": 1'))
        with self.assertRaises(ValueError):M.verify(self.out,self.lock,chunk=5)

    def test_verify_rejects_manifest_or_prior_part_replacement_during_read(self):
        for mode in ['manifest','part']:
            with self.subTest(mode=mode):
                dest=self.root/('race-'+mode);M.prepare(self.source,dest,self.lock,chunk=5)
                original=M.ordinary_file;changed=False
                def observed(path):
                    nonlocal changed
                    if path.name=='studio26.zip.part002' and not changed:
                        changed=True
                        victim=dest/('deveco26-archive-manifest.json' if mode=='manifest' else 'studio26.zip.part001')
                        replacement=self.root/'replacement'
                        replacement.write_bytes(victim.read_bytes()+(b' ' if mode=='manifest' else b''))
                        replacement.replace(victim)
                    return original(path)
                with patch.object(M,'ordinary_file',observed),self.assertRaises(ValueError):M.verify(dest,self.lock,chunk=5)
                self.assertTrue(changed)

    def test_manifest_has_no_local_path_or_url_query(self):
        self.prepare();text=(self.out/'deveco26-archive-manifest.json').read_text()
        self.assertNotIn(str(self.root),text)
        bad=json.loads(json.dumps(self.lock));bad['archive']['urlWithoutQuery']+='?secret=never'
        with self.assertRaises(ValueError):M.prepare(self.source,self.root/'bad',bad,chunk=5)

if __name__=='__main__':unittest.main()
