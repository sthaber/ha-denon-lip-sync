"""Print what a Denon receiver is playing as JSON, for Home Assistant to poll.

Usage:
    denon.py

Output fields:
    input       the selected input, as the receiver names it internally (AUX1)
    resolution  incoming video resolution (4K, 1080p, ...)
    frame_rate  incoming frame rate in whole numbers (23.976 reads as 24)
    hdr         sdr, hdr10, dolby_vision, or the receiver's own label lowercased
    format      frame rate and HDR joined, e.g. 24_hdr10; "none" with no video
    delay       the selected input's audio delay in ms
    error       set instead of the above if the receiver couldn't be reached

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
import time
from pathlib import Path

CONFIG_ENTRIES = Path("/config/.storage/core.config_entries")
PORT = 23
TIMEOUT = 2.0

QUERIES = ("SI?", "SSINFSIGRES ?", "SSINFSIGHDR ?", "PSDELAY ?")

# The receiver's HDR labels, mapped to the names used in helper entity ids.
HDR_NAMES = {"---": "sdr", "HDR10": "hdr10", "Dolby Vision": "dolby_vision"}


def receiver_host() -> str:
    data = json.loads(CONFIG_ENTRIES.read_text())
    for entry in data["data"]["entries"]:
        if entry["domain"] == "denonavr":
            return entry["data"]["host"]
    raise RuntimeError("no denonavr config entry")


def query(host: str) -> dict[str, str]:
    """Send the queries and collect the first answer to each, keyed by prefix."""
    wanted = {"SI": None, "SSINFSIGRES I": None, "SSINFSIGHDR I": None, "PSDELAY ": None}
    with socket.create_connection((host, PORT), timeout=TIMEOUT) as sock:
        sock.sendall("".join(q + "\r" for q in QUERIES).encode())
        deadline = time.monotonic() + TIMEOUT
        buf = ""
        while None in wanted.values() and time.monotonic() < deadline:
            sock.settimeout(max(deadline - time.monotonic(), 0.05))
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            *lines, buf = buf.split("\r")
            for line in lines:
                line = line.strip()
                for prefix in wanted:
                    if wanted[prefix] is None and line.startswith(prefix):
                        wanted[prefix] = line[len(prefix):].strip()
    missing = [p.strip() for p, v in wanted.items() if v is None]
    if missing:
        raise TimeoutError(f"no answer for {', '.join(missing)}")
    return wanted


def parse(answers: dict[str, str]) -> dict[str, object]:
    out: dict[str, object] = {"input": answers["SI"]}

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


def main() -> None:
    try:
        out = parse(query(receiver_host()))
    except Exception as err:
        out = {"error": f"{type(err).__name__}: {err}"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
