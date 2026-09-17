import json
import tempfile
import unittest
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
        self.assertEqual(result["orders"]["rows"], 12)
        self.assertEqual(result["items"]["rows"], 36)

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
