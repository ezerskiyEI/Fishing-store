import os, random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
# Твои настройки (НЕ МЕНЯЙ, ЕСЛИ ОНИ РАБОТАЛИ)
app.config['SECRET_KEY'] = 'fishing_ultra_mega_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['PRODUCT_UPLOADS'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:8001653@localhost:5432/fishing_shop'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки почты
app.config.update(dict(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='beztele153@gmail.com',
    MAIL_PASSWORD='odax zbtq wwko veoa'
))

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- МОДЕЛИ ДАННЫХ ---

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(255))
    avatar = db.Column(db.String(255), default='default.png')
    is_admin = db.Column(db.Boolean, default=False)
    cart_items = db.relationship('Cart', backref='user', lazy=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен! Только для админов.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- РОУТЫ (ГЛАВНАЯ, АВТОРИЗАЦИЯ, РЕГИСТРАЦИЯ) ---

@app.route('/')
def index():
    # Данные для главной страницы (чтобы не было пусто)
    calendar_data = [
        {'fish': 'Щука', 'activity': 85, 'color': 'success', 'comment': 'Активный жор'},
        {'fish': 'Окунь', 'activity': 60, 'color': 'warning', 'comment': 'Берет на мормышку'},
        {'fish': 'Судак', 'activity': 20, 'color': 'danger', 'comment': 'Малоактивен'},
        {'fish': 'Лещ', 'activity': 45, 'color': 'info', 'comment': 'Ищите на глубине'}
    ]
    news_data = [
        {'title': 'Поступление спиннингов', 'date': '06.02', 'desc': 'Shimano и Daiwa уже на складе.'},
        {'title': 'Скидки на воблеры', 'date': '04.02', 'desc': '-30% на все приманки до конца недели.'}
    ]
    return render_template('index.html', calendar=calendar_data, news=news_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ВОТ ЭТОГО НЕ ХВАТАЛО, ИЗ-ЗА ЭТОГО БЫЛА ОШИБКА
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        session.pop('temp_user', None) # Очистка старой сессии
        email = request.form.get('email')
        
        # Проверка, есть ли уже такой юзер
        if User.query.filter_by(email=email).first():
            flash('Этот Email уже занят!', 'danger')
            return redirect(url_for('register'))

        otp = str(random.randint(100000, 999999))
        session['temp_user'] = {
            'username': request.form.get('username'),
            'email': email,
            'password': generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'),
            'otp': otp
        }
        
        try:
            msg = Message('Код подтверждения Fishing Shop', recipients=[email])
            msg.body = f'Ваш код для завершения регистрации: {otp}'
            mail.send(msg)
            flash('Код отправлен на почту!', 'info')
            return redirect(url_for('verify_code'))
        except Exception as e:
            flash(f'Ошибка отправки почты: {e}', 'danger')
            
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
            flash('Вы успешно зарегистрировались!', 'success')
            return redirect(url_for('login'))
        flash('Неверный код!', 'danger')
    return render_template('verify_code.html')

# --- МАГАЗИН (КАТАЛОГ, КОРЗИНА, ТОВАРЫ) ---

@app.route('/catalog')
def catalog():
    cat = request.args.get('category')
    search = request.args.get('search')
    sort = request.args.get('sort')
    
    query = Product.query
    if search:
        query = query.filter((Product.name.ilike(f'%{search}%')) | (Product.description.ilike(f'%{search}%')))
    if cat:
        query = query.filter_by(category=cat)
    
    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    
    return render_template('catalog.html', products=query.all())

@app.route('/product/<int:id>')
def product_detail(id):
    product = db.session.get(Product, id)
    if not product:
        flash('К сожалению, такой товар не найден', 'danger')
        return redirect(url_for('catalog'))
    return render_template('product_detail.html', product=product)

@app.route('/cart')
@login_required
def view_cart():
    items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        db.session.add(Cart(user_id=current_user.id, product_id=product_id, quantity=1))
    db.session.commit()
    # Возвращаемся туда, откуда пришли (каталог или товар)
    return redirect(request.referrer or url_for('view_cart'))

@app.route('/update_cart/<int:id>/<string:action>')
@login_required
def update_cart(id, action):
    item = Cart.query.filter_by(id=id, user_id=current_user.id).first()
    if item:
        if action == 'inc':
            item.quantity += 1
        elif action == 'dec':
            if item.quantity > 1:
                item.quantity -= 1
            else:
                db.session.delete(item) # Если 1 и нажали минус - удаляем
        db.session.commit()
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:id>')
@login_required
def remove_from_cart(id):
    item = Cart.query.filter_by(id=id, user_id=current_user.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('view_cart'))

# --- АДМИНКА ---

@app.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_panel():
    if request.method == 'POST':
        p_id = request.form.get('product_id')
        name = request.form.get('name')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        description = request.form.get('description')
        file = request.files.get('image')
        
        fname = None
        if file and file.filename != '':
            fname = secure_filename(file.filename)
            file.save(os.path.join(app.config['PRODUCT_UPLOADS'], fname))

        if p_id: # Редактирование существующего
            p = db.session.get(Product, int(p_id))
            if p:
                p.name = name
                p.price = price
                p.category = category
                p.description = description
                if fname: p.image = fname
                flash('Товар успешно обновлен!', 'success')
        else: # Создание нового
            new_p = Product(name=name, price=price, category=category, description=description, image=fname or 'no_image.png')
            db.session.add(new_p)
            flash('Товар успешно добавлен!', 'success')
        
        db.session.commit()
        return redirect(url_for('admin_panel'))
        
    return render_template('admin.html', products=Product.query.all())

@app.route('/admin/delete/<int:id>')
@login_required
@admin_required
def admin_delete(id):
    p = db.session.get(Product, id)
    if p:
        db.session.delete(p)
        db.session.commit()
        flash('Товар удален!', 'warning')
    return redirect(url_for('admin_panel'))

# --- СТАТИЧЕСКИЕ СТРАНИЦЫ ---

@app.route('/promotions')
def promotions(): return render_template('promotions.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/delivery')
def delivery(): return render_template('delivery.html')

@app.route('/profile')
@login_required
def profile(): return render_template('profile.html')

# --- ЗАПУСК ---

if __name__ == '__main__':
    # Создаем папки для картинок, если их нет
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PRODUCT_UPLOADS'], exist_ok=True)
    
    with app.app_context():
        db.create_all()
        # Создаем админа, если его нет
        if not User.query.filter_by(username='admin').first():
            adm = User(username='admin', email='admin@fishing.com', 
                       password=generate_password_hash('admin123', method='pbkdf2:sha256'), is_admin=True)
            db.session.add(adm)
            db.session.commit()
            print("Админ создан: login=admin, pass=admin123")
            
    app.run(debug=True)