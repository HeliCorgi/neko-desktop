"""Core-only CI. No Qt, native window, real GPU or approved-art claims."""
"""Run without Qt: python -m unittest discover -s tests -v."""
from copy import deepcopy
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest
import zlib
from neko.model import Cat, STATES, clamp_position
from neko.packs import (ASSETS, MAX_PNG, fingerprint, load_pack, validate_manifest, validate_png)
from neko.storage import MAX_JSON, Preferences, read_json, write_json


def chunk(kind: bytes, data: bytes = b"") -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(width=1024, height=768, extra=b"") -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanlines = (b"\0" + b"\0" * width * 4) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + extra + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND")


class BehaviourTests(unittest.TestCase):
    def test_initial_state(self):
        self.assertEqual(Cat().state, "idle")

    def test_known_actions(self):
        cat = Cat()
        for state in STATES:
            cat.act(state)
            self.assertEqual(cat.state, state)
            self.assertEqual(cat.elapsed, 0)
        with self.assertRaises(ValueError):
            cat.act("run_script")

    def test_frame_rate_independent_walking(self):
        positions = []
        for fps in (10, 20):
            cat = Cat(x=20)
            cat.act("walk")
            for _ in range(fps * 2):
                cat.step(1 / fps)
            positions.append(cat.x)
        self.assertAlmostEqual(positions[0], positions[1])
        self.assertAlmostEqual(positions[0], 88)

    def test_right_boundary(self):
        cat = Cat(x=599)
        cat.act("walk")
        cat.step(0.1)
        self.assertEqual((cat.x, cat.direction), (600, -1))

    def test_left_boundary(self):
        cat = Cat(x=1, direction=-1)
        cat.act("walk")
        cat.step(0.1)
        self.assertEqual((cat.x, cat.direction), (0, 1))

    def test_resize_clamps(self):
        cat = Cat()
        cat.set_bounds(-100)
        self.assertEqual((cat.x, cat.limit), (0, 0))

    def test_suspend_does_not_teleport(self):
        cat = Cat(x=100)
        cat.act("walk")
        cat.step(10000)
        self.assertLessEqual(cat.x - 100, 3.401)

    def test_negative_delta_ignored(self):
        cat = Cat()
        cat.step(-100)
        self.assertEqual(cat.elapsed, 0)

    def test_manual_sleep_is_held(self):
        cat = Cat()
        cat.act("sleep")
        for _ in range(1000):
            cat.step(0.5)
        self.assertEqual(cat.state, "sleep")
        cat.act("pet")
        self.assertFalse(cat.sleeping)

    def test_natural_nap_can_end(self):
        cat = Cat(state="sleep", sleeping=False, remaining=0.1)
        cat.step(0.2)
        self.assertEqual(cat.state, "idle")

    def test_simulation_stays_in_bounds(self):
        cat = Cat(rng=random.Random(7))
        for _ in range(10000):
            cat.step(0.1)
            self.assertIn(cat.state, STATES)
            self.assertTrue(0 <= cat.x <= cat.limit)

    def test_negative_screen_origin(self):
        self.assertEqual(clamp_position(-2200, -99, 160, 160, (-1920, 24, 1920, 1056)), (-1920, 24))
        self.assertEqual(clamp_position(900, 9000, 160, 160, (-1920, 24, 1920, 1056)), (-160, 920))

    def test_tiny_screen(self):
        self.assertEqual(clamp_position(200, 300, 160, 160, (10, 20, 100, 100)), (10, 20))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "settings.json"

    def test_round_trip(self):
        prefs = Preferences(fps=10, size=128, topmost=False, pack="猫/pack.json")
        prefs.save(self.path)
        self.assertEqual(prefs, Preferences.load(self.path))
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_corrupt_preferences_fall_back(self):
        self.path.write_text("{bad", encoding="utf-8")
        self.assertEqual(Preferences.load(self.path), Preferences())

    def test_missing_preferences(self):
        self.assertEqual(Preferences.load(self.path), Preferences())

    def test_invalid_types_do_not_enter_preferences(self):
        write_json(self.path, {"fps": True, "size": 999999, "topmost": "yes", "pack": ["bad"]})
        self.assertEqual(Preferences.load(self.path), Preferences())

    def test_duplicate_json_key(self):
        self.path.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_json(self.path)

    def test_oversized_json(self):
        self.path.write_bytes(b" " * (MAX_JSON + 1))
        with self.assertRaises(ValueError):
            read_json(self.path)

    def test_non_finite_json(self):
        self.path.write_text('{"a":NaN}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_json(self.path)

    def test_atomic_replacement(self):
        write_json(self.path, {"value": 1})
        write_json(self.path, {"value": 2})
        self.assertEqual(read_json(self.path)["value"], 2)


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = read_json(ASSETS / "pack.json")
        cls.image = png()

    def setUp(self):
        self.data = deepcopy(self.template)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        write_json(self.directory / "pack.json", self.data)
        (self.directory / "atlas.png").write_bytes(self.image)

    def test_valid_local_pack(self):
        pack = load_pack(self.directory / "pack.json")
        self.assertEqual(pack.manifest["name"], "こむぎ")
        self.assertEqual(pack.png, self.image)
        self.assertEqual(len(pack.digest), 64)

    def test_traversal_urls_absolute_and_ads_rejected(self):
        for path in ("../evil.png", "/tmp/evil.png", "https://x/evil.png", r"C:\evil.png", "atlas.png:code"):
            self.data["atlas"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_manifest(self.data)

    def test_unsupported_schema(self):
        self.data["schema"] = 2
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_extra_executable_field(self):
        self.data["script"] = "evil.py"
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_bool_is_not_an_index(self):
        self.data["animations"]["idle"]["frames"] = [True]
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_frame_bounds(self):
        for frame in (-1, 12, 0.5, "0"):
            self.data["animations"]["walk"]["frames"] = [frame]
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                validate_manifest(self.data)

    def test_frame_count_limit(self):
        self.data["animations"]["walk"]["frames"] = [0] * 13
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_rate_limit(self):
        for fps in (0, 11, True):
            self.data["animations"]["idle"]["fps"] = fps
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                validate_manifest(self.data)

    def test_missing_animation(self):
        del self.data["animations"]["eat"]
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_oversized_name(self):
        self.data["name"] = "a" * 81
        with self.assertRaises(ValueError):
            validate_manifest(self.data)

    def test_wrong_dimensions(self):
        with self.assertRaises(ValueError):
            validate_png(png(2, 2))

    def test_not_png(self):
        with self.assertRaises(ValueError):
            validate_png(b"<svg>" + b" " * 100)

    def test_corrupt_crc(self):
        raw = bytearray(self.image)
        raw[-1] ^= 1
        with self.assertRaises(ValueError):
            validate_png(bytes(raw))

    def test_truncated_and_trailing_png(self):
        for raw in (self.image[:-3], self.image + b"junk"):
            with self.assertRaises(ValueError):
                validate_png(raw)

    def test_oversized_png(self):
        with self.assertRaises(ValueError):
            validate_png(b"x" * (MAX_PNG + 1))

    def test_apng_rejected(self):
        with self.assertRaises(ValueError):
            validate_png(png(extra=chunk(b"acTL", b"\0" * 8)))

    def test_compressed_metadata_rejected(self):
        for kind in (b"zTXt", b"iTXt", b"iCCP"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_png(png(extra=chunk(kind, b"\0" * 10)))

    def test_missing_idat(self):
        raw = self.image[:33] + chunk(b"IEND")
        with self.assertRaises(ValueError):
            validate_png(raw)

    def test_symlink_rejected(self):
        image = self.directory / "atlas.png"
        image.unlink()
        other = self.directory / "other.png"
        other.write_bytes(self.image)
        try:
            image.symlink_to(other)
        except OSError:
            self.skipTest("This host cannot create symlinks without elevated permissions")
        with self.assertRaises(ValueError):
            load_pack(self.directory / "pack.json")

    def test_fingerprint_changes_with_art_or_manifest(self):
        first = fingerprint(self.data, self.image)
        self.data["name"] = "別の猫"
        self.assertNotEqual(first, fingerprint(self.data, self.image))
        self.assertNotEqual(first, fingerprint(self.template, self.image + b"x"))

    def test_fingerprint_independent_of_key_order(self):
        self.assertEqual(fingerprint(self.data, self.image), fingerprint(dict(reversed(list(self.data.items()))), self.image))



if __name__ == "__main__":
    unittest.main()
