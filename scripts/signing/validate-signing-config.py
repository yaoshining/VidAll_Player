#!/usr/bin/env python3
"""校验仓库中不含签名材料的多环境配置骨架。"""
import json
import re
import sys
from pathlib import Path


def load_json5(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"//.*$", "", source, flags=re.MULTILINE)
    source = re.sub(r",\s*([}\]])", r"\1", source)
    return json.loads(source)


def fail(message: str) -> None:
    print(f"配置校验失败：{message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("用法：validate-signing-config.py <build-profile.json5>")
    config = load_json5(Path(sys.argv[1]))
    app = config.get("app", {})
    signing = {item.get("name"): item for item in app.get("signingConfigs", [])}
    products = {item.get("name"): item for item in app.get("products", [])}
    environments = ("development", "ci")
    product_names = {"development": "default", "ci": "ci"}

    for environment in environments:
        signing_config = signing.get(environment)
        if not signing_config:
            fail(f"缺少 {environment} 签名配置")
        material = signing_config.get("material", {})
        prefix = f"signing/{environment}/"
        for field in ("certpath", "profile", "storeFile"):
            if not material.get(field, "").startswith(prefix):
                fail(f"{environment}.{field} 必须位于 {prefix}")
        for field in ("keyPassword", "storePassword"):
            if not material.get(field, ""):
                fail(f"{environment}.{field} 必须保留 DevEco 密文以支持构建")

        product_name = product_names[environment]
        product = products.get(product_name)
        if not product:
            fail(f"缺少 {product_name} product（{environment} 环境）")
        if product.get("signingConfig") != environment:
            fail(f"{environment} product 必须使用同名签名配置")

    for module in config.get("modules", []):
        for target in module.get("targets", []):
            applied = set(target.get("applyToProducts", []))
            missing = set(product_names.values()) - applied
            if missing:
                fail(f"模块 {module.get('name')} 未应用到环境：{', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
