import os
import random
import datetime
import requests
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from sqlalchemy import text

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
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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

# ====================== МАРШРУТЫ ======================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/promotions')
def promotions(): return render_template('promotions.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/delivery')
def delivery(): return render_template('delivery.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Неверный логин или пароль', 'danger')
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
        file = request.files.get('image')
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['PRODUCT_UPLOADS'], filename))
        if p_id:
            p = db.session.get(Product, int(p_id))
            p.name = name; p.price = price; p.category = category; p.description = desc
            if filename: p.image = filename
        else:
            new_p = Product(name=name, price=price, category=category, description=desc, image=filename or 'no_image.png')
            db.session.add(new_p)
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('admin.html', products=Product.query.all())

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

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
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

if __name__ == '__main__':
    app.run(debug=True)