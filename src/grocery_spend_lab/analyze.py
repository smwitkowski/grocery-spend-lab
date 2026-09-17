#!/usr/bin/env python3
"""Analyze normalized grocery receipt exports and create reusable datasets/charts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from . import __version__
from .validation import SCHEMA_VERSION, validate_inputs

PALETTE = {
    "navy": "#17324D", "blue": "#4178A6", "sky": "#A9C9DE", "teal": "#3B8C88",
    "gold": "#D6A84B", "coral": "#D7745F", "gray": "#7A8793", "light": "#EAF0F4",
    "ink": "#18232E", "green": "#5B8E55",
}

CATEGORY_RULES = [
    ("Baby", r"\b(diapers?|pull[- ]?ups?|baby food|infant|toddler pouch|training pants|baby wipes|waterwipes)\b"),
    ("Household", r"\b(paper towel|bath tissue|toilet paper|trash bags?|storage bags?|aluminum foil|dish soap|detergent|cleaner|bleach|sponges?|napkins?|facial tissues?|disinfect|laundry|air freshener|light bulb|measuring cups?|measuring spoons?|rolling pin|sifter|plastic cups?|dinner forks?|tape|sprayer|cookware|kitchen)\b"),
    ("Personal care and health", r"\b(shampoo|conditioner|body wash|toothpaste|toothbrush|deodorant|vitamin|supplement|medicine|pain relie|bandage|lotion|soap|razor|tampon|pad|sunscreen|aspirin|tylenol|acetaminophen|preparation h|cleansing water|makeup remover|rx )\b"),
    ("Pet", r"\b(dog|cat|pet|kibble|rawhide|canine|feline)\b"),
    ("Beverages", r"\b(soda|ginger ale|sparkling (?:water|mineral)|mineral water|spring water|gallon water|water bottle|juice|lemonade|coffee|tea|drink mix|electrolyte|hydration multiplier|kombucha|prebiotic soda|energy drink|sports drink)\b"),
    ("Alcohol", r"\b(beer|wine|lager|ale|cabernet|chardonnay|pinot|merlot|sauvignon|prosecco|hard seltzer)\b"),
    ("Frozen", r"\b(frozen|ice cream|popsicle|pizza|taquito|mozzarella sticks|waffles?|french fries|tater tots)\b"),
    ("Prepared and convenience", r"\b(ravioli|tortelloni|tortellini|ready[- ]to[- ]eat|meal kit|rotisserie|deli |prepared|microwave|macaroni.*cheese|chicken salad|sushi|sandwich|lunchable)\b"),
    ("Meat and seafood", r"\b(chicken|turkey|beef|pork|salmon|shrimp|tilapia|steak|sausage|bacon|ham|tuna|cod|meatballs?|ground meat|lamb|seafood)\b"),
    ("Dairy and eggs", r"\b(milk|cheese|yogurt|yoghurt|eggs?|butter|cream cheese|sour cream|heavy cream|whipping cream|crème fraîche|creme fraiche|cottage cheese|half & half|half and half|creamer)\b"),
    ("Produce", r"\b(apples?|bananas?|oranges?|mandarins?|clementines?|berries|strawberr(?:y|ies)|blueberr(?:y|ies)|raspberr(?:y|ies)|blackberr(?:y|ies)|grapes?|cherr(?:y|ies)|melons?|cantaloupe|watermelon|pineapple|mango|peach(?:es)?|pears?|avocados?|tomatoes?|lettuce|spinach|kale|broccoli|carrots?|peppers?|onions?|potatoes|cucumber|zucchini|squash|celery|mushrooms?|asparagus|corn|green beans?|salad kit|arugula|brussels sprouts|cauliflower|cilantro|parsley|mint|shallots?|garlic|lemons?|limes?|produce)\b"),
    ("Bread and bakery", r"\b(bread|buns?|rolls?|bagels?|tortillas?|croissant|muffins?|donuts?|doughnuts?|bakery|cakes?|cupcakes?|cheesecake|brioche|pita|naan|english muffins?)\b"),
    ("Breakfast and cereal", r"\b(cereal|granola|oatmeal|rolled oats|steel cut oats|pancake|breakfast bar)\b"),
    ("Snacks and sweets", r"\b(chips|crackers?|cookies?|candy|chocolate|granola bars?|fruit snacks?|applesauce|pretzels?|popcorn|veggie straws|snacks?|gummy|brownie|dessert|yoggies|cashews?|pistachios?|nuts?|walnuts?)\b"),
    ("Pantry and cooking", r"\b(pasta|rice|quinoa|flour|sugar|oil|vinegar|sauce|broth|bouillon|beans|lentil|seasoning|spice|salt|pepper|peanut butter|peanut powder|jelly|jam|syrup|canned|soup|mustard|ketchup|mayonnaise|dressing|vinaigrette|pesto|breadcrumbs|baking|yeast|honey|oats|guacamole|salsa|hummus|curry paste|ginger paste|chili crunch|sumac|dill|chives|flaxseed|chia seeds?|fennel|thyme|coriander|cumin|taco shells?|wonton strips?)\b"),
]

PRIVATE_LABEL = re.compile(
    r"^(harris teeter|simple truth|private selection|kroger|smart way|ht traders|heritage farm|comforts|home chef|bakery fresh goodness)\b",
    re.I,
)


def classify_category(description: str | None) -> str:
    if description is None or pd.isna(description) or not str(description).strip():
        return "Unknown"
    text = str(description).lower()
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text, re.I):
            return category
    return "Other grocery"


def classify_brand(description: str | None, is_weighted: bool) -> str:
    if description is None or pd.isna(description) or not str(description).strip():
        return "Unknown"
    description = str(description)
    if PRIVATE_LABEL.search(description):
        return "Retailer owned"
    if "®" in description or "™" in description:
        return "Other branded"
    if is_weighted or re.match(r"^(fresh|bulk|seedless|yellow|red|green|organic fresh)\b", description, re.I):
        return "Unbranded or fresh"
    return "Brand unclear"


def attributes(description: str | None) -> list[str]:
    if description is None or pd.isna(description) or not str(description).strip():
        return []
    text = str(description).lower()
    tags = []
    if "organic" in text:
        tags.append("Organic")
    if re.search(r"\b(gluten[- ]free|zero sugar|no sugar|keto|plant[- ]based|vegan|dairy[- ]free|lactose[- ]free|low sodium|whole grain)\b", text):
        tags.append("Explicit diet or nutrition claim")
    if re.search(r"\b(premium|artisan|gourmet|imported|private selection)\b", text):
        tags.append("Premium or specialty wording")
    if re.search(r"\b(frozen|ready[- ]to[- ]eat|meal kit|microwave|pre[- ]cut|shredded|snack|pouch|single serve|prepared)\b", text):
        tags.append("Convenience format")
    return tags


def recover_descriptions(items: pd.DataFrame) -> pd.DataFrame:
    items = items.copy()
    known = items.dropna(subset=["description", "upc"])
    lookup = {}
    for upc, group in known.groupby("upc"):
        descriptions = group["description"].dropna().astype(str)
        if len(descriptions):
            lookup[str(upc)] = Counter(descriptions).most_common(1)[0][0]
    missing = items["description"].isna() & items["upc"].notna()
    items.loc[missing, "description"] = items.loc[missing, "upc"].astype(str).map(lookup)
    items["description_recovered"] = missing & items["description"].notna()
    return items


def parse_milk_gallons(row) -> float | None:
    size = str(row.get("size") or "").lower()
    quantity = float(row.get("received") or 0)
    patterns = [(r"([\d.]+)\s*gal", 1.0), (r"([\d.]+)\s*fl\s*oz", 1 / 128),
                (r"([\d.]+)\s*qt", 1 / 4), (r"([\d.]+)\s*pt", 1 / 8)]
    for pattern, factor in patterns:
        match = re.search(pattern, size)
        if match:
            return float(match.group(1)) * factor * quantity
    return None


def parse_egg_dozens(row) -> float | None:
    size = str(row.get("size") or "").lower()
    quantity = float(row.get("received") or 0)
    if "dozen" in size:
        match = re.search(r"([\d.]+)\s*dozen", size)
        return (float(match.group(1)) if match else 1.0) * quantity
    match = re.search(r"(\d+)\s*ct", size)
    return float(match.group(1)) / 12 * quantity if match else None


def add_price_bands(items: pd.DataFrame) -> pd.DataFrame:
    items = items.copy()
    items["package_price_band"] = "Not comparable"
    eligible = items[(~items["is_weighted"]) & (items["unit_price_paid_cents"] > 0)]
    for category, group in eligible.groupby("category"):
        if len(group) < 12 or group["unit_price_paid_cents"].nunique() < 3:
            continue
        ranks = group["unit_price_paid_cents"].rank(pct=True, method="average")
        labels = pd.cut(ranks, bins=[0, 1/3, 2/3, 1], labels=["Lower third", "Middle third", "Upper third"], include_lowest=True)
        items.loc[group.index, "package_price_band"] = labels.astype(str)
    return items


def style_axes(ax, title=None, subtitle=None):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", color="#DCE3E8", linewidth=0.7)
    ax.tick_params(colors=PALETTE["ink"], labelsize=9)
    if title:
        ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=PALETTE["ink"], pad=16)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=PALETTE["gray"], va="bottom")


def savefig(path: Path, rect=None):
    plt.tight_layout(rect=rect)
    plt.savefig(path, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close()


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--merchant", default="Grocery retailer")
    parser.add_argument("--account-label", default="signed-in account")
    parser.add_argument("--receipt-links-indexed", type=int)
    parser.add_argument("--event-date", type=pd.Timestamp)
    parser.add_argument("--event-label", default="Event")
    args = parser.parse_args(argv)
    validation = validate_inputs(args.orders, args.items)
    if not validation["valid"]:
        failure = {"schema_version": SCHEMA_VERSION, "tool_version": __version__, "command": "analyze",
                   "status": "failed", "data": None, "warnings": validation["warnings"], "artifacts": [],
                   "error": {"code": "INVALID_INPUT", "message": "Input validation failed.",
                             "details": validation["errors"]}}
        print(json.dumps(failure))
        raise SystemExit(3)
    requested_output = args.output.resolve()
    if requested_output.exists():
        failure = {"schema_version": SCHEMA_VERSION, "tool_version": __version__, "command": "analyze",
                   "status": "failed", "data": None, "warnings": [], "artifacts": [],
                   "error": {"code": "OUTPUT_CONFLICT", "message": f"Output already exists: {requested_output}", "details": []}}
        print(json.dumps(failure))
        raise SystemExit(5)
    validation_warnings = [{"code": "INPUT_WARNING", "message": message} for message in validation["warnings"]]
    requested_output.parent.mkdir(parents=True, exist_ok=True)
    args.output = Path(tempfile.mkdtemp(prefix=f".{requested_output.name}.tmp-", dir=requested_output.parent))
    data_dir = args.output / "data"
    chart_dir = args.output / "charts"
    data_dir.mkdir(parents=True)
    chart_dir.mkdir()

    orders = pd.read_json(args.orders)
    items = pd.read_json(args.items)
    orders["purchase_date"] = pd.to_datetime(orders["purchase_date"])
    items["purchase_date"] = pd.to_datetime(items["purchase_date"])
    for frame in (orders, items):
        frame["month"] = frame["purchase_date"].dt.to_period("M").astype(str)
    orders["net_merchandise_cents"] = orders["subtotal_cents"].fillna(0) - orders["savings_cents"].fillna(0)
    orders["convenience_cents"] = orders[["fee_paid_cents", "other_fee_cents", "tip_cents"]].fillna(0).sum(axis=1)
    orders["equation_residual_cents"] = orders["total_cents"] - (
        orders["net_merchandise_cents"] + orders["tax_cents"].fillna(0) + orders["convenience_cents"]
    )

    items = recover_descriptions(items)
    items["fulfilled"] = (items["received"].fillna(0) > 0) | (items["paid_cents"].fillna(0) > 0)
    purchased = items[items["fulfilled"]].copy()
    purchased["category"] = [classify_category(v) for v in purchased["description"]]
    purchased["brand_type"] = [classify_brand(d, bool(w)) for d, w in zip(purchased["description"], purchased["is_weighted"])]
    purchased["attributes"] = [attributes(v) for v in purchased["description"]]
    purchased["marked_down"] = purchased["savings_cents"].fillna(0) > 0
    purchased["original_spend_cents"] = purchased["paid_cents"].fillna(0) + purchased["savings_cents"].fillna(0)
    purchased = add_price_bands(purchased)

    item_sums = purchased.groupby("receipt_key")["paid_cents"].sum().rename("item_paid_cents")
    orders = orders.merge(item_sums, on="receipt_key", how="left")
    orders["item_merchandise_residual_cents"] = orders["item_paid_cents"].fillna(0) - orders["net_merchandise_cents"]

    category = purchased.groupby("category").agg(
        paid_cents=("paid_cents", "sum"), savings_cents=("savings_cents", "sum"),
        item_lines=("receipt_key", "size"), unique_upcs=("upc", "nunique"),
        baskets=("receipt_key", "nunique"), marked_lines=("marked_down", "sum"),
    ).reset_index()
    category["spend_share"] = category["paid_cents"] / category["paid_cents"].sum()
    category["marked_line_rate"] = category["marked_lines"] / category["item_lines"]
    category["basket_penetration"] = category["baskets"] / orders["receipt_key"].nunique()
    category = category.sort_values("paid_cents", ascending=False)

    monthly_orders = orders.groupby("month").agg(
        receipts=("receipt_key", "nunique"), total_cents=("total_cents", "sum"),
        net_merchandise_cents=("net_merchandise_cents", "sum"), tax_cents=("tax_cents", "sum"),
        convenience_cents=("convenience_cents", "sum"), savings_cents=("savings_cents", "sum"),
        median_basket_cents=("total_cents", "median"), item_lines=("item_lines", "sum"),
    ).reset_index()
    monthly_items = purchased.groupby("month").agg(
        fulfilled_lines=("receipt_key", "size"), unique_upcs=("upc", "nunique"),
        marked_line_rate=("marked_down", "mean"), paid_item_cents=("paid_cents", "sum"),
    ).reset_index()
    monthly = monthly_orders.merge(monthly_items, on="month", how="left")

    channel = orders.groupby("purchase_type").agg(
        receipts=("receipt_key", "nunique"), total_cents=("total_cents", "sum"),
        merchandise_cents=("net_merchandise_cents", "sum"), convenience_cents=("convenience_cents", "sum"),
        fees_cents=("fee_paid_cents", "sum"), tips_cents=("tip_cents", "sum"),
        median_total_cents=("total_cents", "median"), median_item_lines=("item_lines", "median"),
    ).reset_index()
    channel["convenience_per_order_cents"] = channel["convenience_cents"] / channel["receipts"]

    brand = purchased.groupby("brand_type").agg(
        paid_cents=("paid_cents", "sum"), item_lines=("receipt_key", "size"), unique_upcs=("upc", "nunique")
    ).reset_index().sort_values("paid_cents", ascending=False)
    brand["spend_share"] = brand["paid_cents"] / brand["paid_cents"].sum()

    attribute_rows = []
    for _, row in purchased.iterrows():
        for tag in row["attributes"]:
            attribute_rows.append({"attribute": tag, "paid_cents": row["paid_cents"], "receipt_key": row["receipt_key"], "upc": row["upc"]})
    attr_df = pd.DataFrame(attribute_rows)
    if len(attr_df):
        attr_summary = attr_df.groupby("attribute").agg(
            paid_cents=("paid_cents", "sum"), item_lines=("receipt_key", "size"), baskets=("receipt_key", "nunique")
        ).reset_index().sort_values("paid_cents", ascending=False)
    else:
        attr_summary = pd.DataFrame(columns=["attribute", "paid_cents", "item_lines", "baskets"])

    # Explicit staple definitions avoid matching yogurt, cheese, egg rolls, or prepared egg foods.
    desc = purchased["description"].fillna("")
    milk = purchased[
        desc.str.contains(r"\b(?:milk|almondmilk|oatmilk)\b", case=False, regex=True)
        & ~desc.str.contains(r"(?:milk chocolate|yogurt|cheese|creamer|waffle|bread|powder)", case=False, regex=True)
    ].copy()
    eggs = purchased[
        desc.str.contains(r"\beggs?\b", case=False, regex=True)
        & ~desc.str.contains(r"(?:egg roll|noodle|waffle|sandwich|bite|salad|plant[- ]based)", case=False, regex=True)
    ].copy()
    milk["staple"] = "Fluid milk"
    milk["standard_quantity"] = milk.apply(parse_milk_gallons, axis=1)
    milk["standard_unit"] = "gallons"
    eggs["staple"] = "Shell eggs"
    eggs["standard_quantity"] = eggs.apply(parse_egg_dozens, axis=1)
    eggs["standard_unit"] = "dozens"
    staples = pd.concat([milk, eggs], ignore_index=True)
    staples = staples[["purchase_date", "receipt_key", "staple", "description", "size", "received", "standard_quantity", "standard_unit", "paid_cents", "unit_price_paid_cents", "marked_down", "upc"]]

    price_rows = []
    for upc, group in purchased[purchased["upc"].notna() & (purchased["unit_price_paid_cents"] > 0)].groupby("upc"):
        group = group.sort_values("purchase_date")
        dates = group["purchase_date"].drop_duplicates()
        span = (dates.max() - dates.min()).days if len(dates) else 0
        if len(dates) < 3 or span < 60:
            continue
        regular = group[group["original_unit_price_cents"].notna()]
        first_regular = regular.iloc[0]["original_unit_price_cents"] if len(regular) else np.nan
        last_regular = regular.iloc[-1]["original_unit_price_cents"] if len(regular) else np.nan
        regular_change = (last_regular / first_regular - 1) if first_regular and not pd.isna(first_regular) else np.nan
        x = (group["purchase_date"] - group["purchase_date"].min()).dt.days.to_numpy()
        y = group["unit_price_paid_cents"].to_numpy()
        slope_30 = float(np.polyfit(x, y, 1)[0] * 30) if len(np.unique(x)) > 1 else 0
        price_rows.append({
            "upc": upc, "description": Counter(group["description"].dropna()).most_common(1)[0][0] if group["description"].notna().any() else None,
            "size": Counter(group["size"].dropna()).most_common(1)[0][0] if group["size"].notna().any() else None,
            "observations": len(group), "purchase_dates": len(dates), "span_days": span,
            "first_paid_cents": int(group.iloc[0]["unit_price_paid_cents"]), "last_paid_cents": int(group.iloc[-1]["unit_price_paid_cents"]),
            "min_paid_cents": int(group["unit_price_paid_cents"].min()), "max_paid_cents": int(group["unit_price_paid_cents"].max()),
            "first_regular_cents": None if pd.isna(first_regular) else int(first_regular),
            "last_regular_cents": None if pd.isna(last_regular) else int(last_regular),
            "regular_price_change": None if pd.isna(regular_change) else regular_change,
            "paid_price_slope_30d_cents": slope_30, "marked_observations": int(group["marked_down"].sum()),
        })
    price_trends = pd.DataFrame(price_rows).sort_values(["observations", "span_days"], ascending=False) if price_rows else pd.DataFrame()

    windows = []
    if args.event_date is not None:
        before_start = args.event_date - pd.Timedelta(days=76)
        before_end = args.event_date - pd.Timedelta(days=1)
        after_start = args.event_date
        after_end = args.event_date + pd.Timedelta(days=75)
        window_specs = [
            (f"Before {args.event_label}", before_start, before_end),
            (f"After {args.event_label}", after_start, after_end),
        ]
    else:
        window_specs = []
    for name, start, end in window_specs:
        subset = orders[(orders["purchase_date"] >= start) & (orders["purchase_date"] <= end)]
        keys = set(subset["receipt_key"])
        lines = purchased[purchased["receipt_key"].isin(keys)]
        windows.append({
            "window": name, "start": start.date().isoformat(), "end": end.date().isoformat(), "receipts": len(subset),
            "captured_total_cents": int(subset["total_cents"].sum()),
            "median_basket_cents": float(subset["total_cents"].median()) if len(subset) else None,
            "median_item_lines": float(subset["item_lines"].median()) if len(subset) else None,
            "unique_upcs": int(lines["upc"].nunique()), "delivery_share": float((subset["purchase_type"] == "Delivery").mean()) if len(subset) else None,
            "marked_line_rate": float(lines["marked_down"].mean()) if len(lines) else None,
        })
    windows_df = pd.DataFrame(windows)

    exceptions = orders[(orders["item_merchandise_residual_cents"].abs() > 1) | (orders["equation_residual_cents"].abs() > 1)][[
        "receipt_key", "purchase_date", "purchase_type", "total_cents", "item_merchandise_residual_cents", "equation_residual_cents"
    ]].sort_values("purchase_date")

    top_products = purchased.groupby(["upc", "description", "size"], dropna=False).agg(
        paid_cents=("paid_cents", "sum"), savings_cents=("savings_cents", "sum"),
        item_lines=("receipt_key", "size"), baskets=("receipt_key", "nunique"), received=("received", "sum")
    ).reset_index().sort_values("paid_cents", ascending=False)

    # Save analysis datasets.
    outputs = {
        "orders_enriched": orders, "items_classified": purchased, "category_summary": category,
        "monthly_summary": monthly, "channel_summary": channel, "brand_summary": brand,
        "attribute_summary": attr_summary, "staples": staples, "price_trends": price_trends,
        "pattern_windows": windows_df, "reconciliation_exceptions": exceptions, "top_products": top_products,
    }
    for name, frame in outputs.items():
        copy = frame.copy()
        for col in copy.columns:
            if len(copy) and isinstance(copy.iloc[0][col], list):
                copy[col] = copy[col].map(lambda x: "|".join(x))
        copy.to_csv(data_dir / f"{name}.csv", index=False)

    sns.set_theme(style="whitegrid", font_scale=0.95)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.labelcolor": PALETTE["ink"], "text.color": PALETTE["ink"]})

    # Monthly composition.
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    x = np.arange(len(monthly))
    bottom = np.zeros(len(monthly))
    for col, label, color in [("net_merchandise_cents", "Merchandise after recorded savings", PALETTE["navy"]),
                              ("tax_cents", "Tax", PALETTE["sky"]), ("convenience_cents", "Fees and tips", PALETTE["gold"])]:
        values = monthly[col].fillna(0).to_numpy() / 100
        ax.bar(x, values, bottom=bottom, label=label, color=color, width=0.68)
        bottom += values
    for i, (total, receipts) in enumerate(zip(bottom, monthly["receipts"])):
        ax.text(i, total + max(bottom) * .025, f"{receipts} receipts", ha="center", fontsize=8, color=PALETTE["gray"])
    ax.set_xticks(x, [pd.Period(v).strftime("%b") for v in monthly["month"]])
    ax.set_ylabel("Captured dollars")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.14))
    style_axes(ax, "Captured spending by month", "January and September are partial; February has one receipt")
    savefig(chart_dir / "01_monthly_spending.png")

    # Category spend.
    cat_plot = category.head(12).sort_values("paid_cents")
    fig, ax = plt.subplots(figsize=(8.8, 5.5))
    bars = ax.barh(cat_plot["category"], cat_plot["paid_cents"] / 100, color=PALETTE["blue"])
    for bar, share in zip(bars, cat_plot["spend_share"]):
        ax.text(bar.get_width() + category["paid_cents"].max()/100*.012, bar.get_y()+bar.get_height()/2, f"{share:.0%}", va="center", fontsize=9)
    ax.set_xlabel("Fulfilled-line spending")
    ax.xaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    style_axes(ax, "Where item spending went", "Rule-based categories; percentages are shares of classified fulfilled-line spending")
    savefig(chart_dir / "02_category_spending.png")

    # Brand and attributes.
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.7))
    b = brand.sort_values("paid_cents")
    axes[0].barh(b["brand_type"], b["paid_cents"] / 100, color=PALETTE["teal"])
    axes[0].xaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    axes[0].set_xlabel("Item spending")
    style_axes(axes[0], "Brand identification")
    if len(attr_summary):
        a = attr_summary.sort_values("paid_cents")
        axes[1].barh(a["attribute"], a["paid_cents"] / 100, color=PALETTE["gold"])
        axes[1].xaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
        axes[1].set_xlabel("Overlapping item spending")
    style_axes(axes[1], "Explicit product signals", "Tags overlap and describe labels, not objective quality")
    savefig(chart_dir / "03_brand_and_attributes.png")

    # Discount incidence by category.
    disc = category[category["item_lines"] >= 10].sort_values("marked_line_rate").tail(12)
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    bars = ax.barh(disc["category"], disc["marked_line_rate"] * 100, color=PALETTE["coral"])
    for bar, n in zip(bars, disc["item_lines"]):
        ax.text(bar.get_width() + .7, bar.get_y()+bar.get_height()/2, f"n={n}", va="center", fontsize=8, color=PALETTE["gray"])
    ax.set_xlabel("Fulfilled lines with provider-recorded savings")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    style_axes(ax, "How often purchased lines were marked down", "Incidence only; this does not measure deal quality or market competitiveness")
    savefig(chart_dir / "04_discount_incidence.png")

    # Shopping timeline.
    fig, ax = plt.subplots(figsize=(10.2, 4.4))
    channel_colors = {"In-store": PALETTE["blue"], "Delivery": PALETTE["gold"], "Pickup": PALETTE["teal"]}
    for channel_name, group in orders.groupby("purchase_type"):
        ax.scatter(group["purchase_date"], group["total_cents"] / 100,
                   s=30 + group["item_lines"].fillna(0) * 2.2, alpha=.78,
                   label=channel_name, color=channel_colors.get(channel_name, PALETTE["gray"]), edgecolor="white", linewidth=.7)
    if args.event_date is not None:
        ax.axvline(args.event_date, color=PALETTE["coral"], linestyle="--", linewidth=1)
        ax.text(args.event_date, ax.get_ylim()[1]*.94, args.event_label, color=PALETTE["coral"], fontsize=8, ha="right")
    ax.set_ylabel("Receipt total")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    style_axes(ax, "Shopping cadence and basket size", "Bubble area reflects receipt line count")
    savefig(chart_dir / "05_shopping_timeline.png")

    # Basket comparisons.
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.5))
    order_plot = orders[orders["purchase_type"].isin(["In-store", "Delivery"])]
    sns.boxplot(data=order_plot, x="purchase_type", y=order_plot["total_cents"] / 100, ax=axes[0], color=PALETTE["sky"], width=.5, showfliers=False)
    sns.stripplot(data=order_plot, x="purchase_type", y=order_plot["total_cents"] / 100, ax=axes[0], color=PALETTE["navy"], alpha=.65, size=4)
    axes[0].set(xlabel="", ylabel="Receipt total")
    axes[0].yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    style_axes(axes[0], "Receipt dollars")
    sns.boxplot(data=order_plot, x="purchase_type", y="item_lines", ax=axes[1], color=PALETTE["sky"], width=.5, showfliers=False)
    sns.stripplot(data=order_plot, x="purchase_type", y="item_lines", ax=axes[1], color=PALETTE["navy"], alpha=.65, size=4)
    axes[1].set(xlabel="", ylabel="Receipt lines")
    style_axes(axes[1], "Basket line count")
    fig.suptitle("Delivery and in-store baskets have different shapes", x=.06, ha="left", fontsize=15, fontweight="bold")
    savefig(chart_dir / "06_basket_by_channel.png")

    # Staples timeline.
    fig, axes = plt.subplots(2, 1, figsize=(10.0, 5.6), sharex=True)
    for ax, staple, color in zip(axes, ["Fluid milk", "Shell eggs"], [PALETTE["blue"], PALETTE["gold"]]):
        sub = staples[staples["staple"] == staple].sort_values("purchase_date")
        known = sub[sub["standard_quantity"].notna()]
        ax.bar(known["purchase_date"], known["standard_quantity"], width=3, color=color, alpha=.85)
        ax.scatter(sub["purchase_date"], np.zeros(len(sub)), marker="|", s=90, color=PALETTE["ink"])
        ax.set_ylabel("Gallons" if staple == "Fluid milk" else "Dozens")
        style_axes(ax, staple, "Black ticks show purchases with unstandardized package sizes" if staple == "Fluid milk" else None)
    savefig(chart_dir / "07_staples_timeline.png")

    # Repeat-price small multiples.
    selected = price_trends.head(6)["upc"].tolist() if len(price_trends) else []
    fig, axes = plt.subplots(3, 2, figsize=(10.2, 8.2), sharex=False)
    for ax, upc in zip(axes.flat, selected):
        sub = purchased[purchased["upc"] == upc].sort_values("purchase_date")
        ax.plot(sub["purchase_date"], sub["unit_price_paid_cents"] / 100, color=PALETTE["blue"], linewidth=1.4)
        ax.scatter(sub["purchase_date"], sub["unit_price_paid_cents"] / 100,
                   c=np.where(sub["marked_down"], PALETTE["coral"], PALETTE["navy"]), s=30, zorder=3)
        label = Counter(sub["description"].dropna()).most_common(1)[0][0] if sub["description"].notna().any() else upc
        ax.set_title(label[:48] + ("…" if len(label) > 48 else ""), fontsize=9, loc="left", fontweight="bold")
        ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.2f}")
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
        ax.grid(axis="y", color="#DCE3E8", linewidth=.6)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes.flat[len(selected):]:
        ax.axis("off")
    fig.suptitle("Observed prices for frequently repeated exact UPCs", x=.06, y=.995, ha="left", fontsize=15, fontweight="bold")
    fig.text(.06, .952, "Coral points had provider-recorded savings; movements are selected paid prices, not an inflation index", fontsize=9, color=PALETTE["gray"])
    savefig(chart_dir / "08_repeat_item_prices.png", rect=(0, 0, 1, .90))

    missing_before = int(items["description"].isna().sum() + items["description_recovered"].sum())
    missing_after = int(items["description"].isna().sum())
    fulfilled_total = len(purchased)
    item_spend = int(purchased["paid_cents"].fillna(0).sum())
    described_spend = int(purchased.loc[purchased["description"].notna(), "paid_cents"].fillna(0).sum())
    summary = {
        "scope": {"start": orders["purchase_date"].min().date().isoformat(), "end": orders["purchase_date"].max().date().isoformat(),
                  "receipts": int(len(orders)), "receipt_links_indexed": args.receipt_links_indexed,
                  "merchant": args.merchant, "account": args.account_label},
        "totals": {"captured_total_cents": int(orders["total_cents"].sum()), "net_merchandise_cents": int(orders["net_merchandise_cents"].sum()),
                   "tax_cents": int(orders["tax_cents"].fillna(0).sum()), "convenience_cents": int(orders["convenience_cents"].sum()),
                   "recorded_savings_cents": int(orders["savings_cents"].fillna(0).sum())},
        "lines": {"raw_lines": int(len(items)), "fulfilled_lines": fulfilled_total, "zero_received_lines": int((~items["fulfilled"]).sum()),
                  "missing_descriptions_before_recovery": missing_before, "missing_descriptions_after_recovery": missing_after,
                  "description_spend_coverage": described_spend / item_spend if item_spend else None, "weighted_lines": int(purchased["is_weighted"].sum())},
        "channels": {row["purchase_type"]: int(row["receipts"]) for _, row in channel.iterrows()},
        "discounts": {"marked_line_rate": float(purchased["marked_down"].mean()),
                      "baskets_with_markdown_rate": float(purchased.groupby("receipt_key")["marked_down"].any().mean()),
                      "marked_spend_share": float(purchased.loc[purchased["marked_down"], "paid_cents"].sum() / item_spend),
                      "recorded_line_savings_cents": int(purchased["savings_cents"].sum())},
        "brand": {row["brand_type"]: {"spend_cents": int(row["paid_cents"]), "spend_share": float(row["spend_share"])} for _, row in brand.iterrows()},
        "staples": {"milk_purchase_events": int(milk["receipt_key"].nunique()), "egg_purchase_events": int(eggs["receipt_key"].nunique()),
                    "milk_standardized_gallons": float(milk["standard_quantity"].sum()), "egg_standardized_dozens": float(eggs["standard_quantity"].sum())},
        "reconciliation": {"exception_receipts": int(len(exceptions)), "order_equation_exceptions": int((orders["equation_residual_cents"].abs() > 1).sum()),
                           "item_merchandise_exceptions": int((orders["item_merchandise_residual_cents"].abs() > 1).sum())},
        "methodology": {
            "price_tier": "Within-category package-price thirds for nonweighted lines; not a market price or quality rating.",
            "quality": "Only explicit product wording and attributes are measured; no objective quality score is assigned.",
            "change": "Equal windows are descriptive and confounded by channel, store, season, selection, and incomplete household coverage.",
        },
    }
    (args.output / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "README.md").write_text(
        f"# {args.merchant} grocery analysis data\n\n"
        f"Generated from {args.account_label}. `data/` contains auditable derived tables and `charts/` contains report-ready figures. "
        "The analysis excludes zero-received lines from purchase incidence and retains unknown categories/descriptions. See `analysis_summary.json` for coverage and limitations.\n"
    )
    artifact_paths = sorted(path for path in args.output.rglob("*") if path.is_file())
    artifacts = []
    for path in artifact_paths:
        relative = str(path.relative_to(args.output))
        media_type = "image/png" if path.suffix == ".png" else "text/csv" if path.suffix == ".csv" else "application/json" if path.suffix == ".json" else "text/markdown"
        role = "summary" if relative == "analysis_summary.json" else "chart" if path.suffix == ".png" else "data" if path.suffix == ".csv" else "documentation"
        artifacts.append({"role": role, "path": relative, "media_type": media_type,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    warnings = validation_warnings
    if len(exceptions):
        warnings.append({"code": "RECONCILIATION_RESIDUAL", "count": len(exceptions),
                         "details_artifact": "data/reconciliation_exceptions.csv"})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "command": "analyze",
        "status": "completed_with_warnings" if warnings else "completed",
        "data": {"output": str(requested_output), "receipts": len(orders), "fulfilled_lines": fulfilled_total,
                 "charts": 8, "reconciliation_exceptions": len(exceptions)},
        "inputs": {
            "orders": {"path": str(args.orders), "sha256": hashlib.sha256(args.orders.read_bytes()).hexdigest()},
            "items": {"path": str(args.items), "sha256": hashlib.sha256(args.items.read_bytes()).hexdigest()},
        },
        "options": {"merchant": args.merchant, "account_label": args.account_label,
                    "event_date": args.event_date.date().isoformat() if args.event_date is not None else None,
                    "event_label": args.event_label if args.event_date is not None else None},
        "warnings": warnings,
        "artifacts": artifacts,
        "error": None,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    args.output.replace(requested_output)
    print(json.dumps(manifest, allow_nan=False))


if __name__ == "__main__":
    main()
