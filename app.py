import os
import re
import sys
import uuid
import time
import json
import base64
import logging
import threading
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ProcessPoolExecutor, as_completed

import requests
import PyPDF2
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, session

# ============== CONFIGURATION ==============
DATA_FILE = "users.json"
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

ADMIN_KEY = "ADMIN_12345"
CHANNEL_USERNAME = "@UR_IMAGE"
CHANNEL_LINK = "https://t.me/UR_IMAGE"
BOT_NAME = "Aadhar Web Portal"
TELEGRAM_BOT_TOKEN = "8438982368:AAGaW_6Ie3NEp3ox16s8UQKymjPSnVXkukk"

PLANS = {
    '10':  {'credits': 20,  'price': '₹49',  'lifetime': False},
    '20':  {'credits': 40,  'price': '₹100',  'lifetime': False},
    '50':  {'credits': 10,  'price': '₹250',  'lifetime': False},
    '100': {'credits': float('inf'),   'price': '₹1599', 'lifetime': True},
}

# ============== LOGGING SETUP ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== SESSION FACTORY ==============
PROXY_CONFIG = {
    'use_proxy': False,
    'http': None,
    'https': None
}

def create_session(use_proxy=False, proxy_string=None):
    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(
        pool_connections=10, pool_maxsize=10, max_retries=3, pool_block=False
    ))
    if use_proxy and proxy_string:
        parsed = urlparse(proxy_string)
        proxy_url = f"{parsed.scheme}://{parsed.netloc}"
        PROXY_CONFIG['use_proxy'] = True
        PROXY_CONFIG['http'] = proxy_url
        PROXY_CONFIG['https'] = proxy_url
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    else:
        PROXY_CONFIG['use_proxy'] = False
        PROXY_CONFIG['http'] = None
        PROXY_CONFIG['https'] = None
    return session

uidai_session = None
def get_uidai_session():
    global uidai_session
    if uidai_session is None:
        uidai_session = create_session(False)
    return uidai_session

telegram_session = None
def get_telegram_session():
    global telegram_session
    if telegram_session is None:
        telegram_session = create_session(False)
    return telegram_session

# ============== PDF PASSWORD CRACKER ==============
class PDFPasswordCracker:
    def __init__(self):
        self.found_password = None
        self.stop_flag = False

    @staticmethod
    def _try_password(pdf_bytes, password):
        try:
            from io import BytesIO
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            if pdf_reader.decrypt(password):
                return True, password
            return False, None
        except Exception:
            return False, None

    def decrypt_pdf(self, pdf_path, password, output_path=None):
        try:
            if output_path is None:
                output_path = pdf_path.replace('.pdf', '_decrypted.pdf')
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                pdf_reader.decrypt(password)
                pdf_writer = PyPDF2.PdfWriter()
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
            logger.info(f"Decrypted PDF saved: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error decrypting PDF: {e}")
            return None

    def crack_pdf(self, pdf_path, name):
        self.found_password = None
        self.stop_flag = False

        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        name_upper = name.upper()
        patterns = []
        name_prefix = name_upper[:4] if len(name_upper) >= 4 else name_upper
        patterns.append(('first4', name_prefix))
        if len(name_upper) >= 6:
            patterns.append(('first6', name_upper[:6]))
        name_full = name_upper[:10] if len(name_upper) > 10 else name_upper
        patterns.append(('full', name_full))
        patterns.append(('lower_first4', name_prefix.lower()))
        if len(name_upper) >= 6:
            patterns.append(('lower_first6', name_upper[:6].lower()))
        patterns.append(('title_first4', name_prefix.title()))
        patterns.append(('first4_short', name_prefix[:4]))
        patterns.append(('with_at', f"{name_prefix}@"))
        patterns.append(('with_hash', f"{name_prefix}#"))
        patterns.append(('with_exclaim', f"{name_prefix}!"))
        patterns.append(('year_first', "@"))
        patterns.append(('only_name', name_prefix))

        current_year = datetime.now().year
        common_years = list(range(current_year, 1929, -1))

        prioritized_passwords = []
        for year in common_years:
            for pattern_name, prefix in patterns:
                if pattern_name == 'year_first':
                    password = f"{year}{prefix}"
                elif pattern_name == 'only_name':
                    password = prefix
                elif pattern_name == 'first4_short':
                    password = f"{prefix[:4]}{year}"
                elif pattern_name == 'with_at':
                    password = f"{prefix}@{year}"
                elif pattern_name == 'with_hash':
                    password = f"{prefix}#{year}"
                elif pattern_name == 'with_exclaim':
                    password = f"{prefix}!{year}"
                else:
                    password = f"{prefix}{year}"
                prioritized_passwords.append(password)

        seen = set()
        unique_passwords = []
        for pwd in prioritized_passwords:
            if pwd not in seen:
                seen.add(pwd)
                unique_passwords.append(pwd)

        # On Windows web app, we fallback to threaded pool to avoid process spawns issues in debug loop
        # And sequential processing for fast local cracking
        max_workers = os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            batch_size = 50
            futures = []
            total_passwords = len(unique_passwords)

            for i, pwd in enumerate(unique_passwords):
                if self.stop_flag:
                    break
                futures.append(executor.submit(self._try_password, pdf_bytes, pwd))
                if len(futures) >= batch_size or i == total_passwords - 1:
                    for future in as_completed(futures):
                        if self.stop_flag:
                            break
                        try:
                            success, found_pwd = future.result(timeout=2)
                            if success:
                                self.found_password = found_pwd
                                self.stop_flag = True
                                decrypted_path = self.decrypt_pdf(pdf_path, found_pwd)
                                return True, found_pwd, decrypted_path
                        except Exception:
                            continue
                    futures = []

        if not self.stop_flag:
            no_year_passwords = [prefix for pattern_name, prefix in patterns if pattern_name not in ['only_name']]
            for password in no_year_passwords:
                if self.stop_flag:
                    break
                success, found_pwd = self._try_password(pdf_bytes, password)
                if success:
                    self.found_password = found_pwd
                    self.stop_flag = True
                    decrypted_path = self.decrypt_pdf(pdf_path, found_pwd)
                    return True, found_pwd, decrypted_path

        return False, None, None

# ============== AADHAAR CORE ENGINE ==============
class AadhaarEngine:
    def __init__(self):
        self.session = get_uidai_session()
        self.base_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en_IN',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://myaadhaar.uidai.gov.in',
            'Referer': 'https://myaadhaar.uidai.gov.in/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
            'appid': 'MYAADHAAR',
            'sec-ch-ua': '"Not-A.Brand";v="99", "Chromium";v="124"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
        }
        self.session.headers.update(self.base_headers)
        self.cracker = PDFPasswordCracker()

    def generate_transaction_id(self):
        return str(uuid.uuid4())

    def is_base64(self, s):
        if not isinstance(s, str) or len(s) < 100:
            return False
        if s.startswith('data:'):
            s = s.split(',')[1] if ',' in s else s
        if len(s) % 4 != 0:
            return False
        try:
            base64.b64decode(s)
            return True
        except:
            return False

    def detect_file_type(self, file_bytes):
        if file_bytes[:4] == b'%PDF':
            return 'pdf'
        elif file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'
        elif file_bytes[:2] == b'\xff\xd8':
            return 'jpg'
        return 'unknown'

    def detect_and_decode_base64(self, data, save_prefix="downloads/temp"):
        decoded_items = []
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, str) and len(value) > 100 and self.is_base64(value):
                    try:
                        clean_base64 = value.split(',')[1] if value.startswith('data:') and ',' in value else value
                        decoded_bytes = base64.b64decode(clean_base64)
                        file_type = self.detect_file_type(decoded_bytes)
                        if file_type in ['pdf', 'png', 'jpg']:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ext = file_type
                            filename = f"{save_prefix}_{key}_{timestamp}.{ext}"
                            with open(filename, 'wb') as f:
                                f.write(decoded_bytes)
                            decoded_items.append({'field': key, 'filename': filename, 'type': file_type, 'size': len(decoded_bytes)})
                            logger.info(f"Saved PDF to: {filename}")
                    except Exception as e:
                        logger.error(f"Base64 decode error: {e}")
                if isinstance(value, (dict, list)):
                    decoded_items.extend(self.detect_and_decode_base64(value, save_prefix))
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    decoded_items.extend(self.detect_and_decode_base64(item, save_prefix))
        return decoded_items

    def get_captcha(self):
        transaction_id = self.generate_transaction_id()
        self.session.headers.update({'x-request-id': transaction_id, 'transactionId': transaction_id})
        captcha_data = {'captchaLength': '6', 'captchaType': '2', 'audioCaptchaRequired': True}
        try:
            response = self.session.post(
                'https://tathya.uidai.gov.in/audioCaptchaService/api/captcha/v3/generation',
                json=captcha_data, timeout=15
            )
            if response.status_code != 200:
                return None, None, None
            resp_json = response.json()
            captcha_txn_id = resp_json.get('transactionId')
            captcha_base64 = resp_json.get('imageBase64')
            if not captcha_base64:
                for key, value in resp_json.items():
                    if isinstance(value, str) and len(value) > 100 and self.is_base64(value):
                        captcha_base64 = value
                        break
            if not captcha_base64:
                return None, None, None
            if captcha_base64.startswith('data:image'):
                captcha_base64 = captcha_base64.split(',')[1]
            return captcha_base64, captcha_txn_id, transaction_id
        except Exception as e:
            logger.error(f"Error getting captcha: {str(e)}")
            return None, None, None

    def send_eid_otp(self, mobile, name, captcha_code, captcha_txn_id, transaction_id):
        self.session.headers.update({'x-request-id': transaction_id, 'transactionId': transaction_id})
        request_data = {
            'mobileNumber': mobile, 'dob': None, 'email': None,
            'name': name.upper(), 'option': 'EID', 'otp': None,
            'otpTxnId': None, 'captchaTxnId': captcha_txn_id,
            'captcha': captcha_code, 'resendOtp': False
        }
        try:
            response = self.session.post(
                'https://tathya.uidai.gov.in/retrieveEidUid/ext/v1/generic/retrieveuideid',
                json=request_data, timeout=15
            )
            if response.status_code == 200:
                resp_json = response.json()
                if 'responseData' in resp_json:
                    response_data = resp_json['responseData']
                    otp_txn_id = response_data.get('otpTxnId')
                    status = response_data.get('status')
                    if otp_txn_id and status == "Success":
                        return True, otp_txn_id
                    else:
                        return False, response_data.get('message', 'Unknown error')
                else:
                    return False, 'Invalid response structure'
            else:
                return False, f'HTTP {response.status_code}'
        except Exception as e:
            return False, str(e)

    def verify_eid_otp(self, mobile, name, otp_code, otp_txn_id, captcha_txn_id, captcha_code):
        self.session.headers.update({'x-request-id': self.generate_transaction_id()})
        verify_data = {
            'mobileNumber': mobile, 'dob': None, 'name': name.upper(),
            'email': None, 'option': 'EID', 'otp': otp_code,
            'otpTxnId': otp_txn_id, 'captchaTxnId': captcha_txn_id,
            'captcha': captcha_code, 'resendOtp': False
        }
        try:
            response = self.session.post(
                'https://tathya.uidai.gov.in/retrieveEidUid/ext/v1/generic/retrieveuideid',
                json=verify_data, timeout=15
            )
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('status') == 200 or resp_json.get('status') == "Success":
                    if 'responseData' in resp_json:
                        response_data = resp_json['responseData']
                        eid_number = response_data.get('eidNumber')
                        name_from_response = response_data.get('name', name)
                        if eid_number:
                            return True, eid_number, name_from_response
                        else:
                            return False, None, "No EID found"
                    else:
                        return False, None, "Invalid response"
                else:
                    error_msg = resp_json.get('errorDetails', {}).get('messageEnglish', 'Verification failed')
                    return False, None, error_msg
            else:
                return False, None, f'HTTP {response.status_code}'
        except Exception as e:
            return False, None, str(e)

    def send_aadhaar_otp(self, eid_number, captcha_value, captcha_txn_id, transaction_id):
        self.session.headers.update({'x-request-id': transaction_id, 'transactionId': transaction_id})
        otp_request_data = {
            'eidNumber': eid_number, 'idType': 'eid',
            'captchaTxnId': captcha_txn_id, 'captchaValue': captcha_value,
            'transactionId': transaction_id, 'resendOTP': False
        }
        try:
            response = self.session.post(
                'https://tathya.uidai.gov.in/unifiedAppAuthService/api/v2/generate/aadhaar/otp',
                json=otp_request_data, timeout=15
            )
            if response.status_code == 200:
                resp_json = response.json()
                otp_txn_id = resp_json.get('txnId')
                status = resp_json.get('status')
                message = resp_json.get('message')
                if otp_txn_id and status == "Success":
                    return True, otp_txn_id, message
                else:
                    return False, None, message
            else:
                return False, None, f"HTTP {response.status_code}"
        except Exception as e:
            return False, None, str(e)

    def download_aadhaar_pdf(self, eid_number, otp, otp_txn_id, transaction_id, save_path):
        self.session.headers.update({'x-request-id': transaction_id, 'transactionId': transaction_id})
        download_data = {'eid': eid_number, 'mask': False, 'otp': otp, 'otpTxnId': otp_txn_id}
        try:
            response = self.session.post(
                'https://tathya.uidai.gov.in/downloadAadhaarService/api/aadhaar/download',
                json=download_data, timeout=20
            )
            if response.status_code == 200:
                resp_json = response.json()
                decoded_files = self.detect_and_decode_base64(resp_json, save_prefix=save_path)
                if decoded_files:
                    return True, decoded_files[0]['filename']
                else:
                    if resp_json.get('status') == 'Error' or resp_json.get('errorCode'):
                        error_msg = resp_json.get('message', resp_json.get('errorMessage', 'Unknown error'))
                        return False, error_msg
                    else:
                        return False, "No PDF data found"
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)


# ============== FLASK SERVER SETUP ==============
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "alone_music_secret_key_123"
engine = AadhaarEngine()

_db_lock = threading.Lock()

def _load_users():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_users(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"User DB save error: {e}")

def get_client_ip():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    return ip

def get_or_create_user(user_id, referrer_id=None, ip_address=None):
    uid = str(user_id)
    with _db_lock:
        data = _load_users()
        is_new = False
        if 'referred_ips' not in data:
            data['referred_ips'] = []
            
        if uid not in data and uid != 'referred_ips':
            is_new = True
            data[uid] = {
                'credits': 1,  # 1 free credit on signup
                'lifetime': False,
                'referred_by': str(referrer_id) if referrer_id else None,
                'referral_count': 0,
                'joined': datetime.now().isoformat(),
                'telegram_id': None
            }
            if referrer_id:
                rid = str(referrer_id)
                if rid in data and rid != uid:
                    # Referrer gets credit ONLY if this IP has not referred before!
                    if ip_address and ip_address not in data['referred_ips']:
                        data[rid]['credits'] = data[rid].get('credits', 0) + 1
                        data[rid]['referral_count'] = data[rid].get('referral_count', 0) + 1
                        data['referred_ips'].append(ip_address)
                        logger.info(f"Referral successful! IP {ip_address} credited to {rid}")
                    else:
                        logger.info(f"Referral from IP {ip_address} blocked. Repeat referral attempt.")
            _save_users(data)
        return data.get(uid, {}), is_new

def is_telegram_verified(user_id):
    uid = str(user_id)
    with _db_lock:
        users = _load_users()
        if uid in users:
            u = users[uid]
            if u.get('lifetime'):
                return True
            tg_id = u.get('telegram_id')
            if not tg_id:
                return False
        else:
            return False

    # Check Telegram membership in real-time
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
        response = get_telegram_session().get(
            url,
            params={'chat_id': CHANNEL_USERNAME, 'user_id': tg_id},
            timeout=6
        ).json()
        if response.get('ok'):
            status = response['result']['status']
            return status in ('member', 'administrator', 'creator')
    except Exception as e:
        logger.error(f"Real-time Telegram gate error: {e}")
        return True # Fall safe to not lock out users if bot API fails
    return False

def deduct_user_credit(user_id):
    uid = str(user_id)
    with _db_lock:
        data = _load_users()
        if uid in data:
            if not data[uid].get('lifetime'):
                data[uid]['credits'] = max(0, data[uid].get('credits', 0) - 1)
                _save_users(data)

def check_credits(user_id):
    uid = str(user_id)
    with _db_lock:
        data = _load_users()
        if uid in data:
            u = data[uid]
            if u.get('lifetime'):
                return True
            return u.get('credits', 0) > 0
    return False


# ============== ROUTES ==============

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '192.168.', 'alonepro098']

@app.before_request
def block_unauthorized_hosts():
    host = request.headers.get('Host', '')
    allowed = False
    for item in ALLOWED_HOSTS:
        if item in host:
            allowed = True
            break
    if not allowed:
        return "", 400

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/aadhaar')
def aadhaar_home():
    return render_template('aadhaar.html')

# ============== CARD SUITE API ENDPOINTS ==============

BIN_CACHE_FILE = "bin_cache.json"
bin_cache = {}

def load_bin_cache():
    global bin_cache
    if os.path.exists(BIN_CACHE_FILE):
        try:
            with open(BIN_CACHE_FILE, 'r') as f:
                bin_cache = json.load(f)
        except Exception as e:
            logger.error(f"Error loading BIN cache: {e}")

def save_bin_cache():
    try:
        with open(BIN_CACHE_FILE, 'w') as f:
            json.dump(bin_cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving BIN cache: {e}")

load_bin_cache()

@app.route('/api/tools/bin-lookup', methods=['GET'])
def tool_bin_lookup():
    bin_number = request.args.get('bin', '').strip()
    bin_number = re.sub(r'\D', '', bin_number)[:8]
    if len(bin_number) < 6:
        return jsonify({'success': False, 'message': 'BIN must be at least 6 digits.'}), 400
    
    # Check cache (first 6 or 8 digits)
    for length in (8, 6):
        test_bin = bin_number[:length]
        if len(test_bin) == length and test_bin in bin_cache:
            return jsonify({'success': True, 'data': bin_cache[test_bin]})

    # Fetch from HandyAPI
    url = f"https://data.handyapi.com/bin/{bin_number}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('Status') == 'SUCCESS':
                bin_cache[bin_number] = data
                save_bin_cache()
                return jsonify({'success': True, 'data': data})
            else:
                return jsonify({'success': False, 'message': 'BIN details not found.'}), 404
        else:
            return jsonify({'success': False, 'message': f'External API responded with status {response.status_code}'}), 500
    except Exception as e:
        logger.error(f"BIN lookup error: {e}")
        return jsonify({'success': False, 'message': f'Error performing lookup: {str(e)}'}), 500

# Country code to Faker locale mapping
LOCALE_MAP = {
    'IN': 'en_IN',
    'US': 'en_US',
    'GB': 'en_GB',
    'CA': 'en_CA',
    'AU': 'en_AU',
    'FR': 'fr_FR',
    'DE': 'de_DE',
    'ES': 'es_ES',
    'IT': 'it_IT'
}

@app.route('/api/tools/fake-address', methods=['GET'])
def tool_fake_address():
    from faker import Faker
    country = request.args.get('country', 'US').upper().strip()
    qty = request.args.get('qty', '1')
    try:
        qty = min(max(int(qty), 1), 10)
    except ValueError:
        qty = 1
        
    locale = LOCALE_MAP.get(country, 'en_US')
    
    try:
        fake = Faker(locale)
        addresses = []
        for _ in range(qty):
            gender = 'male' if fake.boolean() else 'female'
            name = fake.name_male() if gender == 'male' else fake.name_female()
            
            addresses.append({
                'name': name,
                'gender': gender.capitalize(),
                'street': fake.street_address(),
                'city': fake.city(),
                'state': fake.state(),
                'postcode': fake.postcode(),
                'country': country,
                'country_name': fake.country(),
                'phone': fake.phone_number(),
                'email': fake.free_email(),
                'uuid': str(uuid.uuid4())[:8].upper()
            })
        return jsonify({'success': True, 'addresses': addresses})
    except Exception as e:
        logger.error(f"Fake address generation error: {e}")
        return jsonify({'success': False, 'message': f'Error generating address: {str(e)}'}), 500

@app.route('/api/user/info', methods=['GET'])
def user_info():
    user_id = request.args.get('user_id')
    ref = request.args.get('ref')
    if not user_id:
        user_id = f"AD-{uuid.uuid4().hex[:8].upper()}"

    ip_addr = get_client_ip()
    user_data, is_new = get_or_create_user(user_id, ref, ip_addr)
    tg_verified = is_telegram_verified(user_id)
    
    return jsonify({
        'user_id': user_id,
        'credits': "Lifetime" if user_data.get('lifetime') else user_data.get('credits', 0),
        'lifetime': user_data.get('lifetime'),
        'referral_count': user_data.get('referral_count', 0),
        'is_new': is_new,
        'tg_verified': tg_verified
    })

@app.route('/api/telegram/verify', methods=['POST'])
def verify_telegram():
    data = request.json or {}
    telegram_id = data.get('telegram_id')
    user_id = data.get('user_id')
    if not telegram_id or not user_id:
        return jsonify({'success': False, 'message': 'User ID and Telegram ID are required'})

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
        response = get_telegram_session().get(
            url,
            params={'chat_id': CHANNEL_USERNAME, 'user_id': telegram_id},
            timeout=8
        ).json()
        if response.get('ok'):
            status = response['result']['status']
            if status in ('member', 'administrator', 'creator'):
                uid = str(user_id)
                with _db_lock:
                    users = _load_users()
                    
                    # Check if another user has this telegram_id
                    existing_uid = None
                    for key, val in users.items():
                        if key != 'referred_ips' and isinstance(val, dict):
                            if val.get('telegram_id') == str(telegram_id):
                                existing_uid = key
                                break
                    
                    if existing_uid:
                        return jsonify({
                            'success': True,
                            'message': 'Successfully verified membership! Switched to your existing account.',
                            'user_id': existing_uid
                        })
                    
                    if uid in users:
                        users[uid]['telegram_id'] = str(telegram_id)
                        _save_users(users)
                return jsonify({
                    'success': True,
                    'message': 'Successfully verified membership!',
                    'user_id': uid
                })
            else:
                return jsonify({'success': False, 'message': f'Not a channel member. Current status: {status}'})
        else:
            return jsonify({'success': False, 'message': response.get('description', 'Validation failed')})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error checking Telegram: {str(e)}'})

@app.route('/api/captcha/get', methods=['GET'])
def get_captcha_image():
    user_id = request.args.get('user_id')
    if not user_id or not is_telegram_verified(user_id):
        return jsonify({'success': False, 'telegram_required': True, 'message': 'Telegram channel join required to continue.'})

    image_b64, captcha_txn_id, transaction_id = engine.get_captcha()
    if image_b64:
        return jsonify({
            'success': True,
            'image': f"data:image/png;base64,{image_b64}",
            'captcha_txn_id': captcha_txn_id,
            'transaction_id': transaction_id
        })
    return jsonify({'success': False, 'message': 'Failed to fetch captcha from UIDAI'})

@app.route('/api/flow/mobile/send-otp', methods=['POST'])
def mobile_send_otp():
    data = request.json or {}
    user_id = data.get('user_id')
    if not user_id or not is_telegram_verified(user_id):
        return jsonify({'success': False, 'telegram_required': True, 'message': 'Telegram channel join required.'})

    mobile = data.get('mobile')
    name = data.get('name', 'MR')
    captcha = data.get('captcha')
    captcha_txn_id = data.get('captcha_txn_id')
    transaction_id = data.get('transaction_id')

    if not all([mobile, captcha, captcha_txn_id, transaction_id]):
        return jsonify({'success': False, 'message': 'Missing parameters'})

    success, result = engine.send_eid_otp(mobile, name, captcha, captcha_txn_id, transaction_id)
    if success:
        return jsonify({'success': True, 'otp_txn_id': result})
    return jsonify({'success': False, 'message': result})

@app.route('/api/flow/mobile/verify-otp', methods=['POST'])
def mobile_verify_otp():
    data = request.json or {}
    user_id = data.get('user_id')
    if not user_id or not is_telegram_verified(user_id):
        return jsonify({'success': False, 'telegram_required': True, 'message': 'Telegram channel join required.'})

    mobile = data.get('mobile')
    name = data.get('name', 'MR')
    otp = data.get('otp')
    otp_txn_id = data.get('otp_txn_id')
    captcha_txn_id = data.get('captcha_txn_id')
    captcha = data.get('captcha')

    if not all([mobile, otp, otp_txn_id, captcha_txn_id, captcha]):
        return jsonify({'success': False, 'message': 'Missing parameters'})

    success, eid_number, name_retrieved = engine.verify_eid_otp(
        mobile, name, otp, otp_txn_id, captcha_txn_id, captcha
    )
    if success:
        return jsonify({
            'success': True,
            'eid': eid_number,
            'name': name_retrieved
        })
    return jsonify({'success': False, 'message': eid_number or 'Verification failed'})

@app.route('/api/flow/pdf/send-otp', methods=['POST'])
def pdf_send_otp():
    data = request.json or {}
    user_id = data.get('user_id')
    if not user_id or not is_telegram_verified(user_id):
        return jsonify({'success': False, 'telegram_required': True, 'message': 'Telegram channel join required.'})

    eid = data.get('eid')
    captcha = data.get('captcha')
    captcha_txn_id = data.get('captcha_txn_id')
    transaction_id = data.get('transaction_id')

    if not all([eid, captcha, captcha_txn_id, transaction_id]):
        return jsonify({'success': False, 'message': 'Missing parameters'})

    success, otp_txn_id, message = engine.send_aadhaar_otp(eid, captcha, captcha_txn_id, transaction_id)
    if success:
        return jsonify({'success': True, 'otp_txn_id': otp_txn_id})
    return jsonify({'success': False, 'message': message or 'Failed to send OTP'})

@app.route('/api/flow/pdf/download', methods=['POST'])
def pdf_download():
    data = request.json or {}
    user_id = data.get('user_id')
    if not user_id or not is_telegram_verified(user_id):
        return jsonify({'success': False, 'telegram_required': True, 'message': 'Telegram channel join required.'})

    eid = data.get('eid')
    otp = data.get('otp')
    otp_txn_id = data.get('otp_txn_id')
    transaction_id = data.get('transaction_id')
    name = data.get('name', 'MR')

    if not all([user_id, eid, otp, otp_txn_id, transaction_id]):
        return jsonify({'success': False, 'message': 'Missing parameters'})

    if not check_credits(user_id):
        return jsonify({'success': False, 'message': 'Insufficient credits! Please buy credits or refer friends.'})

    unique_id = str(uuid.uuid4())
    temp_prefix = os.path.join(DOWNLOADS_DIR, f"aadhaar_{unique_id}")

    success, downloaded_file = engine.download_aadhaar_pdf(eid, otp, otp_txn_id, transaction_id, temp_prefix)

    if success and downloaded_file:
        # Deduct credit
        deduct_user_credit(user_id)

        # Attempt to decrypt PDF using cracker
        crack_success, password, decrypted_path = engine.cracker.crack_pdf(downloaded_file, name)
        
        final_file = decrypted_path if (crack_success and decrypted_path) else downloaded_file
        filename = os.path.basename(final_file)

        if crack_success and decrypted_path and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except Exception:
                pass

        return jsonify({
            'success': True,
            'download_url': f"/downloads/{filename}",
            'unlocked': crack_success,
            'password': password if crack_success else None,
            'message': 'Decrypted successfully' if crack_success else 'PDF downloaded but password protected'
        })
    else:
        return jsonify({'success': False, 'message': downloaded_file or 'Download failed'})

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)

# ============== ADMIN PANEL API ==============

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    key = request.args.get('admin_key')
    if key != ADMIN_KEY:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    with _db_lock:
        data = _load_users()

    total_users = len(data)
    lifetime_count = sum(1 for u in data.values() if u.get('lifetime'))
    total_credits = sum(u.get('credits', 0) for u in data.values() if not u.get('lifetime'))

    return jsonify({
        'success': True,
        'total_users': total_users,
        'lifetime_users': lifetime_count,
        'credits_in_use': total_credits
    })

@app.route('/api/admin/send-credits', methods=['POST'])
def admin_send_credits():
    data = request.json or {}
    key = data.get('admin_key')
    target_id = data.get('target_user_id')
    amount = data.get('amount')

    if key != ADMIN_KEY:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if not target_id or amount is None:
        return jsonify({'success': False, 'message': 'Missing target user or amount'})

    try:
        amount = int(amount)
    except ValueError:
        return jsonify({'success': False, 'message': 'Amount must be an integer'})

    uid = str(target_id)
    with _db_lock:
        users = _load_users()
        if uid not in users:
            return jsonify({'success': False, 'message': 'User not found'})

        if amount == -1:
            users[uid]['lifetime'] = True
            message = "Granted Lifetime access"
        else:
            users[uid]['lifetime'] = False
            users[uid]['credits'] = users[uid].get('credits', 0) + amount
            message = f"Added {amount} credits"
        _save_users(users)

    return jsonify({'success': True, 'message': message})

@app.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    key = request.args.get('admin_key')
    if key != ADMIN_KEY:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    with _db_lock:
        users = _load_users()
    
    return jsonify({
        'success': True,
        'users': users
    })

# ============== CLEANUP CRON (BACKGROUND FILE PURGE) ==============
def file_cleanup_loop():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            for filename in os.listdir(DOWNLOADS_DIR):
                filepath = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 600:
                    try:
                        os.remove(filepath)
                        logger.info(f"Purged expired download file: {filename}")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Cleanup thread error: {e}")

cleanup_thread = threading.Thread(target=file_cleanup_loop, daemon=True)
cleanup_thread.start()

# ============== ALONEMUSIC / YOUTUBE EXTRACTOR ROUTES ==============

import yt_dlp

def get_youtube_file_path(video_id, ext):
    yt_dir = os.path.join(DOWNLOADS_DIR, "youtube.com")
    os.makedirs(yt_dir, exist_ok=True)
    return os.path.join(yt_dir, f"{video_id}.{ext}")

def download_youtube_background(video_url, video_id, dl_type):
    ext = 'mp3' if dl_type == 'audio' else 'mp4'
    local_path = get_youtube_file_path(video_id, ext)
    if os.path.exists(local_path):
        return
    temp_path = local_path + ".tmp"
    
    if dl_type == 'audio':
        ydl_opts = {
            'quiet': True,
            'outtmpl': temp_path,
            'format': 'bestaudio/best',
        }
    else:
        ydl_opts = {
            'quiet': True,
            'outtmpl': temp_path,
            'format': 'best[height<=360][ext=mp4]/best[height<=360]/best',
        }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(temp_path):
            os.rename(temp_path, local_path)
            logger.info(f"Background pre-cache success: {local_path}")
    except Exception as e:
        logger.error(f"Background download error: {e}")
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass

@app.route('/alone_music')
def alone_music_dashboard():
    api_key = session.get('api_key', '')
    return render_template('ytapi.html', api_key=api_key)

@app.route('/ayush_music')
def ayush_music_dashboard():
    api_key = session.get('api_key', '')
    return render_template('ayush_music.html', api_key=api_key)

@app.route('/generate_free_key', methods=['POST'])
def generate_free_key():
    session['api_key'] = "AM-KEY-" + str(uuid.uuid4())[:8].upper()
    return jsonify({'success': True, 'api_key': session['api_key']})

@app.route('/remove_api_key', methods=['POST'])
def remove_api_key():
    session.pop('api_key', None)
    return jsonify({'success': True})

@app.route('/search')
def search_youtube():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'result': []})
        
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    try:
        is_url = re.match(r'^https?://', query) or 'youtube.com' in query or 'youtu.be' in query
        search_query = query if is_url else f"ytsearch10:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_query, download=False)
            results = []
            
            entries = []
            if 'entries' in res:
                entries = res['entries']
            else:
                entries = [res]
                
            for entry in entries:
                if not entry:
                    continue
                duration_sec = entry.get('duration')
                duration_str = 'N/A'
                if duration_sec is not None:
                    mins = int(duration_sec // 60)
                    secs = int(duration_sec % 60)
                    duration_str = f"{mins}:{secs:02d}"
                
                thumbnails = entry.get('thumbnails', [])
                thumb_url = ''
                if thumbnails:
                    thumb_url = thumbnails[-1].get('url', '')
                if not thumb_url:
                    video_id = entry.get('id')
                    if video_id:
                        thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                
                results.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'duration': duration_str,
                    'thumbnails': [{'url': thumb_url}] if thumb_url else []
                })
            return jsonify({'result': results})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download_api():
    query = request.args.get('query', '').strip()
    dl_type = request.args.get('dl_type', 'audio').strip()
    prefetch = request.args.get('prefetch', 'false').lower() == 'true'
    
    if not query:
        return jsonify({'error': 'Missing query'}), 400
        
    video_id = None
    patterns = [
        r'youtu\.be/([^?#/]+)',
        r'watch\?v=([^&#/]+)',
        r'embed/([^?#/]+)',
        r'v/([^?#/]+)',
    ]
    for p in patterns:
        m = re.search(p, query)
        if m:
            video_id = m.group(1)
            break
            
    if not video_id:
        try:
            ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if 'entries' in res and res['entries']:
                    video_id = res['entries'][0]['id']
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    if not video_id:
        return jsonify({'error': 'Video not found'}), 404
        
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    if prefetch:
        threading.Thread(
            target=download_youtube_background,
            args=(video_url, video_id, dl_type),
            daemon=True
        ).start()
        return jsonify({'success': True, 'message': 'Prefetch started'})
        
    ext = 'mp3' if dl_type == 'audio' else 'mp4'
    apikey = session.get('api_key', '')
    if apikey:
        stream_url = f"/downloads/{apikey}/youtube.com/{video_id}.{ext}"
    else:
        stream_url = f"/downloads/youtube.com/{video_id}.{ext}"
        
    return jsonify({'success': True, 'stream_url': stream_url})

@app.route('/downloads/<apikey>/youtube.com/<video_id>.<ext>')
@app.route('/downloads/youtube.com/<video_id>.<ext>')
def stream_youtube(video_id, ext, apikey=None):
    quality = request.args.get('quality', '360')
    download_as_attachment = request.args.get('download', 'false').lower() == 'true'
    
    local_path = get_youtube_file_path(video_id, ext)
    if os.path.exists(local_path):
        return send_from_directory(os.path.join(DOWNLOADS_DIR, "youtube.com"), f"{video_id}.{ext}", as_attachment=download_as_attachment)
        
    if ext == 'mp3':
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio/best',
        }
    else:
        ydl_opts = {
            'quiet': True,
            'format': f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best',
        }
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            stream_url = info.get('url')
            if not stream_url:
                return jsonify({'error': 'Failed to obtain direct stream URL'}), 500
                
            req_headers = {}
            range_header = request.headers.get('Range')
            if range_header:
                req_headers['Range'] = range_header
                
            res = requests.get(stream_url, headers=req_headers, stream=True, timeout=15)
            
            resp_headers = {}
            for h in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
                if h in res.headers:
                    resp_headers[h] = res.headers[h]
                    
            if download_as_attachment:
                title = info.get('title', 'video')
                safe_title = "".join([c if c.isalnum() or c in '._-' else '_' for c in title])
                resp_headers['Content-Disposition'] = f'attachment; filename="{safe_title}.{ext}"'
                
            def generate():
                for chunk in res.iter_content(chunk_size=40960):
                    yield chunk
                    
            return Response(generate(), status=res.status_code, headers=resp_headers)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
