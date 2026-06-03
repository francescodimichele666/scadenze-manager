import os
import smtplib
import threading
import time
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')

# Render.com usa "postgres://" ma SQLAlchemy richiede "postgresql://"
_db_url = os.getenv('DATABASE_URL', 'sqlite:///scadenze.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── Models ─────────────────────────────────────────────────────────────────

class Category(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    name  = db.Column(db.String(100), nullable=False)
    icon  = db.Column(db.String(60),  default='bi-tag-fill')
    color = db.Column(db.String(20),  default='#6366F1')
    scadenze = db.relationship('Scadenza', backref='category', lazy=True)


class Scadenza(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    category_id   = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    amount        = db.Column(db.Float, nullable=True)
    due_date      = db.Column(db.Date, nullable=False)
    recurrence    = db.Column(db.String(20), default='none')
    status        = db.Column(db.String(20), default='pending')
    alert_days    = db.Column(db.Integer, default=7)
    notes         = db.Column(db.Text, default='')
    alert_sent_date = db.Column(db.Date, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def days_remaining(self):
        return (self.due_date - date.today()).days

    @property
    def urgency(self):
        if self.status == 'paid':    return 'paid'
        if self.days_remaining < 0:  return 'overdue'
        if self.days_remaining <= 7: return 'soon'
        return 'ok'


class Setting(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')


# ── Settings helpers ────────────────────────────────────────────────────────

def get_setting(key, default=''):
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default

def set_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


# ── DB init ─────────────────────────────────────────────────────────────────

DEFAULT_CATEGORIES = [
    ('Bollette',      'bi-lightning-charge-fill', '#F59E0B'),
    ('Assicurazioni', 'bi-shield-fill-check',     '#10B981'),
    ('Auto',          'bi-car-front-fill',         '#3B82F6'),
    ('Condominio',    'bi-buildings-fill',          '#8B5CF6'),
    ('Abbonamenti',   'bi-credit-card-fill',        '#EC4899'),
    ('Tasse',         'bi-bank',                    '#EF4444'),
    ('Mutuo/Affitto', 'bi-house-fill',              '#F97316'),
    ('Altro',         'bi-three-dots',              '#6B7280'),
]

def init_db():
    db.create_all()
    if Category.query.count() == 0:
        for name, icon, color in DEFAULT_CATEGORIES:
            db.session.add(Category(name=name, icon=icon, color=color))
        db.session.commit()


# ── Email ───────────────────────────────────────────────────────────────────

def _smtp_send(to, subject, html_body):
    """Invia email via smtplib usando le impostazioni salvate nel DB."""
    server   = get_setting('mail_server',   'smtp.gmail.com')
    port     = int(get_setting('mail_port', '587'))
    username = get_setting('mail_username', '')
    password = get_setting('mail_password', '')
    use_tls  = get_setting('mail_tls', 'true') == 'true'

    if not username or not password:
        raise ValueError("Credenziali email non configurate nelle Impostazioni.")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'ScadenzeManager <{username}>'
    msg['To']      = to
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    with smtplib.SMTP(server, port, timeout=15) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.sendmail(username, to, msg.as_string())


def check_and_send_alerts():
    with app.app_context():
        recipient = get_setting('alert_email', '')
        if not recipient:
            return

        today   = date.today()
        pending = Scadenza.query.filter_by(status='pending').all()
        to_alert = []

        for s in pending:
            if s.alert_sent_date == today:
                continue
            if s.days_remaining <= s.alert_days:
                to_alert.append(s)
                s.alert_sent_date = today

        if to_alert:
            db.session.commit()
            try:
                _send_alert_email(recipient, to_alert)
            except Exception as e:
                print(f'[Alert email error] {e}')


def _send_alert_email(recipient, scadenze_list):
    today_fmt = date.today().strftime('%d/%m/%Y')
    rows = ''
    for s in sorted(scadenze_list, key=lambda x: x.due_date):
        dr = s.days_remaining
        if dr < 0:
            urgency_html = f'<span style="color:#DC2626;font-weight:600;">Scaduta da {abs(dr)}gg</span>'
        elif dr == 0:
            urgency_html = '<span style="color:#DC2626;font-weight:600;">OGGI!</span>'
        else:
            urgency_html = f'<span style="color:#D97706;font-weight:600;">Tra {dr} giorni</span>'
        amount_str = f'€ {s.amount:,.2f}' if s.amount else '—'
        rows += f'''
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #F1F5F9;">{s.title}</td>
          <td style="padding:12px 16px;border-bottom:1px solid #F1F5F9;">{s.category.name}</td>
          <td style="padding:12px 16px;border-bottom:1px solid #F1F5F9;">{s.due_date.strftime("%d/%m/%Y")}</td>
          <td style="padding:12px 16px;border-bottom:1px solid #F1F5F9;font-weight:600;">{amount_str}</td>
          <td style="padding:12px 16px;border-bottom:1px solid #F1F5F9;">{urgency_html}</td>
        </tr>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:24px;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:620px;margin:auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#6366F1 0%,#8B5CF6 100%);padding:32px 24px;text-align:center;">
    <div style="font-size:36px;">⏰</div>
    <h1 style="color:white;margin:8px 0 0;font-size:22px;font-weight:700;">Scadenze in Arrivo</h1>
    <p style="color:rgba(255,255,255,0.75);margin:6px 0 0;font-size:14px;">{today_fmt}</p>
  </div>
  <div style="padding:28px 24px;">
    <p style="color:#374151;margin:0 0 20px;font-size:15px;">
      Hai <strong style="color:#6366F1;">{len(scadenze_list)}</strong> scadenze che richiedono attenzione:
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#374151;">
      <thead>
        <tr style="background:#F8FAFC;">
          <th style="padding:10px 16px;text-align:left;font-weight:600;color:#6B7280;border-bottom:2px solid #E2E8F0;">Titolo</th>
          <th style="padding:10px 16px;text-align:left;font-weight:600;color:#6B7280;border-bottom:2px solid #E2E8F0;">Categoria</th>
          <th style="padding:10px 16px;text-align:left;font-weight:600;color:#6B7280;border-bottom:2px solid #E2E8F0;">Scadenza</th>
          <th style="padding:10px 16px;text-align:left;font-weight:600;color:#6B7280;border-bottom:2px solid #E2E8F0;">Importo</th>
          <th style="padding:10px 16px;text-align:left;font-weight:600;color:#6B7280;border-bottom:2px solid #E2E8F0;">Stato</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div style="background:#F8FAFC;padding:20px 24px;text-align:center;color:#9CA3AF;font-size:12px;border-top:1px solid #E2E8F0;">
    ScadenzeManager — Gestione Scadenze e Pagamenti
  </div>
</div>
</body></html>'''

    _smtp_send(
        to      = recipient,
        subject = f'⏰ {len(scadenze_list)} scadenze in arrivo — ScadenzeManager',
        html_body = html,
    )


# ── Background scheduler ────────────────────────────────────────────────────

def _scheduler_loop():
    while True:
        try:
            check_and_send_alerts()
        except Exception as e:
            print(f'[Scheduler] {e}')
        time.sleep(3600)


# ── Routes: Dashboard ───────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    today = date.today()

    overdue = Scadenza.query.filter(
        Scadenza.status == 'pending',
        Scadenza.due_date < today
    ).count()

    next7 = Scadenza.query.filter(
        Scadenza.status == 'pending',
        Scadenza.due_date >= today,
        Scadenza.due_date <= today + timedelta(days=7)
    ).count()

    next30 = Scadenza.query.filter(
        Scadenza.status == 'pending',
        Scadenza.due_date >= today,
        Scadenza.due_date <= today + timedelta(days=30)
    ).all()

    paid_this_month = Scadenza.query.filter(
        Scadenza.status == 'paid',
        Scadenza.due_date >= today.replace(day=1),
        Scadenza.due_date <= today
    ).count()

    upcoming = Scadenza.query.filter(
        Scadenza.status == 'pending',
        Scadenza.due_date >= today - timedelta(days=30),
    ).order_by(Scadenza.due_date).limit(12).all()

    return render_template('dashboard.html',
        today=today,
        overdue=overdue,
        next7=next7,
        month_count=len(next30),
        month_total=sum(s.amount or 0 for s in next30),
        paid_this_month=paid_this_month,
        upcoming=upcoming,
    )


# ── Routes: Scadenze ────────────────────────────────────────────────────────

@app.route('/scadenze')
def scadenze_list():
    cat_id  = request.args.get('category', type=int)
    status  = request.args.get('status', '')
    period  = request.args.get('period', '')
    today   = date.today()

    q = Scadenza.query
    if cat_id:   q = q.filter_by(category_id=cat_id)
    if status:   q = q.filter_by(status=status)

    if period == 'overdue':
        q = q.filter(Scadenza.due_date < today, Scadenza.status == 'pending')
    elif period == 'week':
        q = q.filter(Scadenza.due_date >= today, Scadenza.due_date <= today + timedelta(days=7))
    elif period == 'month':
        q = q.filter(Scadenza.due_date >= today, Scadenza.due_date <= today + timedelta(days=30))

    scadenze   = q.order_by(Scadenza.due_date).all()
    categories = Category.query.all()

    return render_template('scadenze/list.html',
        scadenze=scadenze, categories=categories,
        today=today,
        selected_cat=cat_id, selected_status=status, selected_period=period,
    )


@app.route('/scadenze/add', methods=['GET', 'POST'])
def scadenza_add():
    categories = Category.query.all()
    if request.method == 'POST':
        s = Scadenza(
            title       = request.form['title'],
            category_id = int(request.form['category_id']),
            amount      = float(request.form['amount']) if request.form.get('amount') else None,
            due_date    = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
            recurrence  = request.form.get('recurrence', 'none'),
            status      = request.form.get('status', 'pending'),
            alert_days  = int(request.form.get('alert_days', 7)),
            notes       = request.form.get('notes', ''),
        )
        db.session.add(s)
        db.session.commit()
        flash('Scadenza aggiunta con successo!', 'success')
        return redirect(url_for('dashboard'))
    default_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template('scadenze/form.html',
        categories=categories, scadenza=None, default_date=default_date, today=date.today())


@app.route('/scadenze/<int:id>/edit', methods=['GET', 'POST'])
def scadenza_edit(id):
    s          = Scadenza.query.get_or_404(id)
    categories = Category.query.all()
    if request.method == 'POST':
        s.title       = request.form['title']
        s.category_id = int(request.form['category_id'])
        s.amount      = float(request.form['amount']) if request.form.get('amount') else None
        s.due_date    = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
        s.recurrence  = request.form.get('recurrence', 'none')
        s.status      = request.form.get('status', 'pending')
        s.alert_days  = int(request.form.get('alert_days', 7))
        s.notes       = request.form.get('notes', '')
        db.session.commit()
        flash('Scadenza aggiornata!', 'success')
        return redirect(url_for('scadenze_list'))
    return render_template('scadenze/form.html',
        categories=categories, scadenza=s,
        default_date=s.due_date.strftime('%Y-%m-%d'), today=date.today())


@app.route('/scadenze/<int:id>/delete', methods=['POST'])
def scadenza_delete(id):
    s = Scadenza.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash('Scadenza eliminata.', 'info')
    return redirect(url_for('scadenze_list'))


@app.route('/scadenze/<int:id>/mark-paid', methods=['POST'])
def scadenza_mark_paid(id):
    s        = Scadenza.query.get_or_404(id)
    s.status = 'paid'

    if s.recurrence != 'none':
        delta_map = {
            'monthly':   timedelta(days=30),
            'quarterly': timedelta(days=90),
            'biannual':  timedelta(days=180),
            'annual':    timedelta(days=365),
        }
        delta = delta_map.get(s.recurrence)
        if delta:
            db.session.add(Scadenza(
                title=s.title, category_id=s.category_id,
                amount=s.amount, due_date=s.due_date + delta,
                recurrence=s.recurrence, status='pending',
                alert_days=s.alert_days, notes=s.notes,
            ))

    db.session.commit()
    flash(f'"{s.title}" segnata come pagata! ✓', 'success')
    return redirect(request.referrer or url_for('dashboard'))


# ── Routes: Settings ────────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        keys = ['mail_server', 'mail_port', 'mail_username',
                'mail_password', 'mail_tls', 'alert_email']
        for key in keys:
            set_setting(key, request.form.get(key, ''))
        flash('Impostazioni salvate!', 'success')
        return redirect(url_for('settings'))

    cfg = {k: get_setting(k, d) for k, d in [
        ('mail_server',   'smtp.gmail.com'),
        ('mail_port',     '587'),
        ('mail_username', ''),
        ('mail_password', ''),
        ('mail_tls',      'true'),
        ('alert_email',   ''),
    ]}
    categories = Category.query.all()
    return render_template('settings.html', cfg=cfg, categories=categories, today=date.today())


@app.route('/test-email', methods=['POST'])
def test_email():
    recipient = get_setting('alert_email', '')
    if not recipient:
        flash('Configura prima l\'email di destinazione nelle impostazioni!', 'danger')
        return redirect(url_for('settings'))
    try:
        _smtp_send(
            to        = recipient,
            subject   = '✅ Test — ScadenzeManager funziona!',
            html_body = '''
            <div style="font-family:Arial,sans-serif;padding:32px;background:#F1F5F9;">
              <div style="max-width:480px;margin:auto;background:white;border-radius:16px;padding:32px;text-align:center;">
                <div style="font-size:48px;">✅</div>
                <h2 style="color:#6366F1;margin:16px 0 8px;">Email configurata correttamente!</h2>
                <p style="color:#64748B;">ScadenzeManager invierà gli alert a questo indirizzo.</p>
              </div>
            </div>''',
        )
        flash(f'Email di test inviata a {recipient} ✓', 'success')
    except Exception as e:
        flash(f'Errore invio email: {str(e)}', 'danger')
    return redirect(url_for('settings'))


@app.route('/trigger-alerts')
def trigger_alerts():
    check_and_send_alerts()
    flash('Controllo alert eseguito!', 'info')
    return redirect(url_for('dashboard'))


# ── Category management ─────────────────────────────────────────────────────

@app.route('/categories/add', methods=['POST'])
def category_add():
    name  = request.form.get('name', '').strip()
    icon  = request.form.get('icon', 'bi-tag-fill')
    color = request.form.get('color', '#6366F1')
    if name:
        db.session.add(Category(name=name, icon=icon, color=color))
        db.session.commit()
        flash(f'Categoria "{name}" aggiunta!', 'success')
    return redirect(url_for('settings'))


@app.route('/categories/<int:id>/delete', methods=['POST'])
def category_delete(id):
    cat = Category.query.get_or_404(id)
    if Scadenza.query.filter_by(category_id=id).count() > 0:
        flash('Non puoi eliminare una categoria con scadenze associate.', 'danger')
    else:
        db.session.delete(cat)
        db.session.commit()
        flash('Categoria eliminata.', 'info')
    return redirect(url_for('settings'))


# ── Calendar ────────────────────────────────────────────────────────────────

@app.route('/calendar')
def calendar():
    return render_template('calendar.html', today=date.today())


# ── API ─────────────────────────────────────────────────────────────────────

@app.route('/api/scadenze')
def api_scadenze():
    show_paid = request.args.get('paid', 'false') == 'true'
    q = Scadenza.query.filter(Scadenza.status != 'cancelled')
    if not show_paid:
        q = q.filter(Scadenza.status == 'pending')
    scadenze = q.all()
    events   = []
    for s in scadenze:
        dr = s.days_remaining
        if s.status == 'paid':
            color = '#10B981'
        elif dr < 0:
            color = '#EF4444'
        elif dr <= 7:
            color = '#F59E0B'
        else:
            color = '#6366F1'
        events.append({
            'id':    s.id,
            'title': s.title + (f' €{s.amount:.0f}' if s.amount else ''),
            'start': s.due_date.isoformat(),
            'color': color,
            'url':   url_for('scadenza_edit', id=s.id),
            'extendedProps': {
                'status':   s.status,
                'amount':   s.amount,
                'category': s.category.name,
                'notes':    s.notes or '',
            }
        })
    return jsonify(events)


# ── App start ───────────────────────────────────────────────────────────────

with app.app_context():
    init_db()

_t = threading.Thread(target=_scheduler_loop, daemon=True)
_t.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
