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
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CMR PAI</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg bg-white shadow-sm">
  <div class="container">
    <a class="navbar-brand fw-semibold" href="{{ url_for('dashboard') }}">CMR PAI</a>
    <div class="d-flex">
      {% if current_user.is_authenticated %}
        <span class="me-3">👤 {{ current_user.username }}</span>
        <a class="btn btn-outline-dark btn-sm" href="{{ url_for('logout') }}">Salir</a>
      {% else %}
        <a class="btn btn-primary btn-sm" href="{{ url_for('login') }}">Ingresar</a>
      {% endif %}
    </div>
  </div>
</nav>
<div class="container py-4">
  {% with messages=get_flashed_messages(with_categories=true) %}
    {% for c,m in messages %}<div class="alert alert-{{c}}">{{m}}</div>{% endfor %}
  {% endwith %}
  {% block content %}{% endblock %}
</div>
</body></html>
"""

LOGIN_TPL = """
{% extends LAYOUT %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card p-4">
      <h4 class="mb-3">Ingresar</h4>
      <form method="post">
        <div class="mb-3"><label class="form-label">Usuario</label><input class="form-control" name="username" required></div>
        <div class="mb-3"><label class="form-label">Contraseña</label><input type="password" class="form-control" name="password" required></div>
        <button class="btn btn-primary w-100">Entrar</button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
"""

DASHBOARD_TPL = """
{% extends LAYOUT %}
{% block content %}
<h3 class="mb-4">Panel CMR PAI</h3>
<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card p-3"><div class="text-muted small">NNA activos</div><div class="fs-3 fw-bold">{{ kpis.nna_activos }}</div></div></div>
  <div class="col-md-3"><div class="card p-3"><div class="text-muted small">Atenciones (mes)</div><div class="fs-3 fw-bold">{{ kpis.att_mes }}</div></div></div>
  <div class="col-md-3"><div class="card p-3"><div class="text-muted small">Atenciones (12m)</div><div class="fs-3 fw-bold">{{ kpis.att_12m }}</div></div></div>
</div>
<div class="card p-3">
  <h6>Serie de atenciones (últimos 12 meses)</h6>
  <canvas id="serie"></canvas>
</div>
<script>
  const labels = {{ labels|tojson }};
  const values = {{ values|tojson }};
  new Chart(document.getElementById('serie'), { type:'line', data:{ labels, datasets:[{ label:'Atenciones', data: values }] }, options:{ responsive:true } });
</script>
{% endblock %}
"""

NNA_LIST_TPL = """
{% extends LAYOUT %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4 class="m-0">NNA</h4>
  <a class="btn btn-primary" href="{{ url_for('nna_new') }}">Nuevo</a>
</div>
<div class="card p-3">
<table class="table align-middle"><thead><tr><th>Nombre</th><th>RUT</th><th>Ingreso</th><th>Estado</th></tr></thead>
<tbody>
{% for n in nnas %}<tr><td>{{ n.nombre }}</td><td>{{ n.rut or '—' }}</td><td>{{ n.fecha_ingreso }}</td><td>{{ n.estado }}</td></tr>{% endfor %}
</tbody></table>
</div>
{% endblock %}
"""

NNA_NEW_TPL = """
{% extends LAYOUT %}
{% block content %}
<h4 class="mb-3">Nuevo NNA</h4>
<div class="card p-3">
  <form method="post" class="row g-3">
    <div class="col-md-6"><label class="form-label">Nombre*</label><input class="form-control" name="nombre" required></div>
    <div class="col-md-3"><label class="form-label">RUT</label><input class="form-control" name="rut"></div>
    <div class="col-md-3"><label class="form-label">Estado</label><select class="form-select" name="estado"><option>activo</option><option>egresado</option></select></div>
    <div class="col-12"><button class="btn btn-primary">Guardar</button> <a href="{{ url_for('nna_list') }}" class="btn btn-light">Cancelar</a></div>
  </form>
</div>
{% endblock %}
"""

# -------------------- Rutas --------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username'].strip()).first()
        if u and u.check_password(request.form['password']):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('Credenciales inválidas', 'danger')
    return render_template_string(LOGIN_TPL, LAYOUT=LAYOUT)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    today = date.today()
    first_day_month = date(today.year, today.month, 1)

    nna_activos = NNA.query.filter_by(estado='activo').count()
    att_mes = Atencion.query.filter(Atencion.fecha >= first_day_month).count()
    att_12m = Atencion.query.filter(Atencion.fecha >= first_day_month - timedelta(days=365)).count()

    # Serie de 12 meses
    labels, values = [], []
    for i in range(12):
        start = date(today.year, today.month, 1) - timedelta(days=30*i)
        end = start + timedelta(days=30)
        c = Atencion.query.filter(Atencion.fecha>=start, Atencion.fecha<end).count()
        labels.append(start.strftime('%b %Y'))
        values.append(c)
    labels.reverse(); values.reverse()

    return render_template_string(DASHBOARD_TPL, LAYOUT=LAYOUT,
        kpis={'nna_activos':nna_activos,'att_mes':att_mes,'att_12m':att_12m},
        labels=labels, values=values)

@app.route('/nna')
@login_required
def nna_list():
    nnas = NNA.query.order_by(NNA.fecha_ingreso.desc()).all()
    return render_template_string(NNA_LIST_TPL, LAYOUT=LAYOUT, nnas=nnas)

@app.route('/nna/nuevo', methods=['GET','POST'])
@login_required
def nna_new():
    if request.method == 'POST':
        n = NNA(nombre=request.form['nombre'], rut=request.form.get('rut') or None, estado=request.form.get('estado') or 'activo')
        db.session.add(n)
        db.session.commit()
        flash('NNA creado', 'success')
        return redirect(url_for('nna_list'))
    return render_template_string(NNA_NEW_TPL, LAYOUT=LAYOUT)

# -------------------- Main --------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
