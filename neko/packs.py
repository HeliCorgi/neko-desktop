"""Untrusted packs are data, not code. Validate before invoking any image decoder."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib
from .model import STATES
from .storage import read_json

ASSETS = Path(__file__).resolve().parent / "assets"
MAX_PNG = 4 * 1024 * 1024
COLUMNS, ROWS, CELL = 4, 3, 256


@dataclass(frozen=True)
class Pack:
    manifest: dict
    png: bytes
    digest: str
    source: str


def validate_manifest(data: dict) -> dict:
    required = {"schema", "name", "author", "license", "atlas", "cell", "columns", "rows", "animations"}
    if set(data) != required:
        raise ValueError("pack.json: required/unknown keys do not match the template")
    for key, expected in {"schema": 1, "cell": CELL, "columns": COLUMNS, "rows": ROWS}.items():
        if type(data[key]) is not int or data[key] != expected:
            raise ValueError(f"{key} must be {expected}")
    for key in ("name", "author", "license"):
        if not isinstance(data[key], str) or not 1 <= len(data[key]) <= 80:
            raise ValueError(f"{key} must contain 1–80 characters")
        if any(ord(char) < 32 for char in data[key]):
            raise ValueError(f"{key} contains control characters")
    # A fixed basename prevents absolute paths, traversal, URLs, UNC paths and ADS.
    if data["atlas"] != "atlas.png":
        raise ValueError("atlas must be the local filename atlas.png")
    animations = data["animations"]
    if not isinstance(animations, dict) or set(animations) != set(STATES):
        raise ValueError("animations must define idle, walk, sleep, pet and eat")
    for state, animation in animations.items():
        if not isinstance(animation, dict) or set(animation) != {"frames", "fps"}:
            raise ValueError(f"{state}: expected frames and fps")
        if type(animation["fps"]) is not int or not 1 <= animation["fps"] <= 10:
            raise ValueError(f"{state}: fps must be an integer between 1 and 10")
        frames = animation["frames"]
        if not isinstance(frames, list) or not 1 <= len(frames) <= 12:
            raise ValueError(f"{state}: expected 1–12 frames")
        if any(type(index) is not int or not 0 <= index < COLUMNS * ROWS for index in frames):
            raise ValueError(f"{state}: frame indices must be integers between 0 and 11")
    return data


def validate_png(raw: bytes) -> None:
    if not 33 <= len(raw) <= MAX_PNG:
        raise ValueError("PNG must be at most 4 MiB")
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[8:16] != b"\x00\x00\x00\rIHDR":
        raise ValueError("Not a PNG image")
    width, height, depth, color, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", raw[16:29])
    if (width, height) != (CELL * COLUMNS, CELL * ROWS):
        raise ValueError("Atlas must be exactly 1024 × 768 pixels")
    if depth != 8 or color != 6 or compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("Export as non-interlaced, 8-bit RGBA PNG")
    # Reject animations and malformed chunk bounds before handing data to Qt.
    offset, ended, has_data = 8, False, False
    fixed_lengths = {b"IHDR": 13, b"pHYs": 9, b"sRGB": 1, b"gAMA": 4, b"cHRM": 32, b"IEND": 0}
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        if length > MAX_PNG or offset + length + 12 > len(raw):
            raise ValueError("Invalid PNG chunk size")
        if kind in (b"acTL", b"fcTL", b"fdAT"):
            raise ValueError("Animated PNG is not supported; use the sprite atlas")
        if kind not in {*fixed_lengths, b"IDAT"}:
            raise ValueError("Export PNG without metadata or ICC profiles (unsupported chunk)")
        if kind in fixed_lengths and length != fixed_lengths[kind]:
            raise ValueError("Invalid PNG metadata length")
        if kind == b"IHDR" and offset != 8:
            raise ValueError("Duplicate PNG header")
        expected_crc = struct.unpack(">I", raw[offset + 8 + length:offset + 12 + length])[0]
        if zlib.crc32(raw[offset + 4:offset + 8 + length]) != expected_crc:
            raise ValueError("PNG checksum mismatch")
        if kind == b"IDAT":
            has_data = True
        offset += length + 12
        if kind == b"IEND":
            if length != 0:
                raise ValueError("Invalid PNG ending")
            ended = True
            break
    if not ended or not has_data or offset != len(raw):
        raise ValueError("Truncated PNG or trailing data")


def fingerprint(manifest: dict, image: bytes) -> str:
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8") + b"\0" + image).hexdigest()


def load_pack(manifest_path: Path) -> Pack:
    if str(manifest_path).startswith(("//", "\\\\")):
        raise ValueError("Choose a local folder, not a network share")
    path = manifest_path.expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".json":
        raise ValueError("Select a pack.json file")
    data = validate_manifest(read_json(path))
    image_path = path.parent / "atlas.png"
    if image_path.is_symlink() or not image_path.is_file() or image_path.resolve(strict=True).parent != path.parent:
        raise ValueError("Atlas must not link outside its pack folder")
    with image_path.open("rb") as file:
        raw = file.read(MAX_PNG + 1)
    validate_png(raw)
    # Keep validated bytes: the decoder must NOT reopen the path (TOCTOU).
    return Pack(data, raw, fingerprint(data, raw), str(path))
