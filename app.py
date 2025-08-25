import os
from datetime import date, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- Config --------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'changeme')

# DATABASE_URL (Neon / Render PostgreSQL). Fallback a sqlite demo si no hay DB_URL
DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///cmr_pai_demo.db')
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# -------------------- Modelos --------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='staff')

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)

class NNA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    rut = db.Column(db.String(20))
    fecha_ingreso = db.Column(db.Date, default=date.today)
    estado = db.Column(db.String(20), default='activo')  # activo | egresado

class Atencion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=date.today)
    tipo = db.Column(db.String(50))  # psicologia | terapia_ocupacional | social
    profesional = db.Column(db.String(200))
    nna_id = db.Column(db.Integer, db.ForeignKey('nna.id'), nullable=False)
    nna = db.relationship('NNA', backref='atenciones')

# -------------------- Carga user --------------------
@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

# -------------------- Bootstrap DB + Admin --------------------
with app.app_context():
    db.create_all()
    admin_user = os.environ.get('ADMIN_USER')
    admin_pass = os.environ.get('ADMIN_PASS')
    if admin_user and admin_pass and not User.query.filter_by(username=admin_user).first():
        u = User(username=admin_user, role='admin')
        u.set_password(admin_pass)
        db.session.add(u)
        db.session.commit()
        print('✅ Usuario admin creado desde variables de entorno')

# -------------------- Templates --------------------
LAYOUT = """
<!
