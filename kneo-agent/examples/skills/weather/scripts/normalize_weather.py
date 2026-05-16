#!/usr/bin/env python3
"""
Normalize weather payloads into a compact one-line summary.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: normalize_weather.py '{\"city\": \"Tokyo\", \"temp_c\": 22, \"condition\": \"sunny\"}'")
        return 1

    payload = json.loads(sys.argv[1])
    print(f"{payload['city']}: {payload['temp_c']} C, {payload['condition']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
