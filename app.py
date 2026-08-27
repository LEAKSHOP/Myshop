from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import secrets
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_NAME = os.path.join(os.path.dirname(__file__), "shop.db")

# =============================================
# ФУНКЦИЯ ХЕШИРОВАНИЯ (ДОЛЖНА БЫТЬ ПЕРВОЙ)
# =============================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =============================================
# БАЗА ДАННЫХ
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            discord_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            emoji TEXT,
            category TEXT DEFAULT 'Услуги'
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_id INTEGER,
            status TEXT DEFAULT 'Новый',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS support (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            reply TEXT,
            status TEXT DEFAULT 'Новое',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Админ: admLeakshop / txtserphelog
    admin_pass = hash_password("txtserphelog")
    cur.execute('INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, 1)', ('admLeakshop', admin_pass))
    
    # Услуги
    services = [
        ('🚀 GAME BOOST', 'Чистка Windows + настройка игры + TwikBooster', 700, '🚀', 'Пакеты'),
        ('⚡ MAX FPS REBOOT', 'Чистка + BIOS + разгон GPU + сеть', 899, '⚡', 'Пакеты'),
        ('💎 FULL PACK BOOST', 'Всё включено (экономия 200 ₽)', 1399, '💎', 'Пакеты'),
        ('🎮 Настройка игр', 'Оптимизация Rust/CS2/PUBG/Apex', 500, '🎮', 'Услуги'),
        ('🌀 Удаление микрофризов', 'Диагностика и устранение зависаний', 500, '🌀', 'Услуги'),
        ('🧹 Чистка Windows', 'Удаление мусора и кэша', 400, '🧹', 'Услуги'),
        ('⚡ Настройка BIOS', 'XMP, разгон процессора', 500, '⚡', 'Услуги'),
        ('🛡️ Настройка интернета', 'MTU, DNS, TCP — убираем пинг', 400, '🛡️', 'Услуги'),
    ]
    for name, desc, price, emoji, category in services:
        cur.execute('INSERT OR IGNORE INTO services (name, description, price, emoji, category) VALUES (?, ?, ?, ?, ?)',
                   (name, desc, price, emoji, category))
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================
# ЗАПУСК БАЗЫ ДАННЫХ
# =============================================
init_db()

# =============================================
# МАРШРУТЫ
# =============================================

@app.route('/')
def index():
    conn = get_db()
    services = conn.execute('SELECT * FROM services').fetchall()
    conn.close()
    return render_template('index.html', services=services, user=session.get('user'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        discord_id = request.form.get('discord_id', '')
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, password, discord_id) VALUES (?, ?, ?)',
                        (username, password, discord_id))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except:
            conn.close()
            return render_template('register.html', error='Пользователь уже существует')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                           (username, password)).fetchone()
        conn.close()
        if user:
            session['user'] = dict(user)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    orders = conn.execute('''
        SELECT orders.*, services.name, services.emoji 
        FROM orders JOIN services ON orders.service_id = services.id 
        WHERE orders.user_id = ?
        ORDER BY orders.created_at DESC
    ''', (session['user']['id'],)).fetchall()
    conn.close()
    return render_template('profile.html', user=session['user'], orders=orders)

@app.route('/admin')
def admin():
    if 'user' not in session or session['user']['is_admin'] != 1:
        return redirect(url_for('index'))
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    services = conn.execute('SELECT * FROM services').fetchall()
    orders = conn.execute('''
        SELECT orders.*, users.username, services.name as service_name 
        FROM orders JOIN users ON orders.user_id = users.id 
        JOIN services ON orders.service_id = services.id
        ORDER BY orders.created_at DESC
    ''').fetchall()
    support = conn.execute('''
        SELECT support.*, users.username 
        FROM support JOIN users ON support.user_id = users.id 
        ORDER BY support.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin.html', users=users, services=services, orders=orders, support=support, user=session['user'])

@app.route('/admin/add_service', methods=['POST'])
def add_service():
    if 'user' not in session or session['user']['is_admin'] != 1:
        return redirect(url_for('index'))
    name = request.form['name']
    description = request.form['description']
    price = int(request.form['price'])
    emoji = request.form['emoji']
    category = request.form.get('category', 'Услуги')
    conn = get_db()
    conn.execute('INSERT INTO services (name, description, price, emoji, category) VALUES (?, ?, ?, ?, ?)',
                (name, description, price, emoji, category))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/delete_service/<int:service_id>')
def delete_service(service_id):
    if 'user' not in session or session['user']['is_admin'] != 1:
        return redirect(url_for('index'))
    conn = get_db()
    conn.execute('DELETE FROM services WHERE id = ?', (service_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/reply_support/<int:support_id>', methods=['POST'])
def reply_support(support_id):
    if 'user' not in session or session['user']['is_admin'] != 1:
        return redirect(url_for('index'))
    reply = request.form['reply']
    conn = get_db()
    conn.execute('UPDATE support SET reply = ?, status = "Отвечено" WHERE id = ?', (reply, support_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/cart')
def cart():
    if 'user' not in session:
        return redirect(url_for('login'))
    cart = session.get('cart', [])
    if not cart:
        return render_template('cart.html', services=[], total=0, user=session['user'])
    conn = get_db()
    services = conn.execute('SELECT * FROM services WHERE id IN ({})'.format(','.join(['?']*len(cart))), cart).fetchall()
    conn.close()
    total = sum(s['price'] for s in services)
    return render_template('cart.html', services=services, total=total, user=session['user'])

@app.route('/add_to_cart/<int:service_id>')
def add_to_cart(service_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    if 'cart' not in session:
        session['cart'] = []
    session['cart'].append(service_id)
    session.modified = True
    return redirect(url_for('index'))

@app.route('/order')
def order():
    if 'user' not in session or 'cart' not in session or not session['cart']:
        return redirect(url_for('index'))
    conn = get_db()
    for service_id in session['cart']:
        conn.execute('INSERT INTO orders (user_id, service_id) VALUES (?, ?)',
                    (session['user']['id'], service_id))
    conn.commit()
    conn.close()
    session['cart'] = []
    session.modified = True
    return redirect(url_for('profile'))

@app.route('/support', methods=['GET', 'POST'])
def support():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        message = request.form['message']
        conn = get_db()
        conn.execute('INSERT INTO support (user_id, message) VALUES (?, ?)',
                    (session['user']['id'], message))
        conn.commit()
        conn.close()
        return redirect(url_for('support'))
    conn = get_db()
    tickets = conn.execute('SELECT * FROM support WHERE user_id = ? ORDER BY created_at DESC',
                          (session['user']['id'],)).fetchall()
    conn.close()
    return render_template('support.html', user=session['user'], tickets=tickets)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
