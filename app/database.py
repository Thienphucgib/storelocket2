import sqlite3
import time
from datetime import datetime

import os

DB_NAME = "bot_data.db"
if os.environ.get("VERCEL"):
    DB_NAME = "/tmp/bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage_logs (
                    user_id INTEGER,
                    date TEXT,
                    count INTEGER,
                    PRIMARY KEY (user_id, date)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    uid TEXT,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

def get_user_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT count FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    
    if result:
        new_count = result[0] + 1
        c.execute("UPDATE usage_logs SET count = ? WHERE user_id = ? AND date = ?", (new_count, user_id, today))
    else:
        c.execute("INSERT INTO usage_logs (user_id, date, count) VALUES (?, ?, ?)", (user_id, today, 1))
        
    conn.commit()
    conn.close()

def check_can_request(user_id, max_limit=5):
    current = get_user_usage(user_id)
    return current < max_limit

def set_lang(user_id, lang):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_settings (user_id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()
    conn.close()

def get_lang(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT language FROM user_settings WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM usage_logs UNION SELECT user_id FROM user_settings")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def reset_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("DELETE FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    conn.commit()
    conn.close()

def set_config(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_config(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_config WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def log_request(user_id, uid, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO request_logs (user_id, uid, status) VALUES (?, ?, ?)", (user_id, uid, status))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM request_logs")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM request_logs WHERE status = 'SUCCESS'")
    success = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM request_logs WHERE status != 'SUCCESS'")
    fail = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM request_logs")
    unique_users = c.fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "success": success,
        "fail": fail,
        "unique_users": unique_users
    }

init_db()

# --- Store / package management ---
def init_store_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL DEFAULT 0,
        duration_days INTEGER NOT NULL DEFAULT 30,
        description TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        user_id TEXT,
        package_id INTEGER NOT NULL,
        customer_name TEXT DEFAULT '',
        contact TEXT DEFAULT '',
        amount INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        note TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(package_id) REFERENCES packages(id)
    )''')
    c.execute("SELECT COUNT(*) FROM packages")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO packages(name,price,duration_days,description,active,sort_order) VALUES(?,?,?,?,1,?)", [
            ('Gói 1 tháng', 29000, 30, 'Thời hạn 30 ngày', 1),
            ('Gói 3 tháng', 69000, 90, 'Tiết kiệm hơn cho nhu cầu dài hạn', 2),
            ('Gói 1 năm', 199000, 365, 'Thời hạn 365 ngày', 3),
        ])
    conn.commit(); conn.close()

def get_packages(include_inactive=False):
    conn=sqlite3.connect(DB_NAME); conn.row_factory=sqlite3.Row; c=conn.cursor()
    q='SELECT * FROM packages' + ('' if include_inactive else ' WHERE active=1') + ' ORDER BY sort_order,id'
    rows=[dict(r) for r in c.execute(q).fetchall()]; conn.close(); return rows

def save_package(data):
    conn=sqlite3.connect(DB_NAME); c=conn.cursor()
    pid=data.get('id')
    vals=(data['name'], int(data['price']), int(data['duration_days']), data.get('description',''), 1 if data.get('active',True) else 0, int(data.get('sort_order',0)))
    if pid:
        c.execute('UPDATE packages SET name=?,price=?,duration_days=?,description=?,active=?,sort_order=? WHERE id=?', vals+(int(pid),))
    else:
        c.execute('INSERT INTO packages(name,price,duration_days,description,active,sort_order) VALUES(?,?,?,?,?,?)', vals); pid=c.lastrowid
    conn.commit(); conn.close(); return int(pid)

def delete_package(pid):
    conn=sqlite3.connect(DB_NAME); c=conn.cursor(); c.execute('DELETE FROM packages WHERE id=?',(pid,)); conn.commit(); ok=c.rowcount>0; conn.close(); return ok

def create_order(user_id, package_id, customer_name='', contact='', note=''):
    import secrets
    conn=sqlite3.connect(DB_NAME); conn.row_factory=sqlite3.Row; c=conn.cursor()
    p=c.execute('SELECT * FROM packages WHERE id=? AND active=1',(package_id,)).fetchone()
    if not p: conn.close(); return None
    code='TP'+datetime.now().strftime('%y%m%d')+secrets.token_hex(3).upper()
    c.execute('INSERT INTO orders(order_code,user_id,package_id,customer_name,contact,amount,note) VALUES(?,?,?,?,?,?,?)', (code,str(user_id or ''),package_id,customer_name,contact,int(p['price']),note))
    conn.commit(); oid=c.lastrowid; conn.close(); return {'id':oid,'order_code':code,'amount':int(p['price']),'package_name':p['name']}

def get_orders():
    conn=sqlite3.connect(DB_NAME); conn.row_factory=sqlite3.Row; c=conn.cursor()
    rows=[dict(r) for r in c.execute('''SELECT o.*,p.name package_name FROM orders o LEFT JOIN packages p ON p.id=o.package_id ORDER BY o.id DESC LIMIT 300''').fetchall()]; conn.close(); return rows

def update_order_status(oid,status):
    if status not in {'pending','paid','processing','completed','cancelled'}: return False
    conn=sqlite3.connect(DB_NAME); c=conn.cursor(); c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid)); conn.commit(); ok=c.rowcount>0; conn.close(); return ok

init_store_db()
