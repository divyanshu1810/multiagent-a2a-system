"""
Script to generate sample product and order data.
Run: python data/generate_data.py
"""
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

# ── Products ─────────────────────────────────────────────────────────────────
product_types = ["Electronics", "Home Appliances", "Menswear", "Womenswear", "Home Décor"]

brands = {
    "Electronics": ["Samsung", "Sony", "LG", "Apple", "Xiaomi", "OnePlus", "Dell", "HP", "Lenovo", "Bose"],
    "Home Appliances": ["Whirlpool", "IFB", "Bosch", "Philips", "Panasonic", "Havells", "Bajaj", "Voltas", "Blue Star", "Daikin"],
    "Menswear": ["Raymond", "Arrow", "Van Heusen", "Peter England", "Allen Solly", "Louis Philippe", "Wills Lifestyle", "Park Avenue", "Zara", "H&M"],
    "Womenswear": ["W", "Biba", "FabIndia", "Global Desi", "Aurelia", "Zara", "H&M", "AND", "Mango", "Vero Moda"],
    "Home Décor": ["Godrej Interio", "Nilkamal", "Durian", "Pepperfry", "Urban Ladder", "HomeTown", "Asian Paints", "Sleepwell", "Springwel", "Hettich"],
}

product_templates = {
    "Electronics": [
        ("Smartphone 5G", 15000, 45000),
        ("Laptop 15.6in", 45000, 90000),
        ("Wireless Earbuds", 3000, 12000),
        ("Smart TV 55in", 35000, 80000),
        ("Tablet 10in", 18000, 55000),
        ("Bluetooth Speaker", 2500, 8000),
        ("Smart Watch", 8000, 35000),
        ("Gaming Console", 35000, 55000),
        ("Webcam HD", 2000, 5000),
        ("DSLR Camera", 45000, 120000),
    ],
    "Home Appliances": [
        ("Refrigerator 350L", 25000, 55000),
        ("Washing Machine 8kg", 22000, 45000),
        ("Microwave Oven 25L", 8000, 18000),
        ("Air Conditioner 1.5T", 32000, 65000),
        ("Vacuum Cleaner", 5000, 18000),
        ("Induction Cooktop", 2500, 6000),
        ("Water Purifier", 8000, 20000),
        ("Ceiling Fan 1200mm", 1500, 4000),
        ("Air Purifier", 8000, 22000),
        ("Dishwasher 12 Place", 28000, 55000),
    ],
    "Menswear": [
        ("Formal Shirt", 800, 3500),
        ("Casual Polo Tee", 600, 2500),
        ("Business Suit", 8000, 25000),
        ("Denim Jeans", 1500, 5000),
        ("Chinos", 1200, 4000),
        ("Blazer", 4000, 15000),
        ("Ethnic Kurta", 1000, 4500),
        ("Sports Jogger", 800, 3000),
        ("Winter Jacket", 3000, 9000),
        ("Formal Trousers", 1200, 3500),
    ],
    "Womenswear": [
        ("Salwar Kameez", 1200, 5000),
        ("Saree", 2000, 15000),
        ("Lehenga Choli", 5000, 25000),
        ("Casual Kurti", 700, 2500),
        ("Western Dress", 1500, 6000),
        ("Palazzo Set", 1000, 3500),
        ("Anarkali Suit", 2500, 8000),
        ("Denim Shirt", 1000, 3000),
        ("Crop Top", 500, 2000),
        ("Formal Blazer", 3000, 10000),
    ],
    "Home Décor": [
        ("Sofa 3-Seater", 25000, 75000),
        ("Dining Table 6-Seater", 20000, 55000),
        ("Wardrobe 3-Door", 18000, 45000),
        ("Bed Frame Queen", 15000, 40000),
        ("Study Table", 5000, 15000),
        ("Bookshelf 5-Shelf", 6000, 18000),
        ("Wall Mirror", 2000, 8000),
        ("Floor Lamp", 3000, 10000),
        ("Decorative Vase", 800, 4000),
        ("Area Rug 6x9ft", 5000, 18000),
    ],
}

rows = []
prod_code_counter = 1000

for ptype, templates in product_templates.items():
    brand_list = brands[ptype]
    for name_base, price_min, price_max in templates:
        for brand in brand_list[:2]:  # 2 brands per template → 20 per type = 100 total
            prod_code = f"P{prod_code_counter}"
            prod_code_counter += 1
            unit_price = random.randint(price_min, price_max)
            qty = random.randint(5, 200)
            rows.append({
                "product_code": prod_code,
                "product_name": f"{brand} {name_base}",
                "product_type": ptype,
                "brand_name": brand,
                "unit_price": unit_price,
                "quantity_in_stock": qty,
            })

products_df = pd.DataFrame(rows)
products_df.to_csv("data/products.csv", index=False)
print(f"✅ Generated {len(products_df)} products → data/products.csv")

# ── Orders ───────────────────────────────────────────────────────────────────
product_codes = products_df["product_code"].tolist()
client_codes = [f"C{str(i).zfill(3)}" for i in range(1, 26)]

base_date = datetime(2024, 1, 1)
order_rows = []
seen = set()

while len(order_rows) < 50:
    pcode = random.choice(product_codes)
    ccode = random.choice(client_codes)
    days_offset = random.randint(0, 364)
    odate = (base_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
    key = (pcode, ccode, odate)
    if key in seen:
        continue
    seen.add(key)
    qty = random.randint(1, 20)
    order_rows.append({
        "product_code": pcode,
        "client_code": ccode,
        "order_date": odate,
        "quantity": qty,
    })

orders_df = pd.DataFrame(order_rows).sort_values("order_date").reset_index(drop=True)
orders_df.to_csv("data/orders.csv", index=False)
print(f"✅ Generated {len(orders_df)} orders → data/orders.csv")
