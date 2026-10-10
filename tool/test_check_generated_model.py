"""Regression tests for cross-platform comparison of generated model assets."""

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from check_generated_model import ModelMismatch, compare_assets, compare_glb, compare_json


def fixture():
    doc = {
        "asset": {"version": "2.0", "copyright": "FlutterKaigi / Yakuran", "extras": {"license": "CC-BY-NC-ND-4.0"}},
        "buffers": [{"byteLength": 20}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 12},
            {"buffer": 0, "byteOffset": 12, "byteLength": 4},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3", "min": [0.0, 1.0, 2.0]},
            {"bufferView": 1, "componentType": 5125, "count": 1, "type": "SCALAR"},
        ],
    }
    return doc, struct.pack("<3fI4s", 0.0, 1.0, 2.0, 7, b"keep")


def glb(doc, binary):
    encoded = json.dumps(doc, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    body = struct.pack("<I4s", len(encoded), b"JSON") + encoded
    body += struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    return struct.pack("<4sII", b"glTF", 2, len(body) + 12) + body


class GeneratedModelComparisonTest(unittest.TestCase):
    def setUp(self):
        self.doc, self.binary = fixture()
        self.expected = glb(self.doc, self.binary)

    def test_small_json_and_float32_rounding_differences_pass(self):
        changed = copy.deepcopy(self.doc)
        changed["accessors"][0]["min"][0] = 1e-16
        binary = bytearray(self.binary)
        struct.pack_into("<3f", binary, 0, 1e-16, 1.0000001, 2.0)
        compare_glb(self.expected, glb(changed, bytes(binary)))

    def test_changed_vertex_fails(self):
        binary = bytearray(self.binary)
        struct.pack_into("<f", binary, 0, 0.01)
        with self.assertRaisesRegex(ModelMismatch, "float"):
            compare_glb(self.expected, glb(self.doc, bytes(binary)))

    def test_removed_copyright_or_license_fails(self):
        for field in ("copyright", "extras"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.doc)
                del changed["asset"][field]
                with self.assertRaisesRegex(ModelMismatch, "object keys"):
                    compare_glb(self.expected, glb(changed, self.binary))

    def test_changed_integer_accessor_fails(self):
        binary = bytearray(self.binary)
        struct.pack_into("<I", binary, 12, 8)
        with self.assertRaisesRegex(ModelMismatch, "non-float byte"):
            compare_glb(self.expected, glb(self.doc, bytes(binary)))

    def test_unreferenced_binary_data_is_strict(self):
        with self.assertRaisesRegex(ModelMismatch, "non-float byte"):
            compare_glb(self.expected, glb(self.doc, self.binary[:-4] + b"oops"))

    def test_json_types_structure_and_integers_are_strict(self):
        for before, after in ((1, 1.0), (1, True), (10000000, 10000001),
                              ([1.0], [1.0, 2.0]), ({"a": 1}, {"b": 1}),
                              ("CC-BY-NC-ND-4.0", "MIT")):
            with self.subTest(before=before, after=after):
                with self.assertRaises(ModelMismatch):
                    compare_json(before, after)

    def test_non_finite_floats_fail(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ModelMismatch, "non-finite"):
                    compare_json(value, value)
                binary = bytearray(self.binary)
                struct.pack_into("<f", binary, 0, value)
                with self.assertRaisesRegex(ModelMismatch, "non-finite"):
                    compare_glb(self.expected, glb(self.doc, bytes(binary)))

    def test_interleaved_padding_is_strict(self):
        doc = copy.deepcopy(self.doc)
        doc["bufferViews"][0].update(byteLength=12, byteStride=8)
        doc["accessors"][0].update(count=2, type="SCALAR")
        baseline = glb(doc, self.binary)
        small_change = bytearray(self.binary)
        struct.pack_into("<f", small_change, 8, 2.0000002)
        compare_glb(baseline, glb(doc, bytes(small_change)))
        struct.pack_into("<f", small_change, 4, 1.0000001)
        with self.assertRaisesRegex(ModelMismatch, "non-float byte"):
            compare_glb(baseline, glb(doc, bytes(small_change)))

    def test_overlapping_integer_view_remains_strict(self):
        doc = copy.deepcopy(self.doc)
        doc["bufferViews"][1]["byteOffset"] = 0
        binary = bytearray(self.binary)
        struct.pack_into("<f", binary, 0, 1e-16)
        with self.assertRaisesRegex(ModelMismatch, "non-float byte"):
            compare_glb(glb(doc, self.binary), glb(doc, bytes(binary)))

    def test_invalid_chunk_or_accessor_bounds_fail(self):
        with self.assertRaises(ModelMismatch):
            compare_glb(self.expected, self.expected[:-1])
        doc = copy.deepcopy(self.doc)
        doc["accessors"][0]["count"] = 2
        invalid = glb(doc, self.binary)
        with self.assertRaisesRegex(ModelMismatch, "outside view"):
            compare_glb(invalid, invalid)

    def test_manifest_size_is_verified_for_each_serialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / name for name in ("before", "after")]
            changed = copy.deepcopy(self.doc)
            changed["accessors"][0]["min"][0] = 1.23456789e-16
            models = [self.expected, glb(changed, self.binary)]
            self.assertNotEqual(len(models[0]), len(models[1]))
            for path, model in zip(paths, models):
                path.mkdir()
                (path / "dashmaru.glb").write_bytes(model)
                (path / "dashmaru_manifest.json").write_text(
                    json.dumps({"bytes": len(model), "meshes": 1}), encoding="utf-8")
            compare_assets(*paths)
            (paths[1] / "dashmaru_manifest.json").write_text(
                json.dumps({"bytes": len(models[1]) + 4, "meshes": 1}), encoding="utf-8")
            with self.assertRaisesRegex(ModelMismatch, "manifest.bytes"):
                compare_assets(*paths)


if __name__ == "__main__":
    unittest.main()
