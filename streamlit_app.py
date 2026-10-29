import os
import sqlite3
import hashlib
import secrets
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("LHB_DB_PATH", str(APP_DIR / "laptop_house.db")))
IMAGE_DIR = APP_DIR / "product_images"
IMAGE_DIR.mkdir(exist_ok=True)

SHOP = "LAPTOP HOUSE BUNER"
PHONE = "03348364835 - 03490178074"
EMAIL = "laptophousebuner@gmail.com"
ADDRESS = "Rafi Shopping Mall, 2nd Floor, Pir Baba Buner"

st.set_page_config(page_title=SHOP, page_icon="💻", layout="wide")

def connect():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"

def check_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$",1)[1], digest)
    except Exception:
        return False

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','employee')));
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT 'Laptop', model TEXT DEFAULT '',
          processor TEXT DEFAULT '', ram TEXT DEFAULT '', storage TEXT DEFAULT '',
          graphics TEXT DEFAULT '', display_size TEXT DEFAULT '',
          condition_text TEXT DEFAULT 'Used', serial_number TEXT DEFAULT '',
          purchase_price REAL NOT NULL DEFAULT 0, selling_price REAL NOT NULL DEFAULT 0,
          quantity INTEGER NOT NULL DEFAULT 0, warranty_days INTEGER NOT NULL DEFAULT 0,
          warranty_terms TEXT DEFAULT '', image_filename TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS sales(
          id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE NOT NULL,
          customer_name TEXT DEFAULT '', customer_phone TEXT DEFAULT '',
          sale_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sold_by TEXT NOT NULL,
          total REAL NOT NULL DEFAULT 0, paid_amount REAL NOT NULL DEFAULT 0,
          discount REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sale_items(
          id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id),
          product_id INTEGER NOT NULL REFERENCES products(id), product_name TEXT NOT NULL,
          specs TEXT DEFAULT '', quantity INTEGER NOT NULL, selling_price REAL NOT NULL,
          purchase_price REAL NOT NULL, warranty_days INTEGER NOT NULL DEFAULT 0,
          warranty_expiry TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS payments(
          id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id),
          amount REAL NOT NULL CHECK(amount > 0), payment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          received_by TEXT NOT NULL, note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        # Existing older DB schema compatibility
        pcols = {r["name"] for r in con.execute("PRAGMA table_info(products)")}
        if "category" not in pcols:
            con.execute("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Laptop'")
        scols = {r["name"] for r in con.execute("PRAGMA table_info(sales)")}
        if "paid_amount" not in scols:
            con.execute("ALTER TABLE sales ADD COLUMN paid_amount REAL NOT NULL DEFAULT 0")
        if "discount" not in scols:
            con.execute("ALTER TABLE sales ADD COLUMN discount REAL NOT NULL DEFAULT 0")
        defaults = [
            ("owner", os.environ.get("LHB_OWNER_PASSWORD", "ChangeOwnerPass!2026"), "owner"),
            ("employee", os.environ.get("LHB_STAFF_PASSWORD", "ChangeStaffPass!2026"), "employee"),
        ]
        for username, password, role in defaults:
            existing = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not existing:
                con.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                            (username, hash_password(password), role))
        con.commit()

def money(v):
    return f"Rs {float(v or 0):,.2f}"

def login_screen():
    st.title("💻 Laptop House Buner")
    st.caption(ADDRESS)
    st.subheader("Staff Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login", use_container_width=True)
    if ok:
        with connect() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        if user and check_password(password, user["password_hash"]):
            st.session_state.user = {"id": user["id"], "username": user["username"], "role": user["role"]}
            st.rerun()
        else:
            st.error("Username or password is incorrect.")

def dashboard():
    with connect() as con:
        products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        stock = con.execute("SELECT COALESCE(SUM(quantity),0) FROM products").fetchone()[0]
        invoices = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        due = con.execute("SELECT COALESCE(SUM(total-paid_amount),0) FROM sales").fetchone()[0]
    a,b,c,d = st.columns(4)
    a.metric("Products", products); b.metric("Stock Units", stock)
    c.metric("Invoices", invoices); d.metric("Customer Balance", money(due))
    st.info("Use the menu on the left to manage stock, billing, payments, and reports.")

def product_page():
    user = st.session_state.user
    st.header("📦 Products & Stock")
    with connect() as con:
        rows = con.execute("SELECT * FROM products ORDER BY name").fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        query = st.text_input("Search by name, model, or serial number")
        if query:
            mask = df.astype(str).apply(lambda col: col.str.contains(query, case=False, na=False)).any(axis=1)
            df = df[mask]
        shown = ["id","name","category","model","processor","ram","storage","condition_text","serial_number","selling_price","quantity","warranty_days"]
        if user["role"] == "owner":
            shown += ["purchase_price"]
        st.dataframe(df[[c for c in shown if c in df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("No products yet. Add your first product below.")
    if user["role"] == "owner":
        with st.expander("➕ Add Product", expanded=False):
            with st.form("add_product", clear_on_submit=True):
                c1,c2,c3 = st.columns(3)
                name = c1.text_input("Product name *")
                category = c2.selectbox("Category", ["Laptop","Accessory"])
                model = c3.text_input("Model / Brand")
                processor = c1.text_input("Processor")
                ram = c2.text_input("RAM")
                storage = c3.text_input("Storage")
                graphics = c1.text_input("Graphics")
                display_size = c2.text_input("Display size")
                condition_text = c3.selectbox("Condition", ["Used","New","Refurbished"])
                serial = c1.text_input("Serial number")
                purchase = c2.number_input("Purchase price (Rs)", min_value=0.0, step=100.0)
                selling = c3.number_input("Selling price (Rs)", min_value=0.0, step=100.0)
                qty = c1.number_input("Quantity", min_value=0, step=1)
                warranty = c2.number_input("Warranty days", min_value=0, step=1)
                terms = c3.text_input("Warranty terms")
                submit = st.form_submit_button("Save Product")
            if submit:
                if not name.strip():
                    st.error("Product name is required.")
                else:
                    with connect() as con:
                        con.execute("""INSERT INTO products
                        (name,category,model,processor,ram,storage,graphics,display_size,condition_text,
                         serial_number,purchase_price,selling_price,quantity,warranty_days,warranty_terms)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (name.strip(),category,model,processor,ram,storage,graphics,display_size,condition_text,
                         serial,purchase,selling,int(qty),int(warranty),terms))
                    st.success("Product saved."); st.rerun()
        with st.expander("✏️ Edit / Delete Product"):
            with connect() as con:
                all_products = con.execute("SELECT id,name,category,quantity FROM products ORDER BY name").fetchall()
            if all_products:
                choices = {f'{p["id"]} — {p["name"]} ({p["category"]}, stock {p["quantity"]})': p["id"] for p in all_products}
                selected_label = st.selectbox("Choose product", list(choices))
                pid = choices[selected_label]
                with connect() as con:
                    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                with st.form("edit_product"):
                    name = st.text_input("Name", p["name"])
                    category = st.selectbox("Category", ["Laptop","Accessory"], index=0 if p["category"]=="Laptop" else 1)
                    model = st.text_input("Model", p["model"] or "")
                    processor = st.text_input("Processor", p["processor"] or "")
                    ram = st.text_input("RAM", p["ram"] or "")
                    storage = st.text_input("Storage", p["storage"] or "")
                    graphics = st.text_input("Graphics", p["graphics"] or "")
                    display_size = st.text_input("Display size", p["display_size"] or "")
                    condition_text = st.selectbox("Condition", ["Used","New","Refurbished"], index=["Used","New","Refurbished"].index(p["condition_text"] if p["condition_text"] in ["Used","New","Refurbished"] else "Used"))
                    serial = st.text_input("Serial number", p["serial_number"] or "")
                    purchase = st.number_input("Purchase price", min_value=0.0, value=float(p["purchase_price"]), step=100.0)
                    selling = st.number_input("Selling price", min_value=0.0, value=float(p["selling_price"]), step=100.0)
                    qty = st.number_input("Quantity", min_value=0, value=int(p["quantity"]), step=1)
                    warranty = st.number_input("Warranty days", min_value=0, value=int(p["warranty_days"]), step=1)
                    terms = st.text_input("Warranty terms", p["warranty_terms"] or "")
                    save = st.form_submit_button("Update Product")
                if save:
                    with connect() as con:
                        con.execute("""UPDATE products SET name=?,category=?,model=?,processor=?,ram=?,storage=?,graphics=?,
                        display_size=?,condition_text=?,serial_number=?,purchase_price=?,selling_price=?,quantity=?,warranty_days=?,
                        warranty_terms=? WHERE id=?""",
                        (name,category,model,processor,ram,storage,graphics,display_size,condition_text,serial,purchase,selling,
                         int(qty),int(warranty),terms,pid))
                    st.success("Product updated."); st.rerun()
                if st.button("Delete selected product", type="secondary"):
                    with connect() as con:
                        used = con.execute("SELECT COUNT(*) FROM sale_items WHERE product_id=?", (pid,)).fetchone()[0]
                        if used:
                            st.error("Cannot delete a product used in previous invoices. Set stock to 0 instead.")
                        else:
                            con.execute("DELETE FROM products WHERE id=?", (pid,))
                            st.success("Product deleted."); st.rerun()

def billing_page():
    st.header("🧾 New Sale / Billing")
    with connect() as con:
        rows = con.execute("SELECT * FROM products WHERE quantity>0 ORDER BY name").fetchall()
    if not rows:
        st.warning("No products in stock. Add stock first.")
        return
    choices = {f'{p["name"]} | {p["model"] or ""} | {p["category"]} | {money(p["selling_price"])} | Stock {p["quantity"]}': dict(p) for p in rows}
    with st.form("sale_form"):
        customer = st.text_input("Customer name")
        phone = st.text_input("Customer phone")
        chosen_labels = st.multiselect("Choose products", list(choices))
        quantities = {}
        for label in chosen_labels:
            quantities[label] = st.number_input(f"Quantity — {label}", min_value=1, max_value=int(choices[label]["quantity"]), value=1, step=1, key=f"qty_{choices[label]['id']}")
        discount = st.number_input("Discount (Rs)", min_value=0.0, step=100.0)
        paid = st.number_input("Paid now (Rs)", min_value=0.0, step=100.0)
        submit = st.form_submit_button("Complete Sale & Create Invoice")
    if submit:
        if not chosen_labels:
            st.error("Choose at least one product."); return
        cart = [(choices[l], int(quantities[l])) for l in chosen_labels]
        subtotal = sum(p["selling_price"]*q for p,q in cart)
        total = round(subtotal-discount,2)
        if discount > subtotal:
            st.error("Discount cannot exceed subtotal."); return
        if paid > total:
            st.error("Paid amount cannot exceed total."); return
        inv = "LHB-" + date.today().strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()
        try:
            with connect() as con:
                con.execute("BEGIN IMMEDIATE")
                for p,q in cart:
                    latest = con.execute("SELECT quantity FROM products WHERE id=?", (p["id"],)).fetchone()
                    if not latest or latest["quantity"] < q:
                        raise ValueError(f'Not enough stock for {p["name"]}.')
                cur = con.execute("""INSERT INTO sales(invoice_no,customer_name,customer_phone,sold_by,total,paid_amount,discount)
                                     VALUES(?,?,?,?,?,?,?)""",
                                  (inv,customer,phone,st.session_state.user["username"],total,paid,discount))
                sid = cur.lastrowid
                for p,q in cart:
                    expiry = (date.today()+timedelta(days=int(p["warranty_days"]))).isoformat()
                    specs = ", ".join(str(p[k]) for k in ["model","processor","ram","storage","graphics","display_size","condition_text","serial_number"] if p[k])
                    con.execute("""INSERT INTO sale_items(sale_id,product_id,product_name,specs,quantity,selling_price,
                                   purchase_price,warranty_days,warranty_expiry) VALUES(?,?,?,?,?,?,?,?,?)""",
                                (sid,p["id"],p["name"],specs,q,p["selling_price"],p["purchase_price"],p["warranty_days"],expiry))
                    con.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (q,p["id"]))
                if paid > 0:
                    con.execute("INSERT INTO payments(sale_id,amount,received_by,note) VALUES(?,?,?,?)",
                                (sid,paid,st.session_state.user["username"],"Initial payment"))
            st.session_state.last_invoice = sid
            st.success(f"Sale saved. Invoice: {inv}")
            st.rerun()
        except Exception as e:
            st.error(f"Sale was not saved: {e}")
    if st.session_state.get("last_invoice"):
        invoice_view(st.session_state.last_invoice)

def invoice_view(sale_id):
    with connect() as con:
        sale = con.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        items = con.execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall()
        payments = con.execute("SELECT * FROM payments WHERE sale_id=? ORDER BY id", (sale_id,)).fetchall()
    if not sale:
        st.error("Invoice not found."); return
    st.divider()
    st.subheader(f"🧾 Invoice {sale['invoice_no']}")
    st.markdown(f"**{SHOP}**  \n{ADDRESS}  \n{PHONE} · {EMAIL}")
    st.write(f"Date: {sale['sale_date']} · Customer: {sale['customer_name']} · Phone: {sale['customer_phone']}")
    df = pd.DataFrame([{"Product":i["product_name"],"Specifications":i["specs"],"Qty":i["quantity"],
                        "Unit Price":i["selling_price"],"Amount":i["selling_price"]*i["quantity"],
                        "Warranty":f'{i["warranty_days"]} days',"Expiry":i["warranty_expiry"]} for i in items])
    st.dataframe(df, use_container_width=True, hide_index=True)
    balance = round(max(0, sale["total"]-sale["paid_amount"]),2)
    a,b,c = st.columns(3)
    a.metric("Total",money(sale["total"])); b.metric("Paid",money(sale["paid_amount"])); c.metric("Balance",money(balance))
    st.caption("Use your browser/app print function to print this invoice. PDF download can be added if needed.")
    if payments:
        st.write("Payment history")
        st.dataframe(pd.DataFrame([dict(p) for p in payments]), use_container_width=True, hide_index=True)
    if balance > 0 and st.session_state.user:
        with st.form(f"payment_{sale_id}"):
            amount = st.number_input("Receive payment (Rs)", min_value=0.01, max_value=float(balance), step=100.0)
            note = st.text_input("Method / note", "Cash")
            submit = st.form_submit_button("Save Payment")
        if submit:
            with connect() as con:
                con.execute("INSERT INTO payments(sale_id,amount,received_by,note) VALUES(?,?,?,?)",
                            (sale_id,amount,st.session_state.user["username"],note))
                con.execute("UPDATE sales SET paid_amount=paid_amount+? WHERE id=?", (amount,sale_id))
            st.success("Payment saved."); st.rerun()

def sales_page():
    st.header("📚 Sales History")
    with connect() as con:
        rows = con.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 500").fetchall()
    if not rows:
        st.info("No sales yet."); return
    df = pd.DataFrame([dict(r) for r in rows])
    df["balance"] = (df["total"]-df["paid_amount"]).clip(lower=0)
    st.dataframe(df[["invoice_no","sale_date","customer_name","customer_phone","total","paid_amount","balance","sold_by"]],
                 use_container_width=True, hide_index=True)
    choices = {f'{r["invoice_no"]} — {r["customer_name"]} — {money(r["total"])}':r["id"] for r in rows}
    selected = st.selectbox("Open invoice", list(choices))
    if st.button("View Invoice"):
        st.session_state.view_invoice = choices[selected]
    if st.session_state.get("view_invoice"):
        invoice_view(st.session_state.view_invoice)

def reports_page():
    if st.session_state.user["role"] != "owner":
        st.error("Owner access only."); return
    st.header("📊 Reports")
    with connect() as con:
        totals = con.execute("""SELECT COUNT(*) count, COALESCE(SUM(total),0) revenue,
        COALESCE(SUM(paid_amount),0) paid, COALESCE(SUM(total-paid_amount),0) due FROM sales""").fetchone()
        profit = con.execute("SELECT COALESCE(SUM((selling_price-purchase_price)*quantity),0) FROM sale_items").fetchone()[0]
        stock_value = con.execute("SELECT COALESCE(SUM(purchase_price*quantity),0) FROM products").fetchone()[0]
    cols = st.columns(3)
    cols[0].metric("Invoices", totals["count"]); cols[1].metric("Total Sales", money(totals["revenue"]))
    cols[2].metric("Payments Received", money(totals["paid"]))
    cols = st.columns(3)
    cols[0].metric("Customer Balances", money(totals["due"])); cols[1].metric("Estimated Gross Profit", money(profit))
    cols[2].metric("Stock Purchase Value", money(stock_value))

def backup_page():
    if st.session_state.user["role"] != "owner":
        st.error("Owner access only."); return
    st.header("💾 Database Backup / Restore")
    st.warning("Keep backup files private. A database contains shop sales and customer information.")
    if DB_PATH.exists():
        st.download_button("Download current database backup", data=DB_PATH.read_bytes(),
                           file_name="laptop_house_backup.db", mime="application/octet-stream")
    uploaded = st.file_uploader("Restore/Import an existing laptop_house.db backup", type=["db","sqlite","sqlite3"])
    if uploaded:
        st.error("Restoring replaces the current database. Download a backup first. Confirm only if this is the correct shop database.")
        if st.checkbox("I have downloaded a backup and want to replace current database"):
            if st.button("Restore uploaded database", type="primary"):
                try:
                    # validate uploaded DB before replacement
                    temp = APP_DIR / "restore_check.db"
                    temp.write_bytes(uploaded.getvalue())
                    chk = sqlite3.connect(temp)
                    tables = {r[0] for r in chk.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    chk.close()
                    if not {"products","sales","sale_items","users"}.issubset(tables):
                        temp.unlink(missing_ok=True)
                        st.error("This database does not look like a Laptop House Buner database.")
                    else:
                        import shutil
                        shutil.copy2(temp, DB_PATH)
                        temp.unlink(missing_ok=True)
                        st.success("Database restored. Please log out and log in again.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Restore failed: {e}")

def main():
    init_db()
    if "user" not in st.session_state:
        login_screen()
        return
    user = st.session_state.user
    st.sidebar.title("💻 Laptop House Buner")
    st.sidebar.caption(f'{user["username"]} · {user["role"]}')
    page = st.sidebar.radio("Menu", ["Dashboard","Products & Stock","New Sale / Billing","Sales History","Reports","Database Backup"])
    if st.sidebar.button("Logout"):
        del st.session_state.user
        st.rerun()
    if page == "Dashboard": dashboard()
    elif page == "Products & Stock": product_page()
    elif page == "New Sale / Billing": billing_page()
    elif page == "Sales History": sales_page()
    elif page == "Reports": reports_page()
    elif page == "Database Backup": backup_page()
    st.sidebar.divider()
    st.sidebar.caption(f"{PHONE}\n{EMAIL}")

main()
