import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from grocery_spend_lab.cli import CAPABILITIES
from grocery_spend_lab.validation import validate_inputs


ROOT = Path(__file__).resolve().parents[1]


class AgentContractTests(unittest.TestCase):
    def test_capabilities_are_versioned_and_discover_core_commands(self):
        self.assertEqual(CAPABILITIES["schema_version"], "1.0")
        self.assertTrue({"validate", "analyze", "schema"} <= set(CAPABILITIES["commands"]))

    def test_synthetic_examples_validate(self):
        result = validate_inputs(ROOT / "examples/orders.json", ROOT / "examples/items.json")
        self.assertTrue(result["valid"], result["errors"])
        self.assertGreaterEqual(result["orders"]["rows"], 40)
        self.assertGreaterEqual(result["items"]["rows"], 500)
        self.assertGreaterEqual(
            (date.fromisoformat(result["orders"]["date_end"]) - date.fromisoformat(result["orders"]["date_start"])).days,
            330,
        )

    def test_synthetic_examples_are_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            orders = folder / "orders.json"
            items = folder / "items.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/generate_synthetic_examples.py"),
                    "--orders", str(orders),
                    "--items", str(items),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(orders.read_bytes(), (ROOT / "examples/orders.json").read_bytes())
            self.assertEqual(items.read_bytes(), (ROOT / "examples/items.json").read_bytes())

    def test_orphan_item_blocks_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            orders = json.loads((ROOT / "examples/orders.json").read_text())
            items = json.loads((ROOT / "examples/items.json").read_text())
            items[0]["receipt_key"] = "missing-receipt"
            (folder / "orders.json").write_text(json.dumps(orders))
            (folder / "items.json").write_text(json.dumps(items))
            result = validate_inputs(folder / "orders.json", folder / "items.json")
            self.assertFalse(result["valid"])
            self.assertTrue(any("absent from orders" in error for error in result["errors"]))

    def test_duplicate_order_blocks_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            orders = json.loads((ROOT / "examples/orders.json").read_text())
            orders.append(orders[0])
            (folder / "orders.json").write_text(json.dumps(orders))
            (folder / "items.json").write_text((ROOT / "examples/items.json").read_text())
            result = validate_inputs(folder / "orders.json", folder / "items.json")
            self.assertFalse(result["valid"])
            self.assertTrue(any("duplicate receipt_key" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
