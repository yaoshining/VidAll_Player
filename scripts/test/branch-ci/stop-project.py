"""仅停止本次构建在指定工程及独立 HVIGOR_USER_HOME 中登记的 daemon。"""
import argparse
import importlib.util
import os
from pathlib import Path

def stop(project, studio, out):
    path = Path(__file__).resolve().parents[1] / "deveco26-gates" / "consumer.py"
    spec = importlib.util.spec_from_file_location("consumer", path)
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    if not (out / "hvigor-home").is_dir():
        return
    env = consumer.E.child_environment(os.environ, studio / "Contents/tools/node/bin/node", studio, out)
    consumer.stop_project(project.resolve(), env, studio, out / "work", [], prefix="branch")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("project", "studio", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    stop(args.project, args.studio, args.out)
