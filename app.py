import os
import ssl
import re
import cloudinary
import threading
import telebot
import random
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta # Важно: импортируем только так
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from sqlalchemy import text
from sqlalchemy.orm import Session
from RAG import rag_query, set_db_products_function


cloudinary.config(
    cloud_name="YOUR_CLOUD_NAME",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET"
)


ssl._create_default_https_context = ssl._create_unverified_context


app = Flask(__name__)

# --- КОНФИГУРАЦИЯ ---
app.config['SECRET_KEY'] = 'fishing_ultra_mega_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['PRODUCT_UPLOADS'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:MtSgofBGovxMowXdvOyRuebJAAXZHShm@maglev.proxy.rlwy.net:18633/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config.update(dict(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='beztele153@gmail.com',
    MAIL_PASSWORD='odax zbtq wwko veoa',
    MAIL_DEFAULT_SENDER=('Fishing Shop', 'beztele153@gmail.com')
))

TELEGRAM_BOT_TOKEN = '8478250303:AAGO88C82UCxrZ8dJjJEDogbL6hKjPy4Izs'

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ====================== МОДЕЛИ ======================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(255))
    avatar = db.Column(db.String(255), default='default.png')
    is_admin = db.Column(db.Boolean, default=False)
    tg_id = db.Column(db.String(50))

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    image = db.Column(db.String(255), default='no_image.png')
    old_price = db.Column(db.Float, nullable=True)   # ← НОВАЯ КОЛОНКА

class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'))
    quantity = db.Column(db.Integer, default=1)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # ИСПРАВЛЕНО: просто datetime.utcnow без повтора слова datetime
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 
    total_price = db.Column(db.Float)
    delivery_address = db.Column(db.String(255))
    status = db.Column(db.String(50), default='В обработке')
    notification_method = db.Column(db.String(20))
    tg_contact = db.Column(db.String(100))

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'))
    quantity = db.Column(db.Integer)
    price_at_purchase = db.Column(db.Float)   # именно price, не price_at_purchase

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ====================== МИГРАЦИИ ======================
with app.app_context():
    db.create_all()
    try:
        # Добавление колонок в orders
        db.session.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS old_price FLOAT;"))
        db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
        db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
        db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_address VARCHAR(255);"))
        db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS notification_method VARCHAR(20);"))
        db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS tg_contact VARCHAR(100);"))
        
        # Добавление колонки в users
        db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tg_id VARCHAR(50);"))
        
        # Добавление колонки price в order_items
        db.session.execute(text("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS price FLOAT;"))
        
        db.session.commit()
        print("✅ Все недостающие колонки добавлены!")
    except Exception as e:
        print("Миграция уже была или ошибка:", e)

# ====================== RAG ИНТЕГРАЦИЯ ======================
def get_products_for_rag(query: str):
    """Функция для поиска товаров в БД по запросу (для RAG)"""
    try:
        # Поиск по названию и описанию
        search_term = f"%{query}%"
        products = Product.query.filter(
            (Product.name.ilike(search_term)) |
            (Product.description.ilike(search_term)) |
            (Product.category.ilike(search_term))
        ).all()

        return [
            {
                'name': p.name,
                'category': p.category,
                'price': p.price,
                'description': p.description or ''
            }
            for p in products
        ]
    except Exception as e:
        print(f"Ошибка поиска товаров: {e}")
        return []

# Регистрируем функцию в RAG-модуле
set_db_products_function(get_products_for_rag)

# ====================== УТИЛИТЫ ======================
def send_telegram_notification(chat_id, message):
    if not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except:
        pass

def get_clean_cart():
    if 'cart' not in session or not isinstance(session['cart'], list):
        session['cart'] = []
        session.modified = True
        return []
    clean = []
    for item in session['cart']:
        if isinstance(item, dict) and isinstance(item.get('id'), int):
            qty = item.get('quantity', 1)
            if isinstance(qty, int) and qty > 0:
                clean.append({'id': item['id'], 'quantity': qty})
    session['cart'] = clean
    session.modified = True
    return clean

@app.context_processor
def inject_cart_count():
    cart = get_clean_cart()
    count = sum(item['quantity'] for item in cart)
    return dict(cart_items_count=count)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function



def get_moon_phase(date):
    """Расчет фазы луны для рыболовного календаря"""
    lunar_days = 29.53058770576
    new_moon = datetime(1970, 1, 7, 20, 35, 0)
    phase = ((date - new_moon).total_seconds() / 86400) % lunar_days
    
    if phase < 1.84 or phase > 27.69: 
        return "🌑 Новолуние", "dark", "Слабый"
    elif phase < 5.53: 
        return "🌒 Растущая", "success", "Отличный"
    elif phase < 12.91: 
        return "🌓 Первая четверть", "warning", "Средний"
    elif phase < 16.61: 
        return "🌕 Полнолуние", "danger", "Слабый"
    elif phase < 20.30: 
        return "🌗 Убывающая", "success", "Отличный"
    else: 
        return "🌘 Последняя четверть", "warning", "Средний"

def generate_calendar(start_date, days=6):
    """Генерация данных для календаря на несколько дней вперед"""
    calendar = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        phase_name, color, rating = get_moon_phase(current_date)
        calendar.append({
            "date": current_date.strftime("%d.%m"),
            "phase": phase_name,
            "color": color,
            "rating": rating
        })
    return calendar

def get_fresh_news():
    news_list = []
    
    # Притворяемся обычным браузером, чтобы нас не заблокировали
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    # ==========================================
    # 1. Парсинг Onliner (HTML)
    # ==========================================
    try:
        onliner_url = "https://people.onliner.by/tag/rybalka"
        resp_o = requests.get(onliner_url, headers=headers, timeout=8)
        
        if resp_o.status_code == 200:
            soup = BeautifulSoup(resp_o.text, 'html.parser')
            
            # Onliner обычно хранит новости в таких блоках
            articles = soup.find_all('div', class_=re.compile(r'news-tidings__item|news-header__item|news-text'))
            
            count = 0
            for article in articles:
                if count >= 2: break # Берём 2 последние новости отсюда
                
                link_tag = article.find('a')
                if not link_tag: continue
                
                link = link_tag.get('href', '')
                if link.startswith('/'):
                    link = "https://people.onliner.by" + link
                
                title_tag = article.find(class_=re.compile(r'title|subtitle'))
                title = title_tag.get_text(strip=True) if title_tag else "Новость Onliner"
                
                # Ищем картинку (Onliner часто прячет её в background-image)
                img_url = 'https://images.unsplash.com/photo-1544551763-47a0159f9234?w=800' # Дефолт
                
                # Поиск обычного тега <img>
                img_tag = article.find('img')
                if img_tag and img_tag.get('src'):
                    img_url = img_tag.get('src')
                else:
                    # Поиск картинки в стилях div-а
                    bg_div = article.find(style=re.compile(r'background-image'))
                    if bg_div:
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', bg_div['style'])
                        if match: 
                            img_url = match.group(1)

                summary_tag = article.find(class_=re.compile(r'speech|text|description'))
                summary = summary_tag.get_text(strip=True) if summary_tag else "Читайте подробности на сайте..."

                news_list.append({
                    "title": title,
                    "summary": summary[:110] + "...",
                    "link": link,
                    "image": img_url,
                    "timestamp": datetime.now().timestamp() + 10 # Искусственно поднимаем выше в сортировке
                })
                count += 1
    except Exception as e:
        print(f"⚠️ Ошибка парсинга Onliner: {e}")

    # ==========================================
    # 2. Парсинг Google News (RSS)
    # ==========================================
    try:
        # Важно: мы добавляем /rss/ перед /topics/, чтобы получить чистые данные, а не тяжелый скриптовый сайт
        google_url = "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNREZuYkRVd0VnSnlkU2dBUAE?hl=ru&gl=RU&ceid=RU:ru"
        resp_g = requests.get(google_url, headers=headers, timeout=8)
        
        if resp_g.status_code == 200:
            feed = feedparser.parse(resp_g.content)
            
            for entry in feed.entries[:2]: # Берём 2 новости отсюда
                content = entry.get('summary', '') + entry.get('description', '')
                
                # Дефолтная картинка, если Google не отдаст фото
                img_url = 'https://images.unsplash.com/photo-1506477331477-33d5d8b3dc85?w=800'
                
                # Достаем тег <img> из описания RSS-ленты
                img_match = re.search(r'<img [^>]*src=["\']([^"\']+)["\']', content)
                if img_match:
                    img_url = img_match.group(1)

                clean_text = re.sub('<[^<]+?>', '', content).strip()
                clean_text = " ".join(clean_text.split()) # Убираем лишние пробелы

                news_list.append({
                    "title": entry.title,
                    "summary": clean_text[:110] + "...",
                    "link": entry.link,
                    "image": img_url,
                    "timestamp": time.mktime(entry.published_parsed) if 'published_parsed' in entry else datetime.now().timestamp()
                })
    except Exception as e:
        print(f"⚠️ Ошибка парсинга Google News: {e}")

    # Сортируем собранные новости (сначала самые свежие)
    news_list.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

    # Возвращаем максимум 3 новости для красивого отображения в шаблоне
    return news_list[:3] if news_list else get_mock_news()

def get_mock_news():
    """Запасные новости на случай ошибки сервера"""
    return [
        {
            "title": "Секреты весеннего клёва 2026",
            "summary": "Разбираемся, на что лучше ловить щуку в этом сезоне...",
            "link": "#",
            "image": "https://images.unsplash.com/photo-1544551763-47a0159f9234?w=400"
        },
        {
            "title": "Обзор новинок Shimano",
            "summary": "Новые катушки серии Stella поступили на тестирование...",
            "link": "#",
            "image": "https://images.unsplash.com/photo-1506477331477-33d5d8b3dc85?w=400"
        }
    ]

# ====================== МАРШРУТЫ ======================

@app.route('/')
def index():
    # Работа с датой для календаря
    date_str = request.args.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
    except:
        selected_date = datetime.now()

    # Сбор данных
    calendar_data = generate_calendar(selected_date)
    news_data = get_fresh_news()

    return render_template(
        'index.html', 
        calendar=calendar_data, 
        news=news_data, 
        selected_date=selected_date.strftime('%Y-%m-%d')
    )


@app.route('/promotions')
def promotions():
    # Показываем только товары со скидкой
    discounted = Product.query.filter(
        Product.old_price.isnot(None),
        Product.price < Product.old_price
    ).all()
    
    return render_template('promotions.html', products=discounted)

@app.route('/about')
def about(): return render_template('about.html')
@app.route('/delivery')
def delivery(): return render_template('delivery.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('login_identity')
        password = request.form.get('password')
        
        # Ищем пользователя либо по username, либо по email
        user = User.query.filter((User.username == identity) | (User.email == identity)).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('profile'))
        flash('Неверные данные для входа')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('Email занят!', 'danger')
            return redirect(url_for('register'))
        otp = str(random.randint(100000, 999999))
        session['temp_user'] = {
            'username': request.form.get('username'),
            'email': email,
            'password': generate_password_hash(request.form.get('password')),
            'otp': otp
        }
        try:
            msg = Message('Код Fishing Shop', recipients=[email])
            msg.body = f'Код: {otp}'
            mail.send(msg)
            return redirect(url_for('verify_code'))
        except Exception as e:
            flash(f'Ошибка отправки: {e}', 'danger')
    return render_template('register.html')

@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        temp = session.get('temp_user')
        if temp and request.form.get('code') == temp['otp']:
            new_u = User(username=temp['username'], email=temp['email'], password=temp['password'])
            db.session.add(new_u)
            db.session.commit()
            session.pop('temp_user', None)
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        flash('Неверный код', 'danger')
    return render_template('verify_code.html')

@app.route('/catalog')
def catalog():
    cat = request.args.get('category')
    search = request.args.get('search')
    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if cat:
        query = query.filter_by(category=cat)
    return render_template('catalog.html', products=query.all())

@app.route('/product/<int:id>')
def product_detail(id):
    product = db.session.get(Product, id)
    return render_template('product_detail.html', product=product)

@app.route('/cart')
def cart():
    cart_session = get_clean_cart()
    items = []
    total = 0
    for item in cart_session:
        product = db.session.get(Product, item['id'])
        if product:
            subtotal = product.price * item['quantity']
            total += subtotal
            items.append({'product': product, 'quantity': item['quantity'], 'subtotal': subtotal})
    return render_template('cart.html', items=items, total=total)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = get_clean_cart()
    found = False
    for item in cart:
        if item['id'] == product_id:
            item['quantity'] += 1
            found = True
            break
    if not found:
        cart.append({'id': product_id, 'quantity': 1})
    session.modified = True
    flash('Товар добавлен!', 'success')
    return redirect(request.referrer or url_for('catalog'))

@app.route('/update_cart/<int:id>/<action>')
def update_cart(id, action):
    cart = get_clean_cart()
    for item in cart:
        if item['id'] == id:
            if action == 'inc':
                item['quantity'] += 1
            elif action == 'dec' and item['quantity'] > 1:
                item['quantity'] -= 1
            break
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:id>')
def remove_from_cart(id):
    cart = get_clean_cart()
    session['cart'] = [item for item in cart if item['id'] != id]
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_session = get_clean_cart()
    if not cart_session:
        return redirect(url_for('catalog'))

    total = sum(db.session.get(Product, item['id']).price * item.get('quantity', 1) for item in cart_session)

    if request.method == 'POST':
        # Доставка
        delivery_type = request.form.get('delivery_type')
        city = request.form.get('city', 'Минск')
        address = request.form.get('address', '')
        selected_post_name = request.form.get('selected_post_name', '')
        selected_post_address = request.form.get('selected_post_address', '')

        if delivery_type == 'post':
            delivery_info = f"{selected_post_name} ({selected_post_address})"
        elif delivery_type == 'courier':
            delivery_info = f"Курьер: {city}, {address}"
        else:  # pickup
            delivery_info = f"Самовывоз ({city})"

        # Способ уведомления
        method = request.form.get('notification_method', 'email')
        tg_contact = request.form.get('tg_contact') if method == 'telegram' else None

        # Если выбран Telegram и введён ID, сохраняем его в профиль (если он изменился)
        if method == 'telegram' and tg_contact and tg_contact != current_user.tg_id:
            current_user.tg_id = tg_contact
            db.session.commit()

        # Создаём заказ
        new_order = Order(
            user_id=current_user.id,
            total_price=total,
            delivery_address=delivery_info,
            notification_method=method,
            tg_contact=tg_contact
        )
        db.session.add(new_order)
        db.session.commit()

        # Сохраняем товары заказа (опционально)
        for item in cart_session:
            product = db.session.get(Product, item['id'])
            if product:
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=product.id,
                    quantity=item['quantity'],
                    price_at_purchase=product.price   # используем точное имя колонки
                )
                db.session.add(order_item)
        db.session.commit()

        # Формируем текст уведомления
        msg_text = f"✅ Заказ #{new_order.id} успешно оформлен!\nСумма: {total} ₽\nДоставка: {delivery_info}"

        # Отправляем уведомление
        if method == 'telegram' and tg_contact:
            send_telegram_notification(tg_contact, msg_text)
        else:
            try:
                msg = Message(
                    subject=f'Заказ #{new_order.id} — Fishing Shop',
                    recipients=[current_user.email],
                    body=msg_text
                )
                mail.send(msg)
            except Exception as e:
                flash(f'Не удалось отправить письмо: {e}', 'warning')

        session.pop('cart', None)
        flash('✅ Заказ оформлен! Уведомление отправлено.', 'success')
        return redirect(url_for('profile'))

    return render_template('checkout.html', total=total)

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_panel():
    if request.method == 'POST':
        p_id = request.form.get('product_id')
        name = request.form.get('name')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        desc = request.form.get('description')
        
        # ← НОВОЕ: старая цена
        old_price_str = request.form.get('old_price', '').strip()
        old_price = float(old_price_str) if old_price_str else None

        file = request.files.get('image')
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['PRODUCT_UPLOADS'], filename))

        if p_id:
            p = db.session.get(Product, int(p_id))
            p.name = name
            p.price = price
            p.category = category
            p.description = desc
            p.old_price = old_price
            if filename:
                p.image = filename
        else:
            new_p = Product(
                name=name, price=price, category=category,
                description=desc, image=filename or 'no_image.png',
                old_price=old_price
            )
            db.session.add(new_p)
        db.session.commit()
        flash('Товар сохранён!', 'success')
        return redirect(url_for('admin_panel'))

    return render_template('admin.html', products=Product.query.all())

@app.route('/admin/promote/<int:id>')
@admin_required
def admin_promote(id):
    p = db.session.get(Product, id)
    if p and (p.old_price is None or p.old_price <= p.price):
        p.old_price = p.price          # фиксируем старую цену
        db.session.commit()
        flash(f'✅ Товар «{p.name}» добавлен в акции! Теперь снизьте цену.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete/<int:id>')
@admin_required
def admin_delete(id):
    p = db.session.get(Product, id)
    if p:
        db.session.delete(p)
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/orders', methods=['GET', 'POST'])
@admin_required
def admin_orders():
    filter_type = request.args.get('filter', 'active')
    
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        order = db.session.get(Order, int(order_id))
        if order:
            old_status = order.status
            order.status = new_status
            db.session.commit()

            # Уведомление при изменении статуса
            if new_status != old_status and new_status in ['В пути', 'Отправлен', 'Доставлен']:
                msg_text = f"📦 Ваш заказ #{order.id} теперь в статусе: {new_status}"

                if order.notification_method == 'telegram' and order.tg_contact:
                    send_telegram_notification(order.tg_contact, msg_text)
                else:
                    try:
                        user = User.query.get(order.user_id)
                        if user:
                            msg = Message(
                                subject=f'Обновление заказа #{order.id} — Fishing Shop',
                                recipients=[user.email],
                                body=msg_text
                            )
                            mail.send(msg)
                    except:
                        pass

    query = Order.query.order_by(Order.created_at.desc())
    if filter_type == 'active':
        query = query.filter(Order.status.notin_(['Доставлен', 'Отменён']))
    elif filter_type == 'completed':
        query = query.filter(Order.status.in_(['Доставлен', 'Отменён']))
    
    orders = query.all()
    return render_template('admin_orders.html', orders=orders, filter_type=filter_type, User=User)


@app.route('/sales')
def sales():
    # Показываем ТОЛЬКО товары в акции
    discounted_products = Product.query.filter(
        Product.old_price.isnot(None),
        Product.old_price > Product.price
    ).all()
    
    return render_template('sales.html', products=discounted_products)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if request.form.get('action') == 'save_tg':
            new_tg = request.form.get('tg_id', '').strip()   # убираем пробелы
            current_user.tg_id = new_tg if new_tg else None
            db.session.commit()
            print(f"[PROFILE] Сохранён tg_id: '{new_tg}' для пользователя {current_user.id}")
            flash('✅ Telegram ID успешно сохранён!', 'success')

        # аватар (оставляем как было)
        elif 'avatar' in request.files:
            file = request.files.get('avatar')
            if file and file.filename:
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.avatar = filename
                db.session.commit()
                flash('Аватар обновлён!', 'success')

    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', orders=orders)

@app.route('/admin/order/delete/<int:id>')
@admin_required
def admin_order_delete(id):
    order = db.session.get(Order, id)
    if order:
        db.session.delete(order)
        db.session.commit()
        flash(f'Заказ #{id} успешно удалён!', 'success')
    return redirect(url_for('admin_orders'))


@app.route('/help')
def help():
    return render_template('help.html')


# ====================== RAG-АССИСТЕНТ API ======================
# Хранилище истории чатов (в памяти, для сессий)
chat_histories = {}

@app.route('/api/assistant', methods=['POST'])
def assistant_chat():
    """API для чата с RAG-ассистентом"""
    data = request.get_json()
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')

    if not user_message:
        return jsonify({'error': 'Пустое сообщение'}), 400

    # Получаем или создаем историю для сессии
    if session_id not in chat_histories:
        chat_histories[session_id] = []

    history = chat_histories[session_id]

    try:
        response = rag_query(user_message, history)

        # Добавляем в историю
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})

        # Ограничиваем историю последними 10 сообщениями
        if len(history) > 10:
            chat_histories[session_id] = history[-10:]

        return jsonify({'response': response})
    except Exception as e:
        print(f"Ошибка RAG-ассистента: {e}")
        return jsonify({'error': 'Ошибка обработки запроса'}), 500

@app.route('/api/assistant/clear', methods=['POST'])
def assistant_clear():
    """Очистка истории чата"""
    session_id = request.get_json().get('session_id', 'default')
    if session_id in chat_histories:
        chat_histories[session_id] = []
    return jsonify({'success': True})


# ====================== TELEGRAM БОТ (ЛОКАЛЬНЫЙ РЕЖИМ) ======================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

WEBAPP_URL = 'http://127.0.0.1:5000'

@bot.message_handler(commands=['status'])
def cmd_status(message):
    tg_id = str(message.chat.id)
    print(f"[BOT] Команда /status от {tg_id}")
    
    try:
        # ←←← ОТКЛЮЧАЕМ ПРОКСИ ДЛЯ LOCALHOST
        r = requests.get(
            f"{WEBAPP_URL}/api/myorders/{tg_id}", 
            timeout=10,
            proxies={"http": None, "https": None}   # ← ЭТО ГЛАВНОЕ ИСПРАВЛЕНИЕ
        )
        print(f"[BOT] Ответ сайта: статус {r.status_code}")
        
        if r.status_code == 404:
            bot.reply_to(message, 
                f"❌ Аккаунт не привязан!\n\n"
                f"Зайди в Профиль на сайте и укажи свой Telegram ID:\n"
                f"`{tg_id}`", parse_mode='Markdown')
            return
        
        data = r.json()
        orders = data.get("orders", [])
        
        if not orders:
            bot.reply_to(message, "У вас пока нет заказов 😔")
            return
        
        text = "📦 **Ваши заказы:**\n\n"
        for order in orders[:5]:
            text += f"🆔 Заказ **#{order['id']}**\n"
            text += f"📅 {order['date']}\n"
            text += f"💰 **{order['total_price']} ₽**\n"
            text += f"🔸 Статус: **{order['status']}**\n"
            text += f"📍 {order['delivery_address'][:80]}...\n\n"
            
            if order.get('items'):
                text += "🛒 Товары:\n"
                for item in order['items']:
                    text += f"   • {item['name']} ×{item['quantity']} — {item['price']} ₽\n"
                text += "\n"
        
        bot.reply_to(message, text, parse_mode='Markdown')
        
    except Exception as e:
        print(f"[BOT] ❌ ОШИБКА: {type(e).__name__} — {e}")
        bot.reply_to(message, "⚠️ Не удалось связаться с сайтом.\nУбедись, что сайт запущен (`python app.py`).")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.reply_to(message,
        "🛠 **Помощь по заказам**\n\n"
        "• `/status` — показать все заказы + товары\n"
        "• Привяжи Telegram ID в Профиле на сайте\n\n"
        "При смене статуса заказа бот пришлёт уведомление автоматически! 🎣",
        parse_mode='Markdown')

# ────────────────────────────────────────────────────────────────
# API для Telegram-бота — список заказов пользователя по tg_id
# ────────────────────────────────────────────────────────────────
from flask import jsonify

@app.route('/api/myorders/<string:tg_id>')
def api_my_orders(tg_id):
    tg_id = tg_id.strip()  # на всякий случай убираем пробелы

    # ищем пользователя по tg_id
    user = User.query.filter_by(tg_id=tg_id).first()

    if not user:
        return jsonify({
            "success": False,
            "error": "user_not_found",
            "message": "Пользователь с таким Telegram ID не найден"
        }), 404

    # получаем все заказы пользователя
    orders = Order.query.filter_by(user_id=user.id)\
                        .order_by(Order.created_at.desc())\
                        .all()

    result = []

    for order in orders:
        # собираем товары заказа
        items = []
        for oi in OrderItem.query.filter_by(order_id=order.id).all():
            product = Product.query.get(oi.product_id)
            items.append({
                "name": product.name if product else "[товар удалён]",
                "quantity": oi.quantity,
                "price": float(oi.price_at_purchase or 0)  # если есть поле price_at_purchase
            })

        result.append({
            "id": order.id,
            "date": order.created_at.strftime("%d.%m.%Y %H:%M"),
            "total_price": round(float(order.total_price), 0),
            "status": order.status,
            "delivery_address": order.delivery_address or "—",
            "items": items
        })

    return jsonify({
        "success": True,
        "orders": result,
        "user_id": user.id,
        "username": user.username
    })

# ================== ЗАПУСК БОТА С ЗАДЕРЖКОЙ ==================
def run_bot():
    import time
    time.sleep(4)                    # даём Flask полностью запуститься
    print("🤖 Бот успешно запущен и готов к работе!")
    bot.infinity_polling(none_stop=True)

threading.Thread(target=run_bot, daemon=True).start()


# ===== Функция определения рейтинга клёва =====
def get_fishing_rating(phase):
    if phase in ["Full Moon", "New Moon"]:
        return "Отличный", "success"
    elif phase in ["First Quarter", "Last Quarter"]:
        return "Средний", "warning"
    else:
        return "Слабый", "secondary"


# ===== Получение лунных фаз из Open-Meteo =====
def get_moon_calendar(lat, lon, start_date, days=30):
    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")

    url = "https://api.open-meteo.com/v1/astronomy"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "auto"
    }

    response = requests.get(url, params=params)
    data = response.json()

    calendar = []

    for i in range(len(data["daily"]["time"])):
        date = data["daily"]["time"][i]
        phase = data["daily"]["moon_phase"][i]

        rating_text, rating_color = get_fishing_rating(phase)

        calendar.append({
            "date": date,
            "phase": phase,
            "rating": rating_text,
            "color": rating_color
        })

    return calendar


if __name__ == '__main__':
    app.run(debug=True)