#include <libavformat/ohcodec_smb_runtime.h>
int main(void) { struct ohcodec_smb_runtime_v1 c = {sizeof(c),0,0,0,0}; return ohcodec_smb_runtime_configure_v1(&c); }
