from flask import Flask, request, render_template, redirect, url_for, session, jsonify
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
    allowed_pages = ['blocked_page', 'logout', 'static']
    
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

# Добавляем поле is_zayvka если его нет (КАК VARCHAR)
try:
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_zayvka VARCHAR(10) DEFAULT 'false'")
    conn.commit()
    print("✅ Поле is_zayvka добавлено как VARCHAR")
except Exception as e:
    print(f"Ошибка при добавлении is_zayvka: {e}")
    conn.rollback()

# Таблица пользователей
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
        is_zayvka VARCHAR(10) DEFAULT 'false',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ Таблица users создана")

# Таблица календаря
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
print("✅ Таблица calendar создана")

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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ Таблица zayvka создана")

# Создаём админа
try:
    cur.execute("SELECT * FROM users WHERE username = %s", (ADMIN_USERNAME,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, email, first_name, last_name, role, is_blocked, is_zayvka) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (ADMIN_USERNAME, ADMIN_PASSWORD, 'admin@calendar.ru', 'Admin', 'Adminov', 'admin', False, 'false'))
        conn.commit()
        print("✅ Админ создан!")
except Exception as e:
    print(f"Ошибка при создании админа: {e}")
    conn.rollback()

# Обновляем существующих пользователей, добавляя is_zayvka = 'false'
try:
    cur.execute("UPDATE users SET is_zayvka = 'false' WHERE is_zayvka IS NULL")
    conn.commit()
    print("✅ Существующие пользователи обновлены")
except Exception as e:
    print(f"Ошибка при обновлении пользователей: {e}")
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

@app.route('/check_status_zayvka')
def check_status_zayvka():
    if 'user_id' not in session:
        return {'is_zayvka': 'false', 'logged_in': False}
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_zayvka FROM users WHERE id = %s", (session['user_id'],))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result:
        return {'is_zayvka': result[0]}  # должно возвращать 'true' или 'false'
    return {'is_zayvka': 'false'}

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
    # ЕСЛИ ПОЛЬЗОВАТЕЛЬ УЖЕ ЗАЛОГИНЕН
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('student_page'))
    
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[3]
            session['first_name'] = user[4]
            session['last_name'] = user[5]
            session['role'] = user[6]
            session['is_zayvka'] = user[9]
            
            if user[6] == 'admin':
                return redirect(url_for('admin_panel'))
            
            if session['is_zayvka'] == 'true':
                return redirect(url_for('calendar_page'))
            
            return redirect(url_for('student_page'))
            
        else:
            return render_template('login.html', error="❌ Неверный логин или пароль")
    
    return render_template('login.html')


@app.route('/api/new_events_count')
def new_events_count():
    if 'user_id' not in session:
        return {'count': 0}
    
    conn = get_db()
    cur = conn.cursor()
    
    last_visit = session.get('last_calendar_visit')
    
    if last_visit:
        cur.execute("""
            SELECT COUNT(*) FROM calendar 
            WHERE created_at > %s
        """, (last_visit,))
    else:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        cur.execute("""
            SELECT COUNT(*) FROM calendar 
            WHERE created_at > %s
        """, (yesterday,))
    
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    
    return {'count': count}

@app.route('/update_calendar_visit')
def update_calendar_visit():
    if 'user_id' in session:
        session['last_calendar_visit'] = datetime.datetime.now()
    return {'success': True}

@app.route('/api/recent_events')
def recent_events():
    if 'user_id' not in session:
        return {'events': []}
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM calendar 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    events = cur.fetchall()
    cur.close()
    conn.close()
    
    result = []
    for event in events:
        result.append({
            'id': event[0],
            'title': event[8],
            'event_date': str(event[6]),
            'event_time': event[7],
            'first_name': event[3],
            'last_name': event[4]
        })
    
    return {'events': result}

# ============ API ДЛЯ POSTMAN ============

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    API для регистрации через Postman
    POST /api/register
    {
        "first_name": "Иван",
        "last_name": "Иванов",
        "username": "ivan",
        "password": "123456",
        "email": "ivan@example.com",
        "role": "student"  // или "teacher"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        username = data.get('username', '').lower()
        password = data.get('password')
        email = data.get('email')
        role = data.get('role', 'student')
        
        # Валидация
        if not all([first_name, last_name, username, password, email]):
            return jsonify({'success': False, 'error': 'Все поля обязательны'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Создаём пользователя
        cur.execute("""
            INSERT INTO users (username, password, email, first_name, last_name, role, is_blocked, is_zayvka) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (username, password, email, first_name, last_name, role, False, 'false'))
        
        user_id = cur.fetchone()[0]
        
        # Создаём заявку на сегодня
        today = datetime.date.today()
        today_str = today.isoformat()
        title = f"Заявка на {today_str}"
        
        cur.execute("""
            INSERT INTO zayvka (user_id, username, first_name, last_name, email, user_role, event_date, event_time, title, description) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, username, first_name, last_name, email, role, today_str, '12:00', title, ''))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Уведомление в Telegram
        role_emoji = "👨‍🎓" if role == 'student' else "👨‍🏫"
        role_name = "Студент" if role == 'student' else "Преподаватель"
        
        message = f"""
📢 <b>НОВАЯ РЕГИСТРАЦИЯ ЧЕРЕЗ API! ({role_name})</b>

{role_emoji} <b>Роль:</b> {role_name}
👤 <b>Имя:</b> {first_name} {last_name}
🔑 <b>Логин:</b> {username}
📧 <b>Email:</b> {email}
🆔 <b>ID:</b> {user_id}

🔗 <a href="http://localhost:5000/admin_zayvka">Перейти к заявкам</a>
        """
        send_telegram(message)
        
        return jsonify({
            'success': True,
            'message': 'Регистрация успешна',
            'user_id': user_id,
            'username': username
        }), 201
        
    except psycopg2.IntegrityError as e:
        return jsonify({'success': False, 'error': 'Пользователь уже существует'}), 409
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events', methods=['POST'])
def api_create_event():
    """
    API для создания события через Postman
    POST /api/events
    {
        "username": "ivan",
        "password": "123456",
        "date": "2026-03-01",
        "time": "14:00",
        "title": "Важное событие",
        "description": "Описание события"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        username = data.get('username', '').lower()
        password = data.get('password')
        date_str = data.get('date')
        time_str = data.get('time', '12:00')
        title = data.get('title')
        description = data.get('description', '')
        
        # Валидация
        if not all([username, password, date_str, title]):
            return jsonify({'success': False, 'error': 'Не все обязательные поля заполнены'}), 400
        
        # Проверяем дату
        try:
            event_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return jsonify({'success': False, 'error': 'Неверный формат даты. Используйте ГГГГ-ММ-ДД'}), 400
        
        # Проверяем, что дата не в прошлом
        moscow_tz = datetime.timezone(datetime.timedelta(hours=3))
        moscow_now = datetime.datetime.now(moscow_tz).date()
        
        if event_date < moscow_now:
            return jsonify({'success': False, 'error': 'Нельзя добавлять события в прошлом'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Проверяем пользователя
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        user_id = user[0]
        is_zayvka = user[9]
        
        # Проверяем, есть ли доступ к календарю
        if is_zayvka != 'true':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'У вас нет доступа к календарю. Заявка ещё не принята'}), 403
        
        # Создаём событие
        cur.execute("""
            INSERT INTO calendar (user_id, username, first_name, last_name, user_role, event_date, event_time, title, description) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, user[1], user[4], user[5], user[6], date_str, time_str, title, description))
        
        event_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Уведомление в Telegram о новом событии
        role_emoji = "👨‍🏫" if user[6] == 'teacher' else "👨‍🎓"
        message = f"""
📅 <b>НОВОЕ СОБЫТИЕ ЧЕРЕЗ API!</b>

{role_emoji} <b>Автор:</b> {user[4]} {user[5]} (@{username})
📆 <b>Дата:</b> {date_str} {time_str}
📝 <b>Название:</b> {title}
📋 <b>Описание:</b> {description or 'Нет описания'}

🔗 <a href="http://localhost:5000/calendar">Перейти в календарь</a>
        """
        send_telegram(message)
        
        return jsonify({
            'success': True,
            'message': 'Событие создано',
            'event_id': event_id
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events', methods=['GET'])
def api_get_events():
    """
    API для получения списка событий
    GET /api/events?username=ivan&password=123456&limit=10
    """
    try:
        username = request.args.get('username', '').lower()
        password = request.args.get('password')
        limit = request.args.get('limit', 50, type=int)
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        conn = get_db()
        cur = conn.cursor()
        
        # Проверяем пользователя
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        # Получаем события
        if user[6] == 'admin':
            # Админ видит все события
            cur.execute("""
                SELECT * FROM calendar 
                ORDER BY event_date DESC, event_time DESC 
                LIMIT %s
            """, (limit,))
        else:
            # Обычный пользователь видит только свои события
            cur.execute("""
                SELECT * FROM calendar 
                WHERE user_id = %s 
                ORDER BY event_date DESC, event_time DESC 
                LIMIT %s
            """, (user[0], limit))
        
        events = cur.fetchall()
        cur.close()
        conn.close()
        
        result = []
        for event in events:
            result.append({
                'id': event[0],
                'user_id': event[1],
                'username': event[2],
                'author': f"{event[3]} {event[4]}",
                'role': event[5],
                'date': str(event[6]),
                'time': event[7],
                'title': event[8],
                'description': event[9]
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'events': result
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    

@app.route('/api/login', methods=['POST'])
def api_login():
    """
    API для входа
    POST /api/login
    {
        "username": "ivan",
        "password": "123456"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        username = data.get('username', '').lower()
        password = data.get('password')
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'email': user[3],
                'first_name': user[4],
                'last_name': user[5],
                'role': user[6],
                'is_blocked': user[7],
                'is_zayvka': user[9]
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/status', methods=['GET'])
def api_user_status():
    """
    API для проверки статуса пользователя
    GET /api/user/status?username=ivan&password=123456
    """
    try:
        username = request.args.get('username', '').lower()
        password = request.args.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        return jsonify({
            'success': True,
            'is_blocked': user[7],
            'is_zayvka': user[9],
            'role': user[6]
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500





@app.route('/register', methods=['GET', 'POST'])
def register():
    # Если пользователь уже залогинен
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('student_page'))

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
            
            # Создаём пользователя с is_zayvka = 'false'
            cur.execute("""
                INSERT INTO users (username, password, email, first_name, last_name, role, is_blocked, is_zayvka) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (username, password, email, first_name, last_name, role, False, 'false'))
            
            user_id = cur.fetchone()[0]
            
            # Создаём заявку
            today = datetime.date.today()
            today_str = today.isoformat()
            title = f"Заявка на {today_str}"
            
            cur.execute("""
                INSERT INTO zayvka (user_id, username, first_name, last_name, email, user_role, event_date, event_time, title, description) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, username, first_name, last_name, email, role, today_str, '12:00', title, ''))
            
            conn.commit()
            
            # Создаём сессию
            session['user_id'] = user_id
            session['username'] = username
            session['email'] = email
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['role'] = role
            session['is_zayvka'] = 'false'
            
            cur.close()
            conn.close()
            
            # Уведомление админу (БЕЗ ДАТЫ ЗАЯВКИ)
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
            
            return redirect(url_for('student_page'))
            
        except psycopg2.IntegrityError as e:
            return render_template('register.html', error="❌ Пользователь уже существует")
        except Exception as e:
            return render_template('register.html', error=f"❌ Ошибка: {e}")
    
    return render_template('register.html')





@app.route('/zayvka')
def student_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Проверка на блокировку
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_blocked FROM users WHERE id = %s", (session['user_id'],))
    is_blocked = cur.fetchone()[0]
    
    if is_blocked:
        cur.close()
        conn.close()
        return redirect(url_for('blocked_page'))
    
    # Если есть доступ к календарю - отправляем в календарь
    if session.get('is_zayvka') == 'true':
        cur.close()
        conn.close()
        return redirect(url_for('calendar_page'))
    
    # Получаем ВСЕ заявки пользователя
    cur.execute("SELECT * FROM zayvka WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    zayvki = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('student.html',
        zayvki=zayvki,
        first_name=session['first_name'],
        last_name=session['last_name'],
        username=session['username'],
        email=session['email'],
        calendar_access=False
    )

@app.route('/blocked')
def blocked_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name, username, email, block_reason FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    return render_template('blocked.html',
        first_name=user[0] if user else 'Неизвестно',
        last_name=user[1] if user else '',
        username=user[2] if user else 'Неизвестно',
        email=user[3] if user else 'Неизвестно',
        block_reason=user[4] if user and user[4] else 'Причина не указана'
    )

@app.route('/calendar')
def calendar_page():
    # Проверка авторизации
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Проверка на блокировку
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_blocked FROM users WHERE id = %s", (session['user_id'],))
    is_blocked = cur.fetchone()[0]
    
    if is_blocked:
        cur.close()
        conn.close()
        return redirect(url_for('blocked_page'))
    
    # ПОЛУЧАЕМ АКТУАЛЬНОЕ ЗНАЧЕНИЕ is_zayvka ИЗ БАЗЫ ДАННЫХ
    cur.execute("SELECT is_zayvka FROM users WHERE id = %s", (session['user_id'],))
    db_is_zayvka = cur.fetchone()[0]
    
    # ОБНОВЛЯЕМ СЕССИЮ, ЕСЛИ ЗНАЧЕНИЕ ИЗМЕНИЛОСЬ
    if session.get('is_zayvka') != db_is_zayvka:
        session['is_zayvka'] = db_is_zayvka
        print(f"🔄 Сессия обновлена: is_zayvka = {db_is_zayvka}")
    
    # ЕСЛИ is_zayvka = 'false' - ОТПРАВЛЯЕМ НА СТРАНИЦУ ЗАЯВОК
    if db_is_zayvka == 'false':
        cur.close()
        conn.close()
        return redirect(url_for('student_page'))
    
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
    
    # Получаем события за текущий месяц
    cur.execute("""
        SELECT * FROM calendar 
        WHERE event_date >= %s AND event_date < %s
        ORDER BY event_date, event_time
    """, (start_date, end_date))
    month_events = cur.fetchall()
    
    # Формируем словарь событий по дням
    day_events = {}
    for event in month_events:
        date_str = event[6]
        if isinstance(date_str, datetime.date):
            day = date_str.day
        else:
            try:
                event_date = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
                day = event_date.day
            except:
                continue
        
        if day not in day_events:
            day_events[day] = []
        day_events[day].append({
            'title': event[8],
            'description': event[9],
            'time': event[7] or '00:00',
            'author': f"{event[3]} {event[4]}",
            'role': event[5],
            'id': event[0],
            'user_id': event[1]
        })
    
    today = datetime.date.today().isoformat()
    
    # Получаем все события для списка
    cur.execute("SELECT * FROM calendar WHERE event_date >= %s ORDER BY event_date", (today,))
    all_events = cur.fetchall()
    
    # Считаем статистику
    cur.execute("SELECT COUNT(*) FROM calendar WHERE user_id = %s", (session['user_id'],))
    my_events = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    # Навигация по месяцам
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
        other_events=len(all_events) - my_events,
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
    cur.close()
    conn.close()
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
    cur.close()
    conn.close()
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
    
    cur.close()
    conn.close()
    
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
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_unlock/<int:user_id>')
def admin_unlock(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_blocked=False, block_reason=NULL WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_delete/<int:user_id>')
def admin_delete(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
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
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_delete_all_events')
def admin_delete_all_events():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM calendar")
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin_zayvka')
def admin_zayvka():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем все заявки
    cur.execute("SELECT * FROM zayvka ORDER BY created_at DESC")
    zayvki = cur.fetchall()
    
    # Простая статистика - только общее количество
    cur.execute("SELECT COUNT(*) FROM zayvka")
    total = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return render_template('admin_zayvka.html',
        zayvki=zayvki,
        total=total,
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
        # Обновляем is_zayvka на 'true'
        cur.execute("UPDATE users SET is_zayvka = 'true' WHERE id = %s", (z[1],))
        
        # Удаляем заявку
        cur.execute("DELETE FROM zayvka WHERE id = %s", (zayvka_id,))
        conn.commit()
        
        # Обновляем сессию строкой
        if session.get('user_id') == z[1]:
            session['is_zayvka'] = 'true'
        
        # Уведомление
        role_emoji = "👨‍🏫" if z[6] == 'teacher' else "👨‍🎓"
        message = f"""
✅ <b>ЗАЯВКА ПРИНЯТА!</b>

{role_emoji} <b>Пользователь:</b> {z[3]} {z[4]}
📝 <b>Событие:</b> {z[9]}

🎉 Пользователь теперь имеет доступ к календарю
        """
        send_telegram(message)
    
    cur.close()
    conn.close()
    return redirect(url_for('admin_zayvka'))





@app.route('/admin_zayvka_reject/<int:zayvka_id>')
def admin_zayvka_reject(zayvka_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем информацию о заявке
    cur.execute("SELECT * FROM zayvka WHERE id = %s", (zayvka_id,))
    z = cur.fetchone()
    
    if z:
        user_id = z[1]
        user_name = f"{z[3]} {z[4]}"
        
        # Удаляем все события пользователя из календаря
        cur.execute("DELETE FROM calendar WHERE user_id = %s", (user_id,))
        
        # Удаляем все заявки пользователя
        cur.execute("DELETE FROM zayvka WHERE user_id = %s", (user_id,))
        
        # Удаляем самого пользователя
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        conn.commit()
        
        # Если это тот самый пользователь, чья сессия сейчас активна - очищаем сессию
        if session.get('user_id') == user_id:
            session.clear()
        
        # Уведомление (УПРОЩЁННОЕ)
        message = f"""
❌ <b>ЗАЯВКА ОТКЛОНЕНА</b>

👤 <b>Пользователь:</b> {user_name}
📝 <b>Событие:</b> {z[9]}

💀 Аккаунт полностью удален из системы
        """
        send_telegram(message)
    
    cur.close()
    conn.close()
    return redirect(url_for('admin_zayvka'))






@app.route('/admin_zayvka_reject_all')
def admin_zayvka_reject_all():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем всех пользователей, у которых есть заявки
    cur.execute("SELECT DISTINCT user_id FROM zayvka")
    users_to_delete = cur.fetchall()
    
    deleted_count = 0
    for user in users_to_delete:
        user_id = user[0]
        
        # Удаляем события пользователя
        cur.execute("DELETE FROM calendar WHERE user_id = %s", (user_id,))
        
        # Удаляем заявки пользователя
        cur.execute("DELETE FROM zayvka WHERE user_id = %s", (user_id,))
        
        # Удаляем самого пользователя
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        deleted_count += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    send_telegram(f"🗑️ <b>МАССОВОЕ ОТКЛОНЕНИЕ</b>\nУдалено аккаунтов: {deleted_count}")
    
    # Очищаем сессию если админ сам себя не удалил
    if session.get('user_id') in [u[0] for u in users_to_delete]:
        session.clear()
        return redirect(url_for('login'))
    
    return redirect(url_for('admin_zayvka'))

@app.route('/admin_zayvka_delete_single/<int:zayvka_id>')
def admin_zayvka_delete_single(zayvka_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем информацию о заявке для уведомления
    cur.execute("SELECT * FROM zayvka WHERE id = %s", (zayvka_id,))
    z = cur.fetchone()
    
    if z:
        cur.execute("DELETE FROM zayvka WHERE id = %s", (zayvka_id,))
        conn.commit()
        send_telegram(f"🗑️ Заявка #{zayvka_id} от {z[3]} {z[4]} удалена администратором")
    
    cur.close()
    conn.close()
    return redirect(url_for('admin_zayvka'))

@app.route('/admin_zayvka_delete_all')
def admin_zayvka_delete_all():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем количество для статистики
    cur.execute("SELECT COUNT(*) FROM zayvka")
    count = cur.fetchone()[0]
    
    cur.execute("DELETE FROM zayvka")
    conn.commit()
    cur.close()
    conn.close()
    
    send_telegram(f"🗑️ <b>АДМИН УДАЛИЛ ВСЕ ЗАЯВКИ</b>\nУдалено: {count} заявок")
    
    return redirect(url_for('admin_zayvka'))

@app.route('/admin_zayvka_delete_all_rejected')
def admin_zayvka_delete_all_rejected():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем количество для статистики
    cur.execute("SELECT COUNT(*) FROM zayvka WHERE status='rejected'")
    count = cur.fetchone()[0]
    
    cur.execute("DELETE FROM zayvka WHERE status='rejected'")
    conn.commit()
    cur.close()
    conn.close()
    
    send_telegram(f"🗑️ Удалено {count} отклоненных заявок")
    
    return redirect(url_for('admin_zayvka'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============ JSON API (ТОЛЬКО ДЛЯ АДМИНА) ============

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return {'success': False, 'error': 'Требуются права администратора'}, 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/users', methods=['GET'])
@admin_required
def api_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, first_name, last_name, role, is_blocked, is_zayvka FROM users ORDER BY id")
    users = cur.fetchall()
    cur.close()
    conn.close()
    
    result = []
    for user in users:
        result.append({
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'first_name': user[3],
            'last_name': user[4],
            'role': user[5],
            'is_blocked': user[6],
            'is_zayvka': user[7]
        })
    
    return {'success': True, 'count': len(result), 'users': result}

@app.route('/api/calendar', methods=['GET'])
def api_calendar():
    """
    API для получения календаря
    Поддерживает два способа:
    1. Через сессию (если уже вошли на сайт)
    2. Через параметры username/password (для мобильных приложений)
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        
        user_id = None
        user_role = None
        
        # СПОСОБ 1: Проверяем сессию
        if 'user_id' in session:
            user_id = session['user_id']
            user_role = session.get('role')
            print(f"🔑 Авторизация через сессию: user_id={user_id}")
            
        # СПОСОБ 2: Проверяем параметры URL
        else:
            username = request.args.get('username', '').lower()
            password = request.args.get('password')
            
            if username and password:
                cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", 
                           (username, password))
                user = cur.fetchone()
                if user:
                    user_id = user[0]
                    user_role = user[6]
                    print(f"📱 Авторизация через параметры: username={username}")
        
        # Если не авторизован ни одним способом
        if not user_id:
            cur.close()
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Требуется авторизация (войдите на сайт или укажите username/password)'
            }), 401
        
        # Получаем все события
        cur.execute("SELECT * FROM calendar ORDER BY event_date DESC, event_time DESC")
        events = cur.fetchall()
        cur.close()
        conn.close()
        
        result = []
        for event in events:
            result.append({
                'id': event[0],
                'user_id': event[1],
                'username': event[2],
                'first_name': event[3],
                'last_name': event[4],
                'user_role': event[5],
                'event_date': str(event[6]),
                'event_time': event[7],
                'title': event[8],
                'description': event[9]
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'events': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500
    



@app.route('/api/zayvka', methods=['GET'])
@admin_required
def api_zayvka():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM zayvka ORDER BY created_at DESC")
    zayvki = cur.fetchall()
    cur.close()
    conn.close()
    
    result = []
    for z in zayvki:
        result.append({
            'id': z[0],
            'user_id': z[1],
            'username': z[2],
            'first_name': z[3],
            'last_name': z[4],
            'email': z[5],
            'user_role': z[6],
            'event_date': str(z[7]),
            'event_time': z[8],
            'title': z[9],
            'description': z[10],
            'status': z[11],
            'created_at': str(z[12])
        })
    
    return {'success': True, 'count': len(result), 'zayvki': result}

@app.route('/api/user/<int:user_id>', methods=['GET'])
@admin_required
def api_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, first_name, last_name, role, is_blocked, is_zayvka FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return {
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'first_name': user[3],
                'last_name': user[4],
                'role': user[5],
                'is_blocked': user[6],
                'is_zayvka': user[7]
            }
        }
    return {'success': False, 'error': 'User not found'}, 404

@app.route('/api/calendar/<int:event_id>', methods=['GET'])
@admin_required
def api_event(event_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM calendar WHERE id = %s", (event_id,))
    event = cur.fetchone()
    cur.close()
    conn.close()
    
    if event:
        return {
            'success': True,
            'event': {
                'id': event[0],
                'user_id': event[1],
                'username': event[2],
                'first_name': event[3],
                'last_name': event[4],
                'user_role': event[5],
                'event_date': str(event[6]),
                'event_time': event[7],
                'title': event[8],
                'description': event[9]
            }
        }
    return {'success': False, 'error': 'Event not found'}, 404

@app.route('/api/zayvka/<int:zayvka_id>', methods=['GET'])
@admin_required
def api_one_zayvka(zayvka_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM zayvka WHERE id = %s", (zayvka_id,))
    z = cur.fetchone()
    cur.close()
    conn.close()
    
    if z:
        return {
            'success': True,
            'zayvka': {
                'id': z[0],
                'user_id': z[1],
                'username': z[2],
                'first_name': z[3],
                'last_name': z[4],
                'email': z[5],
                'user_role': z[6],
                'event_date': str(z[7]),
                'event_time': z[8],
                'title': z[9],
                'description': z[10],
                'status': z[11],
                'created_at': str(z[12])
            }
        }
    return {'success': False, 'error': 'Zayvka not found'}, 404

@app.route('/json')
@admin_required
def json_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 JSON API (Админ)</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial; background: #1a2639; color: white; padding: 30px; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #4a90e2; }
            .admin-badge { 
                background: #ffd700; 
                color: black; 
                padding: 10px 20px; 
                border-radius: 30px; 
                display: inline-block;
                margin-bottom: 20px;
            }
            .api-links { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0; }
            .api-card { background: white; color: #333; padding: 20px; border-radius: 10px; border-left: 5px solid #4a90e2; }
            .api-card a { color: #4a90e2; text-decoration: none; font-weight: bold; }
            .json-box { background: #2d3748; color: #a0c0ff; padding: 20px; border-radius: 10px; font-family: monospace; white-space: pre-wrap; max-height: 400px; overflow: auto; }
            button { background: #4a90e2; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
            .warning { background: rgba(255,215,0,0.2); color: #ffd700; padding: 15px; border-radius: 10px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="admin-badge">👑 Администратор</div>
            <h1>📊 JSON API панель</h1>
            
            <div class="warning">
                ⚠️ Доступно только для администраторов
            </div>
            
            <div class="api-links">
                <div class="api-card">
                    <h3>👥 Пользователи</h3>
                    <a href="/api/users" target="_blank">/api/users</a>
                    <br><small>GET - все пользователи</small>
                </div>
                <div class="api-card">
                    <h3>📅 События</h3>
                    <a href="/api/calendar" target="_blank">/api/calendar</a>
                    <br><small>GET - все события</small>
                </div>
                <div class="api-card">
                    <h3>📝 Заявки</h3>
                    <a href="/api/zayvka" target="_blank">/api/zayvka</a>
                    <br><small>GET - все заявки</small>
                </div>
            </div>
            
            <h2>📥 Результат:</h2>
            <div id="result" class="json-box">Нажми кнопку...</div>
            
            <div style="margin-top: 20px;">
                <button onclick="loadAPI('/api/users')">👥 Пользователи</button>
                <button onclick="loadAPI('/api/calendar')">📅 События</button>
                <button onclick="loadAPI('/api/zayvka')">📝 Заявки</button>
            </div>
            
            <p style="margin-top: 20px; color: #666;">
                🔗 Также доступны: /api/user/1, /api/calendar/1, /api/zayvka/1
            </p>
        </div>
        
        <script>
            async function loadAPI(url) {
                const result = document.getElementById('result');
                result.innerHTML = '⏳ Загрузка...';
                try {
                    const response = await fetch(url);
                    if (response.status === 403) {
                        result.innerHTML = '❌ Ошибка: Требуются права администратора';
                        return;
                    }
                    const data = await response.json();
                    result.innerHTML = JSON.stringify(data, null, 2);
                } catch (e) {
                    result.innerHTML = '❌ Ошибка: ' + e.message;
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("🚀 КАЛЕНДАРЬ ЗАПУЩЕН!")
    print("📅 http://localhost:5000")
    print("👑 Админ: admin / спец.пароль")
    print("📡 API Endpoints:")
    print("   POST /api/register - регистрация")
    print("   POST /api/login - вход")
    print("   POST /api/events - создание события")
    print("   GET /api/events - список событий")
    print("   GET /api/user/status - статус пользователя")
    app.run(host='0.0.0.0', port=5000, debug=True)