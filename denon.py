"""Read a Denon receiver's video format and set its audio delay.

Usage:
    denon.py WATCHED_INPUT          print what the receiver is playing as JSON
    denon.py set INPUT DELAY        set the audio delay, only if INPUT is selected

Output fields when reading:
    input          the selected input, by the receiver's internal name (AUX1)
    watched_input  WATCHED_INPUT, passed through so HA has it in one place
    resolution     incoming video resolution (4K, 1080p, ...)
    frame_rate     incoming frame rate in whole numbers (23.976 reads as 24)
    hdr            sdr, hdr10, dolby_vision, or the receiver's own label lowercased
    format         frame rate and HDR joined, e.g. 24_hdr10; "none" with no video
    delay          the selected input's audio delay in ms
    error          set instead of the above if the receiver couldn't be reached

The receiver's delay command changes whichever input is selected; there's
no way to aim it at one input. So `set` asks which input is selected and
sends the delay over the same connection a moment later, and does nothing
if the input has changed since HA decided what to send. HA will see the
new input on its next poll and decide again.

The receiver's address comes from the denonavr config entry in HA storage,
so nothing here needs editing.

The receiver answers queries on its control port (23) but never announces
video format changes on its own, so this has to be polled. Its answers go
to every open connection, including Home Assistant's own; the Denon
integration ignores lines it doesn't know.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import time
from pathlib import Path

CONFIG_ENTRIES = Path("/config/.storage/core.config_entries")
PORT = 23
TIMEOUT = 2.0

# The receiver's HDR labels, mapped to the names used in helper entity ids.
HDR_NAMES = {"---": "sdr", "HDR10": "hdr10", "Dolby Vision": "dolby_vision"}

# Receiver input names, e.g. AUX1, SAT/CBL. Arguments end up in a command
# line, so keep them to plain tokens.
INPUT_NAME = re.compile(r"^[A-Za-z0-9/._-]+$")

MAX_DELAY = 500  # ms; the receiver ignores anything higher


def receiver_host() -> str:
    data = json.loads(CONFIG_ENTRIES.read_text())
    for entry in data["data"]["entries"]:
        if entry["domain"] == "denonavr":
            return entry["data"]["host"]
    raise RuntimeError("no denonavr config entry")


class Receiver:
    def __init__(self, host: str) -> None:
        self.sock = socket.create_connection((host, PORT), timeout=TIMEOUT)
        self.buf = ""

    def close(self) -> None:
        self.sock.close()

    def ask(self, commands: list[str], prefixes: list[str]) -> dict[str, str]:
        """Send commands and return the first answer starting with each prefix."""
        answers: dict[str, str | None] = dict.fromkeys(prefixes)
        self.sock.sendall("".join(c + "\r" for c in commands).encode())
        deadline = time.monotonic() + TIMEOUT
        while None in answers.values() and time.monotonic() < deadline:
            self.sock.settimeout(max(deadline - time.monotonic(), 0.05))
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk.decode(errors="replace")
            *lines, self.buf = self.buf.split("\r")
            for line in lines:
                line = line.strip()
                for prefix in answers:
                    if answers[prefix] is None and line.startswith(prefix):
                        answers[prefix] = line[len(prefix):].strip()
        missing = [p.strip() for p, v in answers.items() if v is None]
        if missing:
            raise TimeoutError(f"no answer for {', '.join(missing)}")
        return answers  # type: ignore[return-value]


def read_state(watched_input: str) -> dict[str, object]:
    receiver = Receiver(receiver_host())
    try:
        answers = receiver.ask(
            ["SI?", "SSINFSIGRES ?", "SSINFSIGHDR ?", "PSDELAY ?"],
            ["SI", "SSINFSIGRES I", "SSINFSIGHDR I", "PSDELAY "],
        )
    finally:
        receiver.close()

    out: dict[str, object] = {"input": answers["SI"], "watched_input": watched_input}

    # "4K24", "1080p60"; "---" when there's no video.
    match = re.fullmatch(r"(.*?)(\d+)", answers["SSINFSIGRES I"])
    if match:
        out["resolution"], out["frame_rate"] = match[1], int(match[2])
    else:
        out["resolution"], out["frame_rate"] = None, None

    label = answers["SSINFSIGHDR I"]
    out["hdr"] = HDR_NAMES.get(label) or re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

    out["format"] = f"{out['frame_rate']}_{out['hdr']}" if out["frame_rate"] else "none"
    out["delay"] = int(answers["PSDELAY "])
    return out


def set_delay(expected_input: str, delay: int) -> str:
    receiver = Receiver(receiver_host())
    try:
        selected = receiver.ask(["SI?"], ["SI"])["SI"]
        if selected != expected_input:
            return f"skipped: input is {selected}, not {expected_input}"
        receiver.ask([f"PSDELAY {delay:03d}"], ["PSDELAY "])
        return f"set {expected_input} to {delay} ms"
    finally:
        receiver.close()


def main() -> int:
    args = sys.argv[1:]

    if len(args) == 1 and INPUT_NAME.match(args[0]):
        try:
            out = read_state(args[0])
        except Exception as err:
            out = {"error": f"{type(err).__name__}: {err}"}
        print(json.dumps(out))
        return 0

    if len(args) == 3 and args[0] == "set" and INPUT_NAME.match(args[1]) and args[2].isdigit():
        delay = int(args[2])
        if delay > MAX_DELAY:
            print(f"delay {delay} is over {MAX_DELAY} ms", file=sys.stderr)
            return 2
        try:
            print(set_delay(args[1], delay))
        except Exception as err:
            print(f"{type(err).__name__}: {err}", file=sys.stderr)
            return 1
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
