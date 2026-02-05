import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev_key_123'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 # Ограничение 2МБ

# --- База данных ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:8001653@localhost:5432/fishing_shop'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Настройки Почты ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'beztele153@gmail.com'
app.config['MAIL_PASSWORD'] = 'odax zbtq wwko veoa' 
app.config['MAIL_DEFAULT_SENDER'] = ('Fishing Shop', 'beztele153@gmail.com')
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Модель пользователя ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), default='default.png') # Имя файла аватара

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- МАРШРУТЫ ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.avatar = filename
                db.session.commit()
                flash('Профиль обновлен!', 'success')
                return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        otp_code = str(random.randint(100000, 999999))
        
        session['temp_user'] = {
            'username': username,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256'),
            'otp': otp_code
        }

        try:
            msg = Message('Код подтверждения', recipients=[email])
            msg.body = f'Ваш код: {otp_code}'
            mail.send(msg)
            return redirect(url_for('verify_code'))
        except:
            flash('Ошибка почты', 'danger')
    return render_template('register.html')

@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        user_code = request.form.get('code')
        temp = session.get('temp_user')
        if temp and user_code == temp['otp']:
            new_user = User(username=temp['username'], email=temp['email'], password=temp['password'])
            db.session.add(new_user)
            db.session.commit()
            session.pop('temp_user')
            flash('Регистрация завершена!', 'success')
            return redirect(url_for('login'))
        flash('Неверный код', 'danger')
    return render_template('verify_code.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Ошибка входа', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/catalog')
def catalog(): return render_template('catalog.html')
@app.route('/promotions')
def promotions(): return render_template('promotions.html')
@app.route('/about')
def about(): return render_template('about.html')

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    with app.app_context():
        db.create_all()
    app.run(debug=True)