"""Measure the authored command text for one equivalent modeling task."""

import argparse
import json
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitquen_forge.language import parse, serialize  # noqa: E402

PYTHON = """import bpy
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
base = bpy.context.object
base.name = "base"
base.dimensions = (4, 4, 2)
base.location = (1, 0, 0)
"""
COMPACT = "+cube/base size=4,4,2\n@pos/base 1,0,0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoding", default="o200k_base")
    args = parser.parse_args()
    tokenizer = tiktoken.get_encoding(args.encoding)
    readable = serialize(parse(COMPACT), readable=True)
    scripts = {"python": PYTHON.strip(), "readable": readable, "compact": COMPACT}
    counts = {name: len(tokenizer.encode(source)) for name, source in scripts.items()}
    print(
        json.dumps(
            {"encoding": args.encoding, "scope": "command text only", "tokens": counts}, indent=2
        )
    )


if __name__ == "__main__":
    main()
