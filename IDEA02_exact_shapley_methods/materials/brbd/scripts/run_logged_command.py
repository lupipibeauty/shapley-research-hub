#!/usr/bin/env python3
"""Run one external command while preserving an unedited UTF-8 raw log.

The wrapper records the exact argv, working directory, timestamps and exit
status.  It does not interpret benchmark output.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> int:
    # Windows PTYs may expose a GBK stdout even when the child log is UTF-8.
    # Keep console streaming best-effort; the on-disk raw log remains UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing command after --")

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.meta.parent.mkdir(parents=True, exist_ok=True)
    start_wall = time.time()
    start_perf = time.perf_counter()
    with args.log.open("w", encoding="utf-8", errors="replace", newline="") as log:
        log.write(f"COMMAND_JSON={json.dumps(command, ensure_ascii=False)}\n")
        log.write(f"CWD={args.cwd.resolve()}\n")
        log.write(f"START_UNIX={start_wall}\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=args.cwd,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None

        def pump_output() -> None:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
                log.flush()

        pump = threading.Thread(target=pump_output, daemon=True)
        pump.start()
        timed_out = False
        try:
            return_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
            return_code = 124
            log.write(f"TIMEOUT_SECONDS={args.timeout_seconds}\n")
            log.flush()
        pump.join(timeout=30)
        elapsed = time.perf_counter() - start_perf
        log.write(f"END_UNIX={time.time()}\n")
        log.write(f"ELAPSED_SECONDS={elapsed}\n")
        log.write(f"RETURN_CODE={return_code}\n")

    meta = {
        "command": command,
        "cwd": str(args.cwd.resolve()),
        "start_unix": start_wall,
        "end_unix": time.time(),
        "elapsed_seconds": elapsed,
        "return_code": return_code,
        "timed_out": timed_out,
        "timeout_seconds": args.timeout_seconds,
        "log": str(args.log.resolve()),
    }
    args.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
