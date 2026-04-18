#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import struct
import subprocess
import sys
import termios
import fcntl
from typing import IO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Bridge a PTY-backed shell over stdio.')
    parser.add_argument('--shell', required=True)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--cols', type=int, default=120)
    parser.add_argument('--rows', type=int, default=34)
    parser.add_argument('--shell-arg', action='append', dest='shell_args', default=[])
    return parser.parse_args()


def set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack('HHHH', rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def main() -> int:
    args = parse_args()
    shell_args: list[str] = args.shell_args
    env = os.environ.copy()
    env['TERM'] = 'xterm-256color'
    env['COLORTERM'] = 'truecolor'

    master_fd, slave_fd = os.openpty()
    set_winsize(slave_fd, clamp(args.rows, 12, 120), clamp(args.cols, 40, 320))

    child = subprocess.Popen(
        [args.shell, *shell_args],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=args.cwd,
        env=env,
        start_new_session=True,
        close_fds=True,
    )
    os.close(slave_fd)

    stdin_fd = sys.stdin.fileno()
    stdout: IO[bytes] = sys.stdout.buffer
    selector = selectors.DefaultSelector()
    selector.register(master_fd, selectors.EVENT_READ, 'pty')
    selector.register(stdin_fd, selectors.EVENT_READ, 'stdin')

    control_fd: int | None
    try:
        os.fstat(3)
        control_fd = 3
        selector.register(control_fd, selectors.EVENT_READ, 'control')
    except OSError:
        control_fd = None

    control_buffer = bytearray()

    def shutdown(*_: object) -> None:
        if child.poll() is not None:
            return

        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while True:
            events = selector.select(timeout=0.25)

            for key, _ in events:
                if key.data == 'pty':
                    try:
                        data = os.read(master_fd, 65536)
                    except OSError:
                        data = b''

                    if not data:
                        return child.wait()

                    stdout.write(data)
                    stdout.flush()
                    continue

                if key.data == 'stdin':
                    data = os.read(stdin_fd, 65536)
                    if not data:
                        selector.unregister(stdin_fd)
                        continue

                    write_all(master_fd, data)
                    continue

                if key.data == 'control' and control_fd is not None:
                    data = os.read(control_fd, 4096)
                    if not data:
                        selector.unregister(control_fd)
                        control_fd = None
                        continue

                    control_buffer.extend(data)
                    while b'\n' in control_buffer:
                        raw_line, _, remainder = control_buffer.partition(b'\n')
                        control_buffer = bytearray(remainder)
                        if not raw_line.strip():
                            continue

                        message = json.loads(raw_line.decode('utf-8'))
                        if message.get('type') != 'resize':
                            continue

                        rows = clamp(int(message.get('rows', args.rows)), 12, 120)
                        cols = clamp(int(message.get('cols', args.cols)), 40, 320)
                        set_winsize(master_fd, rows, cols)
                        if child.poll() is None:
                            try:
                                os.killpg(child.pid, signal.SIGWINCH)
                            except ProcessLookupError:
                                pass

            if child.poll() is not None and not events:
                return child.returncode or 0
    finally:
        shutdown()
        try:
            os.close(master_fd)
        except OSError:
            pass

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
