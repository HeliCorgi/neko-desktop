"""Small, bounded preferences; atomic writes. Never deserialize executable objects."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

MAX_JSON = 16_384


def _unique(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contains a duplicate key")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    with path.open("rb") as file:
        raw = file.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("JSON is too large (maximum 16 KiB)")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def write_json(path: Path, data: dict) -> None:
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_JSON:
        raise ValueError("JSON is too large")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".neko-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@dataclass
class Preferences:
    fps: int = 20
    size: int = 160
    topmost: bool = True
    pack: str = ""

    @classmethod
    def load(cls, path: Path) -> "Preferences":
        try:
            data = read_json(path)
        except (OSError, ValueError, RecursionError):
            return cls()
        prefs = cls()
        if type(data.get("fps")) is int and data["fps"] in (10, 20):
            prefs.fps = data["fps"]
        if type(data.get("size")) is int and data["size"] in (128, 160, 192):
            prefs.size = data["size"]
        if type(data.get("topmost")) is bool:
            prefs.topmost = data["topmost"]
        if isinstance(data.get("pack"), str) and len(data["pack"]) <= 2048:
            prefs.pack = data["pack"]
        return prefs

    def save(self, path: Path) -> None:
        write_json(path, asdict(self))
