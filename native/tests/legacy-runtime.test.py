#!/usr/bin/env python3
"""固定运行库必须精确匹配现用 HAR，拒绝缺失、篡改、未知 ABI 和默认 STL。"""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 out=Path(td);bad=out/'bad.so';bad.write_bytes(b'wrong runtime')
 cases=[('arm64-v8a','none',ROOT/'entry/libs/arm64-v8a/libc++_shared.so',True),
        ('x86_64','none',ROOT/'entry/libs/x86_64/libc++_shared.so',True),
        ('arm64-v8a','c++_shared',bad,False),('riscv64','none',bad,False),
        ('arm64-v8a','none',bad,False),('arm64-v8a','none',out/'missing.so',False)]
 for abi,stl,runtime,expected in cases:
  script=out/'test.cmake';script.write_text(f'include("{ROOT}/native/cmake/legacy-cxx-runtime.cmake")\nvidall_check_legacy_runtime("{runtime}" "{abi}" "{stl}")\n')
  result=subprocess.run(['cmake','-P',str(script)],capture_output=True,text=True)
  assert (result.returncode==0)==expected,result.stderr
print('PASS 旧运行库固定：两个 ABI 正常、默认 STL/未知 ABI/篡改/缺失拒绝')
