import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "grocery_spend_lab", *args],
        cwd=ROOT.parent,
        text=True,
        capture_output=True,
        check=False,
    )


class SubprocessContractTests(unittest.TestCase):
    def test_discovery_and_schema_emit_json(self):
        capabilities = run_cli("capabilities")
        self.assertEqual(capabilities.returncode, 0, capabilities.stderr)
        self.assertEqual(json.loads(capabilities.stdout)["tool"], "grocery-spend-lab")
        schema = run_cli("schema", "--name", "orders")
        self.assertEqual(schema.returncode, 0, schema.stderr)
        self.assertEqual(json.loads(schema.stdout)["type"], "array")
        version = run_cli("--version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), "0.2.0")

    def test_invalid_input_uses_exit_three_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            orders = folder / "orders.json"
            items = folder / "items.json"
            output = folder / "result"
            orders.write_text("[]")
            items.write_text("[]")
            result = run_cli("analyze", "--orders", str(orders), "--items", str(items), "--output", str(output))
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "INVALID_INPUT")
            self.assertFalse(output.exists())

    def test_existing_output_uses_exit_five_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            result = run_cli(
                "analyze", "--orders", str(ROOT / "examples/orders.json"),
                "--items", str(ROOT / "examples/items.json"), "--output", str(output),
            )
            self.assertEqual(result.returncode, 5)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "OUTPUT_CONFLICT")
            self.assertEqual(marker.read_text(), "keep")

    def test_analysis_publishes_complete_hashed_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result"
            result = run_cli(
                "analyze", "--orders", str(ROOT / "examples/orders.json"),
                "--items", str(ROOT / "examples/items.json"), "--output", str(output),
                "--merchant", "Example Market",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope = json.loads(result.stdout)
            self.assertIn(envelope["status"], {"completed", "completed_with_warnings"})
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest, envelope)
            for artifact in manifest["artifacts"]:
                path = output / artifact["path"]
                self.assertTrue(path.is_file(), artifact["path"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
