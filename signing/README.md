# Placeholder for HarmonyOS signing certificates

This directory should contain HarmonyOS signing certificate files:
- default.cer: HarmonyOS application certificate
- default.p12: PKCS12 keystore file
- default.p7b: Provisioning profile

For local development, copy your certificates from ~/.ohos/config/ to this directory.
For CI, these files should be provided as secrets or generated on the runner.
