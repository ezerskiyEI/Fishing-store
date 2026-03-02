import os
import random
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

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
    MAIL_DEFAULT_SENDER='beztele153@gmail.com'
))

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

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ====================== КОРЗИНА ======================
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

# --- КОРЗИНА ---
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

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    delivery_type = request.form.get('delivery_type')
    city = request.form.get('city', 'Витебск')
    address = request.form.get('address')
    selected_post_name = request.form.get('selected_post_name')
    selected_post_address = request.form.get('selected_post_address')

    if delivery_type == 'post':
        if not selected_post_name:
            flash('❌ Выберите пункт выдачи на карте!', 'danger')
            return redirect(url_for('cart'))
        delivery_info = f"{selected_post_name} ({selected_post_address})"
    elif delivery_type == 'courier':
        delivery_info = f"Курьер: {city}, {address}"
    else:
        delivery_info = f"Самовывоз в {city}"

    session.pop('cart', None)
    flash(f'✅ Заказ успешно оформлен! Доставка: {delivery_info}', 'success')
    return redirect(url_for('profile'))

# --- АДМИНКА ---
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

@app.route('/admin/orders')
@admin_required
def admin_orders():
    filter_type = request.args.get('filter', 'active')  # по умолчанию активные
    
    query = Order.query.order_by(Order.created_at.desc())
    
    if filter_type == 'active':
        query = query.filter(Order.status.notin_(['Доставлен', 'Отменён']))
    elif filter_type == 'completed':
        query = query.filter(Order.status.in_(['Доставлен', 'Отменён']))
    
    orders = query.all()
    return render_template('admin_orders.html', orders=orders, filter_type=filter_type)

@app.route('/promotions')
def promotions(): return render_template('promotions.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/delivery')
def delivery(): return render_template('delivery.html')
@app.route('/profile')
@login_required
def profile(): return render_template('profile.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)