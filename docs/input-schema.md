# Normalized input schema

The analyzer reads two JSON arrays. Monetary values are integer cents.

## `orders.json`

Required fields: `receipt_key`, `purchase_date`, `purchase_type`, `item_lines`,
`subtotal_cents`, `savings_cents`, `tax_cents`, `fee_paid_cents`,
`other_fee_cents`, `tip_cents`, and `total_cents`.

`subtotal_cents` is the merchandise amount before provider-recorded savings.
`total_cents` is the captured receipt total. Dates use ISO `YYYY-MM-DD`.

## `items.json`

Required fields: `receipt_key`, `purchase_date`, `purchase_type`, `description`,
`size`, `upc`, `is_weighted`, `received`, `paid_cents`, `savings_cents`,
`unit_price_paid_cents`, and `original_unit_price_cents`.

Rows with zero `received` and zero `paid_cents` are retained in the raw export
but excluded from purchase-incidence analysis. Missing descriptions remain
visible as `Unknown`. UPC-level price change requires at least three purchase
dates spanning 60 days.
