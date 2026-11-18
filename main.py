#!/usr/bin/env python3
"""Copy the committed entry.png to the output directory.

Server-safe: no rendering, no network, stdlib only. The image is the
already-committed entry.png beside this file; we just copy it byte-for-byte.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "entry.png")


def main():
    if len(sys.argv) > 1:
        out = sys.argv[1]
    else:
        outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
        out = os.path.join(outdir, "entry.png")
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    shutil.copyfile(SRC, out)
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))


if __name__ == "__main__":
    main()
