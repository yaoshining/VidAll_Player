#include "../../../fixtures/normal-core-consumer/presentation-evidence/bounded_enumeration.h"
#include <cassert>
#include <iostream>
int main() {
  int calls=0;
  auto ok=[&](uint32_t* n,int* data) { ++calls; if(!data)*n=2;else {data[0]=4;data[1]=9;*n=2;}return 0;};
  auto a=BoundedEnumerate<int>(ok,8);assert(a.ok && a.values.size()==2 && a.values[1]==9 && calls==2);
  auto empty=[](uint32_t* n,int*){*n=0;return 0;};assert(BoundedEnumerate<int>(empty,8).ok);
  auto fail=[](uint32_t*,int*){return -3;};auto b=BoundedEnumerate<int>(fail,8);assert(!b.ok && b.error==-3);
  calls=0;auto large=[&](uint32_t* n,int*){++calls;*n=100000;return 0;};assert(!BoundedEnumerate<int>(large,8).ok && calls==1);
  calls=0;auto changing=[&](uint32_t* n,int* p){++calls;*n=2;return p?5:0;};assert(!BoundedEnumerate<int>(changing,8).ok && calls==6);
  calls=0;auto grows=[&](uint32_t* n,int* p){++calls;if(!p){*n=2;return 0;}*n=9;return 0;};assert(!BoundedEnumerate<int>(grows,8).ok);
  std::cout<<"PASS: bounded capability enumeration normal/empty/error/limit/incomplete/count growth\n";
}
