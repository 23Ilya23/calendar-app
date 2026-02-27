from flask import Flask, request, render_template, redirect, url_for, session
import psycopg2
import datetime
import time
import calendar as cal
from functools import wraps

app = Flask(__name__, 
            template_folder='/templates', 
            static_folder='/static')

# СЕКРЕТНЫЙ КЛЮЧ
app.secret_key = 'acb29987-9f0b-45f0-853b-542c65e869e2!lKsdzGfwA9Q2JSg7L4rfjnsGJpThHnKGkhi9xD0aWtc='

# НАСТРОЙКИ СЕССИИ
app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,
    SESSION_REFRESH_EACH_REQUEST=True
)

# ============ ТЕЛЕГРАМ БОТ ============
TELEGRAM_TOKEN = "8461027814:AAG5lFd_lE_cU1JqXxfWUej_K1A8HuHp0CY"
TELEGRAM_CHAT_ID = "1085743146"

def send_telegram(message):
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=data)
        print("📱 Telegram уведомление отправлено")
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")

# ============ АДМИН ДАННЫЕ ============
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "vT%hkighrihjh%rthjrthij145tr$%%"

time.sleep(10)

# ============ ПОДКЛЮЧЕНИЕ К БД ============
def get_db():
    for i in range(10):
        try:
            conn = psycopg2.connect(
                host="postgres", port="5432", dbname="calendar_db",
                user="postgres", password="123"
            )
            return conn
        except:
            time.sleep(2)
    return None

# ============ ПРОВЕРКА БЛОКИРОВКИ ============
def check_blocked_global():
    if 'user_id' in session and session.get('role') != 'admin':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT is_blocked FROM users WHERE id = %s", (session['user_id'],))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result[0]:
            return True
    return False

@app.before_request
def before_request():
    allowed_pages = ['blocked_page', 'logout', 'static', 'student_page']
    
    if check_blocked_global():
        if request.endpoint not in allowed_pages:
            return redirect(url_for('blocked_page'))

# ============ ИНИЦИАЛИЗАЦИЯ БД ============
conn = get_db()
cur = conn.cursor()

# Добавляем поле block_reason если его нет
try:
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS block_reason TEXT")
    conn.commit()
    print("✅ Поле block_reason добавлено")
except:
    conn.rollback()

cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        role VARCHAR(20) DEFAULT 'student',
        is_blocked BOOLEAN DEFAULT FALSE,
        block_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS calendar (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        username VARCHAR(50) NOT NULL,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        user_role VARCHAR(20) NOT NULL,
        event_date DATE NOT NULL,
        event_time VARCHAR(5),
        title VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Таблица заявок (zayvka)
cur.execute("""
    CREATE TABLE IF NOT EXISTS zayvka (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        username VARCHAR(50) NOT NULL,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        email VARCHAR(100),
        user_role VARCHAR(20) NOT NULL,
        event_date DATE NOT NULL,
        event_time VARCHAR(5),
        title VARCHAR(255) NOT NULL,
        description TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ Таблица zayvka создана")

# Создаём админа
try:
    cur.execute("SELECT * FROM users WHERE username = %s", (ADMIN_USERNAME,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, email, first_name, last_name, role, is_blocked) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (ADMIN_USERNAME, ADMIN_PASSWORD, 'admin@calendar.ru', 'Admin', 'Adminov', 'admin', False))
        conn.commit()
        print("✅ Админ создан!")
except:
    conn.rollback()

conn.commit()
cur.close()
conn.close()
print("✅ База готова!")

# ============ МАРШРУТЫ ============

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('student_page'))
    return redirect(url_for('login'))

@app.route('/check_status')
def check_status():
    if 'user_id' not in session:
        return {'is_blocked': False, 'logged_in': False}
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_blocked FROM users WHERE id = %s", (session['user_id'],))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result:
        return {'is_blocked': result[0]}
    return {'is_blocked': False}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close(); conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[3]
            session['first_name'] = user[4]
            session['last_name'] = user[5]
            session['role'] = user[6]
            
            if user[6] == 'admin':
                return redirect(url_for('admin_panel'))
            
            # Проверяем, есть ли события в календаре от этого пользователя
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM calendar WHERE user_id = %s", (user[0],))
            events_count = cur.fetchone()[0]
            cur.close(); conn.close()
            
            if events_count > 0:
                return redirect(url_for('calendar_page'))
            else:
                return redirect(url_for('student_page'))
        else:
            return render_template('login.html', error="❌ Неверный логин или пароль")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username'].lower()
        password = request.form['password']
        email = request.form['email']
        role = request.form.get('role', 'student')
        
        try:
            conn = get_db()
            cur = conn.cursor()
            
            # Создаём пользователя (НЕ блокируем)
            cur.execute("""
                INSERT INTO users (username, password, email, first_name, last_name, role, is_blocked) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (username, password, email, first_name, last_name, role, False))
            
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Сразу создаём сессию
            session['user_id'] = user_id
            session['username'] = username
            session['email'] = email
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['role'] = role
            
            cur.close(); conn.close()
            
            # Уведомление админу
            role_emoji = "👨‍🎓" if role == 'student' else "👨‍🏫"
            role_name = "Студент" if role == 'student' else "Преподаватель"
            
            message = f"""
📢 <b>НОВАЯ РЕГИСТРАЦИЯ! ({role_name})</b>

{role_emoji} <b>Роль:</b> {role_name}
👤 <b>Имя:</b> {first_name} {last_name}
🔑 <b>Логин:</b> {username}
📧 <b>Email:</b> {email}
🆔 <b>ID:</b> {user_id}

🔗 <a href="http://localhost:5000/admin_zayvka">Перейти к заявкам</a>
            """
            send_telegram(message)
            
            # Перенаправляем на страницу заявок
            return redirect(url_for('student_page'))
            
        except psycopg2.IntegrityError:
            return render_template('register.html', error="❌ Пользователь уже существует")
        except Exception as e:
            return render_template('register.html', error=f"❌ Ошибка: {e}")
    
    return render_template('register.html')

@app.route('/student')
def student_page():
    if 'user_id' not in session or session['role'] == 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # АВТОМАТИЧЕСКИ СОЗДАЁМ ЗАЯВКУ НА СЕГОДНЯ (если ещё нет)
    today = datetime.date.today()
    today_str = today.isoformat()
    
    # Проверяем, есть ли уже заявка на сегодня
    cur.execute("""
        SELECT COUNT(*) FROM zayvka 
        WHERE user_id = %s AND event_date = %s
    """, (session['user_id'], today_str))
    
    if cur.fetchone()[0] == 0:
        # Создаём автоматическую заявку
        title = f"Заявка на {today_str}"
        cur.execute("""
            INSERT INTO zayvka (user_id, username, first_name, last_name, email, user_role, event_date, event_time, title, description, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], session['username'], session['first_name'], session['last_name'],
              session['email'], session['role'], today_str, '12:00', title, '', 'pending'))
        conn.commit()
        
        # Уведомление админу
        role_emoji = "👨‍🏫" if session['role'] == 'teacher' else "👨‍🎓"
        message = f"""
📝 <b>АВТОМАТИЧЕСКАЯ ЗАЯВКА!</b>

{role_emoji} <b>От:</b> {session['first_name']} {session['last_name']}
📆 <b>Дата:</b> {today_str} 12:00

🔗 <a href="http://localhost:5000/admin_zayvka">Рассмотреть</a>
        """
        send_telegram(message)
    
    # Получаем все заявки пользователя
    cur.execute("SELECT * FROM zayvka WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    zayvki = cur.fetchall()
    cur.close(); conn.close()
    
    return render_template('student.html',
        zayvki=zayvki,
        first_name=session['first_name'],
        last_name=session['last_name'],
        username=session['username'],
        email=session['email'],
        today=today_str
    )

@app.route('/calendar')
def calendar_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Проверяем, есть ли события в календаре от этого пользователя
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM calendar WHERE user_id = %s", (session['user_id'],))
    events_count = cur.fetchone()[0]
    
    if events_count == 0 and session['role'] != 'admin':
        cur.close(); conn.close()
        return redirect(url_for('student_page', message="❌ Сначала нужно получить одобрение заявки"))
    
    # Получаем месяц и год из запроса
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    if not month or not year:
        today = datetime.date.today()
        month = today.month
        year = today.year
    
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                   'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    month_name = month_names[month - 1]
    
    cal_grid = cal.monthcalendar(year, month)
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    cur.execute("""
        SELECT * FROM calendar 
        WHERE event_date >= %s AND event_date < %s
        ORDER BY event_date, event_time
    """, (start_date, end_date))
    month_events = cur.fetchall()
    
    day_events = {}
    for event in month_events:
        date_str = event[7]
        if ':' not in date_str:
            try:
                event_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                day = event_date.day
                
                if day not in day_events:
                    day_events[day] = []
                day_events[day].append({
                    'title': event[9],
                    'description': event[10],
                    'time': event[8] or '00:00',
                    'author': f"{event[3]} {event[4]}",
                    'role': event[5]
                })
            except:
                pass
    
    today = datetime.date.today().isoformat()
    cur.execute("SELECT * FROM calendar WHERE event_date >= %s ORDER BY event_date", (today,))
    all_events = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) FROM calendar WHERE user_id = %s", (session['user_id'],))
    my_events = cur.fetchone()[0]
    cur.close(); conn.close()
    
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    return render_template('calendar.html',
        events=all_events,
        my_events=my_events,
        other_events=len(all_events)-my_events,
        day_events=day_events,
        calendar_grid=cal_grid,
        month_name=month_name,
        month=month,
        year=year,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        user_id=session['user_id'],
        first_name=session['first_name'],
        last_name=session['last_name'],
        username=session['username'],
        email=session['email'],
        role=session['role'],
        today=today
    )

@app.route('/add_event', methods=['POST'])
def add_event():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    date_str = request.form['date']
    
    try:
        event_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return redirect(url_for('calendar_page', message="❌ Неправильный формат даты"))
    
    moscow_tz = datetime.timezone(datetime.timedelta(hours=3))
    moscow_now = datetime.datetime.now(moscow_tz).date()
    
    if event_date < moscow_now:
        return redirect(url_for('calendar_page', message="❌ Нельзя добавлять события в прошлом!"))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO calendar (user_id, username, first_name, last_name, user_role, event_date, event_time, title, description) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (session['user_id'], session['username'], session['first_name'], session['last_name'],
          session['role'], date_str, request.form['time'], request.form['title'], request.form['description']))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('calendar_page', message="✅ Событие добавлено!"))

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    if session['role'] == 'admin':
        cur.execute("DELETE FROM calendar WHERE id = %s", (event_id,))
    else:
        cur.execute("DELETE FROM calendar WHERE id = %s AND user_id = %s", (event_id, session['user_id']))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('calendar_page', message="✅ Событие удалено!"))

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM users WHERE role='student' OR role='teacher' ORDER BY created_at DESC")
    users = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) FROM users WHERE role='student' OR role='teacher'")
    total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM users WHERE role='student' AND is_blocked=True")
    blocked_students = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM users WHERE role='teacher' AND is_blocked=True")
    blocked_teachers = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM users WHERE (role='student' OR role='teacher') AND is_blocked=False")
    active = cur.fetchone()[0]
    
    cur.close(); conn.close()
    
    return render_template('admin.html',
        users=users,
        total=total,
        blocked_students=blocked_students,
        blocked_teachers=blocked_teachers,
        blocked=blocked_students + blocked_teachers,
        active=active,
        username=session['username']
    )

@app.route('/admin_block/<int:user_id>', methods=['POST'])
def admin_block(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    reason = request.form.get('reason', '')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_blocked=True, block_reason=%s WHERE id=%s", (reason, user_id))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_unlock/<int:user_id>')
def admin_unlock(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_blocked=False, block_reason=NULL WHERE id=%s", (user_id,))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_delete/<int:user_id>')
def admin_delete(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_delete_all_students')
def admin_delete_all_students():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM calendar WHERE user_role='student' OR user_role='teacher'")
    cur.execute("DELETE FROM users WHERE role='student' OR role='teacher'")
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_delete_all_events')
def admin_delete_all_events():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM calendar")
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_zayvka')
def admin_zayvka():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM zayvka ORDER BY created_at DESC")
    zayvki = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM zayvka")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM zayvka WHERE status='pending'")
    pending = cur.fetchone()[0]
    cur.close(); conn.close()
    
    return render_template('admin_zayvka.html',
        zayvki=zayvki,
        total=total,
        pending=pending,
        username=session['username']
    )

@app.route('/admin_zayvka_approve/<int:zayvka_id>')
def admin_zayvka_approve(zayvka_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM zayvka WHERE id = %s", (zayvka_id,))
    z = cur.fetchone()
    
    if z:
        # Сразу добавляем в календарь
        cur.execute("""
            INSERT INTO calendar (user_id, username, first_name, last_name, user_role, event_date, event_time, title, description) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (z[1], z[2], z[3], z[4], z[6], z[7], z[8], z[9], z[10]))
        
        # Удаляем заявку (она больше не нужна)
        cur.execute("DELETE FROM zayvka WHERE id = %s", (zayvka_id,))
        conn.commit()
    
    cur.close(); conn.close()
    return redirect(url_for('admin_zayvka'))

@app.route('/admin_zayvka_reject/<int:zayvka_id>')
def admin_zayvka_reject(zayvka_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM zayvka WHERE id = %s", (zayvka_id,))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('admin_zayvka'))

@app.route('/admin_zayvka_reject_all')
def admin_zayvka_reject_all():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM zayvka WHERE status='pending'")
    conn.commit()
    cur.close(); conn.close()
    
    send_telegram("🗑️ <b>Все заявки удалены администратором</b>")
    return redirect(url_for('admin_zayvka'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    print("🚀 КАЛЕНДАРЬ ЗАПУЩЕН!")
    print("📅 http://localhost:5000")
    print("👑 Админ: admin / спец.пароль")
    app.run(host='0.0.0.0', port=5000, debug=True)