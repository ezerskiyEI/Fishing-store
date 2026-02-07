import os, random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fishing_ultra_mega_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['PRODUCT_UPLOADS'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:8001653@localhost:5432/fishing_shop'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Почта
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

# --- МОДЕЛИ ---

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
    quantity = db.Column(db.Integer, default=1) # Поле количества
    product = db.relationship('Product')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- РОУТЫ ---

@app.route('/')
def index():
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

@app.route('/catalog')
def catalog():
    cat = request.args.get('category')
    search = request.args.get('search')
    sort = request.args.get('sort')
    query = Product.query
    if search: query = query.filter(Product.name.ilike(f'%{search}%'))
    if cat: query = query.filter_by(category=cat)
    if sort == 'price_asc': query = query.order_by(Product.price.asc())
    elif sort == 'price_desc': query = query.order_by(Product.price.desc())
    return render_template('catalog.html', products=query.all())

@app.route('/delivery')
def delivery():
    return render_template('delivery.html')

@app.route('/product/<int:id>')
def product_detail(id):
    # Используем db.session.get (для новых версий SQLAlchemy)
    product = db.session.get(Product, id)
    if not product:
        flash('К сожалению, такой товар не найден', 'danger')
        return redirect(url_for('catalog'))
    return render_template('product_detail.html', product=product)

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

        if p_id: # Редактирование
            p = db.session.get(Product, int(p_id))
            p.name, p.price, p.category, p.description = name, price, category, description
            if fname: p.image = fname
            flash('Товар обновлен')
        else: # Создание
            new_p = Product(name=name, price=price, category=category, description=description, image=fname or 'no_image.png')
            db.session.add(new_p)
            flash('Товар добавлен')
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('admin.html', products=Product.query.all())

@app.route('/admin/delete/<int:id>')
@login_required
@admin_required
def admin_delete(id):
    p = db.session.get(Product, id)
    if p: db.session.delete(p); db.session.commit(); flash('Удалено')
    return redirect(url_for('admin_panel'))

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
    if item: item.quantity += 1
    else: db.session.add(Cart(user_id=current_user.id, product_id=product_id))
    db.session.commit()
    return redirect(url_for('view_cart'))

@app.route('/update_cart/<int:id>/<string:action>')
@login_required
def update_cart(id, action):
    item = Cart.query.filter_by(id=id, user_id=current_user.id).first()
    if item:
        if action == 'inc': item.quantity += 1
        elif action == 'dec' and item.quantity > 1: item.quantity -= 1
        db.session.commit()
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:id>')
@login_required
def remove_from_cart(id):
    item = Cart.query.filter_by(id=id, user_id=current_user.id).first()
    if item: db.session.delete(item); db.session.commit()
    return redirect(url_for('view_cart'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/promotions')
def promotions(): return render_template('promotions.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/profile')
@login_required
def profile(): return render_template('profile.html')



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            adm = User(username='admin', email='admin@test.com', 
                       password=generate_password_hash('admin123'), is_admin=True)
            db.session.add(adm); db.session.commit()
    app.run(debug=True)