#!/usr/bin/env python3
"""Generate a deterministic, varied grocery history for documentation and tests."""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


DEFAULT_SEED = 20260917
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Product:
    description: str
    size: str
    upc: str
    base_cents: int
    selection_weight: float
    weighted: bool = False
    taxable: bool = False
    snap_eligible: bool = True


CATALOG = [
    Product("Fresh Bananas", "1 lb", "0000000004011", 69, 8.5, weighted=True),
    Product("Organic Fresh Honeycrisp Apples", "1 lb", "0000000032828", 249, 3.4, weighted=True),
    Product("Fresh Avocados", "each", "0000000042294", 129, 4.2),
    Product("Baby Spinach", "5 oz", "0001111084821", 349, 2.5),
    Product("Broccoli Crowns", "1 lb", "0000000030808", 199, 2.4, weighted=True),
    Product("Red Bell Peppers", "1 lb", "0000000046839", 279, 1.8, weighted=True),
    Product("Yellow Onions", "3 lb", "0001111017302", 299, 2.1),
    Product("Fresh Blueberries", "1 pint", "0001111090044", 399, 1.7),
    Product("Lemons", "2 lb bag", "0001111042441", 429, 1.3),
    Product("Green Seedless Grapes", "1 lb", "0000000040229", 299, 1.4, weighted=True),
    Product("Valley Farm® Whole Milk", "1 gal", "0001111041604", 389, 6.5),
    Product("Meadow Lane® Large Eggs", "1 dozen", "0001111089017", 429, 5.0),
    Product("Simple Truth Organic Greek Yogurt", "32 oz", "0001111001820", 649, 2.1),
    Product("Harris Teeter Shredded Cheddar Cheese", "8 oz", "0007203671412", 399, 2.7),
    Product("Farmhouse® Salted Butter", "16 oz", "0001111084319", 529, 1.4),
    Product("Oat Valley® Oatmilk", "64 fl oz", "0003663207631", 499, 1.3),
    Product("Harris Teeter Sandwich Bread", "20 oz", "0007203670107", 299, 4.3),
    Product("Grain House® Whole Grain Bagels", "6 ct", "0002430016308", 449, 1.6),
    Product("Bakery Fresh Goodness Brioche Buns", "8 ct", "0001111095532", 499, 1.0),
    Product("Morning Mill® Toasted Oat Cereal", "18 oz", "0001600012751", 549, 2.0),
    Product("Simple Truth Organic Rolled Oats", "32 oz", "0001111080106", 429, 1.3),
    Product("Heritage Farm Boneless Chicken Breast", "1 lb", "0001111097238", 499, 3.8, weighted=True),
    Product("Fresh Atlantic Salmon Fillet", "1 lb", "0020818300000", 1099, 1.1, weighted=True),
    Product("Prairie Creek® Lean Ground Beef", "1 lb", "0001111060221", 649, 2.0),
    Product("Heritage Farm Turkey Bacon", "12 oz", "0001111083350", 499, 1.0),
    Product("Simple Truth Organic Black Beans", "15 oz", "0001111086207", 149, 2.0),
    Product("Riverside® Jasmine Rice", "5 lb", "0001740011283", 899, 1.1),
    Product("Old Mill® Penne Pasta", "16 oz", "0001111088133", 199, 1.7),
    Product("Garden Table® Tomato Basil Sauce", "24 oz", "0005100012215", 399, 1.5),
    Product("Simple Truth Organic Low Sodium Broth", "32 oz", "0001111087044", 329, 1.2),
    Product("Harvest Gold® Extra Virgin Olive Oil", "25.5 fl oz", "0004173601010", 1299, 0.7),
    Product("Harris Teeter Creamy Peanut Butter", "18 oz", "0007203673508", 349, 1.1),
    Product("Orchard Jar® Strawberry Jam", "18 oz", "0005150000066", 449, 0.8),
    Product("Golden Field® Honey", "12 oz", "0001111080090", 649, 0.6),
    Product("Stone Ridge® Sea Salt Crackers", "12 oz", "0004400003202", 399, 1.6),
    Product("Harris Teeter Sea Salt Potato Chips", "8 oz", "0007203671928", 349, 1.7),
    Product("Trail Day® Roasted Cashews", "8 oz", "0001111093385", 699, 0.9),
    Product("Orchard Kids® Fruit Snacks", "10 ct", "0001600014731", 399, 1.0),
    Product("Cocoa House® Dark Chocolate", "3.5 oz", "0003400025001", 429, 0.7),
    Product("Peak Roast® Ground Coffee", "12 oz", "0002550000329", 1099, 1.1),
    Product("River Spring® Sparkling Water", "8 pack", "0001200017178", 599, 1.3),
    Product("Citrus Grove® Orange Juice", "52 fl oz", "0002500004798", 549, 1.4),
    Product("Frozen Valley® Mixed Berries", "16 oz", "0001111083497", 499, 1.2),
    Product("Hearth Table® Frozen Pizza", "18 oz", "0007218063240", 699, 1.0),
    Product("Simple Truth Frozen Broccoli", "12 oz", "0001111086429", 249, 1.3),
    Product("Home Chef Prepared Chicken Alfredo", "12 oz", "0001111091309", 899, 0.8),
    Product("Deli Fresh Turkey Sandwich", "each", "0001111097023", 749, 0.5),
    Product("Green Kitchen® Salad Kit", "11 oz", "0007143000119", 449, 1.3),
    Product("Bright Home® Paper Towels", "6 rolls", "0003700037727", 1199, 0.6, taxable=True, snap_eligible=False),
    Product("Harris Teeter Trash Bags", "20 ct", "0007203678022", 899, 0.4, taxable=True, snap_eligible=False),
    Product("Clear Day® Dish Soap", "24 fl oz", "0003700097361", 499, 0.5, taxable=True, snap_eligible=False),
    Product("Fresh Mint® Toothpaste", "4.8 oz", "0003500055460", 499, 0.4, taxable=True, snap_eligible=False),
    Product("Daily Care® Shampoo", "12 fl oz", "0003700083048", 699, 0.3, taxable=True, snap_eligible=False),
    Product("Happy Paws® Dog Treats", "16 oz", "0002310010893", 799, 0.5, taxable=True, snap_eligible=False),
]


ESSENTIALS = {
    "0000000004011": 0.58,
    "0001111041604": 0.52,
    "0001111089017": 0.40,
    "0007203670107": 0.42,
    "0001111084821": 0.23,
}


def price_for(product: Product, purchase_date: date, rng: random.Random) -> tuple[int, int]:
    month_index = purchase_date.month - 1
    drift = 1 + month_index * rng.uniform(0.0015, 0.0045)
    regular = max(49, round((product.base_cents * drift + rng.choice([-20, -10, 0, 0, 0, 10, 20])) / 5) * 5)
    if rng.random() < (0.30 if product.selection_weight >= 2 else 0.20):
        discount = rng.choice([0.10, 0.15, 0.20, 0.25, 0.30])
        paid = max(39, round((regular * (1 - discount)) / 5) * 5)
    else:
        paid = regular
    return paid, regular


def weighted_quantity(product: Product, rng: random.Random) -> float:
    if "Bananas" in product.description:
        return round(rng.uniform(1.4, 3.4), 2)
    if "Chicken" in product.description:
        return round(rng.uniform(1.2, 3.0), 2)
    if "Salmon" in product.description:
        return round(rng.uniform(0.7, 1.8), 2)
    return round(rng.uniform(0.6, 2.2), 2)


def choose_products(target: int, rng: random.Random) -> list[Product]:
    selected: list[Product] = []
    selected_upcs: set[str] = set()
    by_upc = {product.upc: product for product in CATALOG}
    for upc, probability in ESSENTIALS.items():
        if rng.random() < probability:
            selected.append(by_upc[upc])
            selected_upcs.add(upc)
    remaining = [product for product in CATALOG if product.upc not in selected_upcs]
    while len(selected) < target and remaining:
        product = rng.choices(remaining, weights=[item.selection_weight for item in remaining], k=1)[0]
        selected.append(product)
        remaining.remove(product)
    rng.shuffle(selected)
    return selected


def purchase_dates(rng: random.Random) -> list[date]:
    dates = []
    current = date(2025, 1, 4)
    while current <= date(2025, 12, 28):
        dates.append(current)
        current += timedelta(days=rng.choices(
            [3, 4, 5, 6, 7, 8, 9, 10, 12],
            weights=[1, 2, 3, 5, 9, 6, 4, 2, 1],
            k=1,
        )[0])
    return dates


def generate(seed: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    orders: list[dict] = []
    items: list[dict] = []
    for receipt_number, purchase_date in enumerate(purchase_dates(rng), start=1):
        channel = rng.choices(["In-store", "Delivery", "Pickup"], weights=[0.68, 0.20, 0.12], k=1)[0]
        line_ranges = {"Delivery": (18, 31), "Pickup": (13, 24), "In-store": (7, 23)}
        products = choose_products(rng.randint(*line_ranges[channel]), rng)
        receipt_key = f"synthetic-{purchase_date.isoformat()}-{receipt_number:03d}"
        item_rows = []
        taxable_paid = 0

        for line_number, product in enumerate(products, start=1):
            paid_unit, regular_unit = price_for(product, purchase_date, rng)
            missed = channel != "In-store" and rng.random() < 0.045
            if product.weighted:
                ordered = weighted_quantity(product, rng)
                received = 0 if missed else ordered
            else:
                ordered = rng.choices([1, 2, 3], weights=[0.83, 0.15, 0.02], k=1)[0]
                received = 0 if missed else ordered
            paid_total = round(paid_unit * received) if received else 0
            original_total = round(regular_unit * received) if received else 0
            savings = original_total - paid_total
            if product.taxable:
                taxable_paid += paid_total
            item_rows.append({
                "account": "synthetic-household", "receipt_key": receipt_key,
                "purchase_date": purchase_date.isoformat(), "purchase_type": channel,
                "line_number": line_number, "description": product.description, "size": product.size,
                "upc": product.upc, "item_type": "NORMAL", "is_weighted": product.weighted,
                "unit_of_measure": "LB" if product.weighted else "EACH", "ordered": ordered,
                "received": received, "not_received": ordered if missed else 0,
                "substitutes": 1 if missed and rng.random() < 0.35 else 0, "refunded": 0,
                "unit_price_paid_cents": 0 if missed else paid_unit,
                "original_unit_price_cents": regular_unit, "paid_cents": paid_total,
                "original_total_cents": original_total, "savings_cents": savings,
                "snap_eligible": product.snap_eligible,
            })

        merchandise_paid = sum(row["paid_cents"] for row in item_rows)
        subtotal = sum(row["original_total_cents"] for row in item_rows)
        savings = sum(row["savings_cents"] for row in item_rows)
        tax = round(taxable_paid * 0.0725)
        if channel == "Delivery":
            fee_paid = rng.choice([0, 395, 495, 595])
            other_fee = rng.choices([0, 199, 299], weights=[0.7, 0.2, 0.1], k=1)[0]
            tip = round(merchandise_paid * rng.uniform(0.08, 0.14) / 25) * 25
        elif channel == "Pickup":
            fee_paid = rng.choices([0, 295], weights=[0.75, 0.25], k=1)[0]
            other_fee = tip = 0
        else:
            fee_paid = other_fee = tip = 0
        total = merchandise_paid + tax + fee_paid + other_fee + tip
        store = rng.choices(
            ["Example Market Central", "Example Market North", "Example Market West"],
            weights=[0.62, 0.28, 0.10], k=1,
        )[0]
        orders.append({
            "account": "synthetic-household", "receipt_key": receipt_key,
            "purchase_date": purchase_date.isoformat(), "purchase_type": channel, "store": store,
            "store_city": "Sample City", "store_state": "NC", "item_lines": len(item_rows),
            "item_quantity": round(sum(float(row["received"]) for row in item_rows), 2),
            "subtotal_cents": subtotal, "savings_cents": savings, "tax_cents": tax,
            "fee_paid_cents": fee_paid, "other_fee_cents": other_fee, "tip_cents": tip,
            "total_cents": total,
        })
        items.extend(item_rows)
    return orders, items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--orders", type=Path, default=ROOT / "examples" / "orders.json")
    parser.add_argument("--items", type=Path, default=ROOT / "examples" / "items.json")
    args = parser.parse_args()
    orders, items = generate(args.seed)
    args.orders.parent.mkdir(parents=True, exist_ok=True)
    args.items.parent.mkdir(parents=True, exist_ok=True)
    args.orders.write_text(json.dumps(orders, indent=2) + "\n")
    args.items.write_text(json.dumps(items, indent=2) + "\n")
    print(f"wrote {len(orders)} orders and {len(items)} item rows with seed {args.seed}")


if __name__ == "__main__":
    main()
