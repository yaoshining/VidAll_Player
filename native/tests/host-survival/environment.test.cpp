#include "environment_lifetime.h"
#include <cassert>
using vidall::runtime::EnvironmentLifetime;
int main(){
 int a,b;
 auto first=EnvironmentLifetime::Open(&a),other=EnvironmentLifetime::Open(&b);
 assert(first&&other&&first!=other&&EnvironmentLifetime::Current(&a)==first);
 assert(EnvironmentLifetime::Open(&a)==first);
 assert(first->Matches(&a)&&!first->Matches(&b));
 EnvironmentLifetime::Close(first);
 assert(!first->IsOpen()&&!first->Matches(&a)&&!EnvironmentLifetime::Current(&a));
 assert(other->IsOpen());
 auto reused=EnvironmentLifetime::Open(&a);assert(reused!=first&&reused->IsOpen());
 EnvironmentLifetime::Close(first);assert(EnvironmentLifetime::Current(&a)==reused);
 EnvironmentLifetime::Close(reused);EnvironmentLifetime::Close(other);
}
