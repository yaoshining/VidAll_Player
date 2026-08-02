#!/usr/bin/env python3
"""在受控构建环境将签名密码写入临时 build-profile 副本。"""
import argparse
import os
import re
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"签名密码注入失败：{message}")


def replace_empty_passwords(source: str, environment: str, key_password: str, store_password: str) -> str:
    config_pattern = re.compile(
        r'("name"\s*:\s*"' + re.escape(environment) + r'"\s*,.*?"material"\s*:\s*\{)(.*?)(\n\s*\})',
        re.DOTALL,
    )
    match = config_pattern.search(source)
    if not match:
        fail(f"找不到 {environment} 签名配置")

    material = match.group(2)
    replacements = 0
    for field, value in (("keyPassword", key_password), ("storePassword", store_password)):
        pattern = re.compile(r'("' + field + r'"\s*:\s*)""')
        material, count = pattern.subn(r'\g<1>"' + value + '"', material, count=1)
        replacements += count
    if replacements != 2:
        fail(f"{environment} 签名配置中的密码字段必须为空")
    return source[:match.start(2)] + material + source[match.end(2):]


def main() -> None:
    parser = argparse.ArgumentParser(description="向临时构建配置注入签名密码")
    parser.add_argument("--environment", choices=("development", "ci", "production"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    key_password = os.environ.get("OHOS_SIGNING_KEY_PASSWORD")
    store_password = os.environ.get("OHOS_SIGNING_STORE_PASSWORD")
    if not key_password or not store_password:
        fail("必须设置 OHOS_SIGNING_KEY_PASSWORD 与 OHOS_SIGNING_STORE_PASSWORD")

    source = args.config.read_text(encoding="utf-8")
    args.config.write_text(
        replace_empty_passwords(source, args.environment, key_password, store_password),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
