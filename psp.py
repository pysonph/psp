import os
import telebot
import re
import datetime
import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import random
import html
from dotenv import load_dotenv
import threading
from playwright.sync_api import sync_playwright

# ==========================================
# 📌 environment variables
# ==========================================
load_dotenv() 

BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 1318826936)) 
FB_EMAIL = os.getenv('FB_EMAIL')
FB_PASS = os.getenv('FB_PASS')

if not BOT_TOKEN:
    print("❌ error: bot_token missing in .env.")
    exit()

MMT = datetime.timezone(datetime.timedelta(hours=6, minutes=30))

# ==========================================
# 1. bot basic info
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 🗄️ local json database
# ==========================================
DB_FILE = 'database.json'

def load_data():
    if not os.path.exists(DB_FILE):
        return {"users": [OWNER_ID], "cookie": "PHPSESSID=205fdnmcd5c6mf0ut2kq4l6ji5"}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"users": [OWNER_ID], "cookie": "PHPSESSID=205fdnmcd5c6mf0ut2kq4l6ji5"}

def save_data(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ error saving database: {e}")

initial_data = load_data()
if OWNER_ID not in initial_data["users"]:
    initial_data["users"].append(OWNER_ID)
    save_data(initial_data)

# ==========================================
# 🍪 get cookies function 
# ==========================================
def get_login_cookies():
    db_data = load_data()
    raw_cookie = db_data.get("cookie", "")
    cookie_dict = {}
    for item in raw_cookie.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            cookie_dict[k] = v
    return cookie_dict

# ==========================================
# 🤖 playwright auto-login (facebook)
# ==========================================
def auto_login_and_get_cookie():
    if not FB_EMAIL or not FB_PASS:
        print("❌ fb_email and fb_pass missing in .env.")
        return False
        
    print("🔄 auto-login with facebook and searching for new cookie...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            
            page.goto("https://www.smile.one/customer/login")
            time.sleep(5) 
            
            with context.expect_page() as popup_info:
                page.locator("a.login-btn-facebook, a[href*='facebook.com']").first.click()
            
            fb_popup = popup_info.value
            fb_popup.wait_for_load_state()
            
            time.sleep(2)
            fb_popup.fill('input[name="email"]', FB_EMAIL)
            time.sleep(1)
            fb_popup.fill('input[name="pass"]', FB_PASS)
            time.sleep(1)
            
            fb_popup.click('button[name="login"], input[name="login"]')
            
            try:
                page.wait_for_url("**/customer/order**", timeout=30000)
                print("✅ auto-login successful. saving cookie...")
                
                cookies = context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                raw_cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                
                db_data = load_data()
                db_data["cookie"] = raw_cookie_str
                save_data(db_data)
                
                browser.close()
                return True
            except Exception as wait_e:
                print(f"❌ did not reach order page. (possible facebook checkpoint): {wait_e}")
                browser.close()
                return False
            
    except Exception as e:
        print(f"❌ error during auto-login: {e}")
        return False

# ==========================================
# 📌 packages (mlbb & magic chess)
# ==========================================
BR_PACKAGES = {
    '86': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}],
    '172': [{'pid': '23', 'price': 122.00, 'name': '172 💎'}],
    '257': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '279': [{'pid': '213', 'price': 19.0, 'name': '22 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '706': [{'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '2195': [{'pid': '27', 'price': 1453.00, 'name': '2195 💎'}],
    '3688': [{'pid': '28', 'price': 2424.00, 'name': '3688 💎'}],
    '5532': [{'pid': '29', 'price': 3660.00, 'name': '5532 💎'}],
    '9288': [{'pid': '30', 'price': 6079.00, 'name': '9288 💎'}],
    'b50': [{'pid': '22590', 'price': 39.0, 'name': 'b50 💎'}],
    'b150': [{'pid': '22591', 'price': 116.9, 'name': 'b150 💎'}],
    'b250': [{'pid': '22592', 'price': 187.5, 'name': 'b250 💎'}],
    'b500': [{'pid': '22593', 'price': 385, 'name': 'b500 💎'}],
    '600': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '343': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '514': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '429': [{'pid': '23', 'price': 122.00, 'name': '172 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '878': [{'pid': '23', 'price': 122.00, 'name': '172 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '963': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '1049': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '1135': [{'pid': '23', 'price': 122.00, 'name': '172 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '1412': [{'pid': '26', 'price': 480.00, 'name': '706 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '1584': [{'pid': '23', 'price': 122.00, 'name': '172 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '1755': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '2538': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '27', 'price': 1453.00, 'name': '2195 💎'}],
    '2901': [{'pid': '27', 'price': 1453.00, 'name': '2195 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}],
    '3244': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.00, 'name': '706 💎'}, {'pid': '27', 'price': 1453.00, 'name': '2195 💎'}],
    'elite': [{'pid': '26555', 'price': 39.00, 'name': 'Elite Weekly Paackage'}],
    'epic': [{'pid': '26556', 'price': 196.5, 'name': 'Epic Monthly Package'}],
    'tp': [{'pid': '33', 'price': 402.5, 'name': 'Twilight Passage'}],
    'wp': [{'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp2': [{'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp3': [{'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp4': [{'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp5': [{'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.00, 'name': 'Weekly Pass'}],
}

PH_PACKAGES = {
    '11': [{'pid': '212', 'price': 9.50, 'name': '11 💎'}],
    '22': [{'pid': '213', 'price': 19.0, 'name': '22 💎'}],
    '56': [{'pid': '214', 'price': 47.50, 'name': '56 💎'}],
    '112': [{'pid': '214', 'price': 47.50, 'name': '56 💎'}, {'pid': '214', 'price': 47.50, 'name': '56 💎'}],
    'wp': [{'pid': '16641', 'price': 95.00, 'name': 'Weekly Pass'}],
}

MCC_PACKAGES = {
    '86': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}],
    '172': [{'pid': '23826', 'price': 125.00, 'name': '172 💎'}],
    '257': [{'pid': '23827', 'price': 187.00, 'name': '257 💎'}],
    '343': [{'pid': '23828', 'price': 250.0, 'name': '343 💎'}],
    '516': [{'pid': '23829', 'price': 375.0, 'name': '516 💎'}],
    '706': [{'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '1346': [{'pid': '23831', 'price': 937.50, 'name': '1346 💎'}],
    '1825': [{'pid': '23832', 'price': 1250.00, 'name': '1825 💎'}],
    '2195': [{'pid': '23833', 'price': 1500.00, 'name': '2195 💎'}],
    '3688': [{'pid': '23834', 'price': 2500.00, 'name': '3688 💎'}],
    '5532': [{'pid': '23835', 'price': 3750.00, 'name': '5532 💎'}],
    '9288': [{'pid': '23836', 'price': 6250.00, 'name': '9288 💎'}],
    'b50': [{'pid': '23837', 'price': 40.0, 'name': '50+50 💎'}],
    'b150': [{'pid': '23838', 'price': 120.0, 'name': '150+150 💎'}],
    'b250': [{'pid': '23839', 'price': 200.0, 'name': '250+250 💎'}],
    'b500': [{'pid': '23840', 'price': 400, 'name': '500+500 💎'}],
    '429': [{'pid': '23826', 'price': 122.00, 'name': '172 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}],
    '600': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23827', 'price': 177.5, 'name': '257 💎'}],
    '878': [{'pid': '23826', 'price': 125.00, 'name': '172 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '963': [{'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '1049': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '1135': [{'pid': '23826', 'price': 125.00, 'name': '172 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '1412': [{'pid': '23830', 'price': 500.00, 'name': '706 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '1584': [{'pid': '23826', 'price': 125.00, 'name': '172 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}, {'pid': '23830', 'price': 480.00, 'name': '706 💎'}],
    '1755': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '2538': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23833', 'price': 1500.00, 'name': '2195 💎'}],
    '2901': [{'pid': '23833', 'price': 1500.00, 'name': '2195 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}],
    '3244': [{'pid': '23825', 'price': 62.50, 'name': '86 💎'}, {'pid': '23827', 'price': 187.00, 'name': '257 💎'}, {'pid': '23830', 'price': 500.00, 'name': '706 💎'}, {'pid': '23833', 'price': 1500.00, 'name': '2195 💎'}],
    'wp': [{'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp2': [{'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp3': [{'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp4': [{'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}],
    'wp5': [{'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.00, 'name': 'Weekly Pass'}],
}

# ==========================================
# 2. fetch real balance function
# ==========================================
def get_smile_balance(scraper, headers, balance_url='https://www.smile.one/customer/order'):
    balances = {'br_balance': 0.00, 'ph_balance': 0.00}
    try:
        response = scraper.get(balance_url, headers=headers)
        
        br_match = re.search(r'(?i)(?:Balance|Saldo)[\s:]*?<\/p>\s*<p>\s*([\d\.,]+)', response.text)
        if br_match:
            balances['br_balance'] = float(br_match.group(1).replace(',', ''))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            main_balance_div = soup.find('div', class_='balance-coins')
            if main_balance_div:
                p_tags = main_balance_div.find_all('p')
                if len(p_tags) >= 2:
                    balances['br_balance'] = float(p_tags[1].text.strip().replace(',', ''))
                    
        ph_match = re.search(r'(?i)Saldo PH[\s:]*?<\/span>\s*<span>\s*([\d\.,]+)', response.text)
        if ph_match:
            balances['ph_balance'] = float(ph_match.group(1).replace(',', ''))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            ph_balance_container = soup.find('div', id='all-balance')
            if ph_balance_container:
                span_tags = ph_balance_container.find_all('span')
                if len(span_tags) >= 2:
                    balances['ph_balance'] = float(span_tags[1].text.strip().replace(',', ''))
    except Exception as e:
        pass
    return balances

# ==========================================
# 3. smile.one scraper function (mlbb)
# ==========================================
def process_smile_one_order(user_id, zone_id, product_id, currency_name, item_price=None, seen_order_ids=None, cached_session=None):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())

    if currency_name == 'PH':
        main_url = 'https://www.smile.one/ph/merchant/mobilelegends'
        checkrole_url = 'https://www.smile.one/ph/merchant/mobilelegends/checkrole'
        query_url = 'https://www.smile.one/ph/merchant/mobilelegends/query'
        pay_url = 'https://www.smile.one/ph/merchant/mobilelegends/pay'
        order_api_url = 'https://www.smile.one/ph/customer/activationcode/codelist'
        balance_url = 'https://www.smile.one/ph/customer/order'
    else:
        main_url = 'https://www.smile.one/merchant/mobilelegends'
        checkrole_url = 'https://www.smile.one/merchant/mobilelegends/checkrole'
        query_url = 'https://www.smile.one/merchant/mobilelegends/query'
        pay_url = 'https://www.smile.one/merchant/mobilelegends/pay'
        order_api_url = 'https://www.smile.one/customer/activationcode/codelist'
        balance_url = 'https://www.smile.one/customer/order'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest', 
        'Referer': main_url, 
        'Origin': 'https://www.smile.one'
    }

    try:
        response = scraper.get(main_url, headers=headers)
        
        if response.status_code in [403, 503] or "cloudflare" in response.text.lower() or "security verification" in response.text.lower():
             return {"status": "error", "message": "⚠️ cloudflare security blocked the bot. insert new cookie from browser."}

        soup = BeautifulSoup(response.text, 'html.parser')
        
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token: return {"status": "error", "message": "csrf token not found. insert new cookie using /setcookie."}

        check_data = {
            'user_id': user_id, 
            'zone_id': zone_id, 
            '_csrf': csrf_token
        }
        
        role_response = scraper.post(checkrole_url, data=check_data, headers=headers)
        try:
            role_result = role_response.json()
            ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
            if not ig_name or str(ig_name).strip() == "":
                real_error = role_result.get('msg') or role_result.get('message') or "account not found."
                return {"status": "error", "message": f"❌ invalid account: {real_error}"}
        except Exception:
            return {"status": "error", "message": "⚠️ check role api error: cannot check account."}

        query_data = {
            'user_id': user_id, 'zone_id': zone_id, 'pid': product_id,
            'checkrole': '', 'pay_methond': 'smilecoin', 'channel_method': 'smilecoin', '_csrf': csrf_token
        }
        
        query_response = scraper.post(query_url, data=query_data, headers=headers)
        
        try: 
            query_result = query_response.json()
        except Exception: 
            if "cloudflare" in query_response.text.lower() or "just a moment" in query_response.text.lower():
                return {"status": "error", "message": "⚠️ cloudflare blocked the query."}
            return {"status": "error", "message": f"query api error (status: {query_response.status_code})"}
            
        flowid = query_result.get('flowid') or query_result.get('data', {}).get('flowid')
        
        if not flowid:
            raw_debug = json.dumps(query_result, ensure_ascii=False)
            real_error = query_result.get('msg') or query_result.get('message') or ""
            
            if "login" in str(real_error).lower() or "unauthorized" in str(real_error).lower():
                return {"status": "error", "message": "⚠️ cookie expired. please insert new cookie using `/setcookie`."}
            else:
                err_text = real_error if real_error else "account not found or rejected."
                return {"status": "error", "message": f"smile.one response: {err_text}\n\n*(debug: {raw_debug})*"}

        current_balances = get_smile_balance(scraper, headers, balance_url)

        pay_data = {
            '_csrf': csrf_token, 'user_id': user_id, 'zone_id': zone_id, 'pay_methond': 'smilecoin',
            'product_id': product_id, 'channel_method': 'smilecoin', 'flowid': flowid, 'email': '', 'coupon_id': ''
        }
        
        pay_response = scraper.post(pay_url, data=pay_data, headers=headers)
        pay_text = pay_response.text.lower()
        
        if "saldo insuficiente" in pay_text or "insufficient" in pay_text:
            return {"status": "error", "message": "insufficient balance in your account."}
        
        time.sleep(2) 
        
        real_order_id = "not found"
        is_success = False

        api_params = {'type': 'orderlist', 'p': '1', 'pageSize': '5'}
        try:
            hist_res = scraper.get(order_api_url, params=api_params, headers=headers)
            hist_json = hist_res.json()
            
            if 'list' in hist_json and isinstance(hist_json['list'], list) and len(hist_json['list']) > 0:
                for order in hist_json['list']:
                    if str(order.get('user_id')) == str(user_id) and str(order.get('server_id')) == str(zone_id):
                        if str(order.get('order_status', '')).lower() == 'success' or str(order.get('status')) == '1':
                            real_order_id = str(order.get('increment_id', "not found"))
                            is_success = True
                            break
        except Exception as e:
            pass

        if not is_success:
            try:
                pay_json = pay_response.json()
                code = str(pay_json.get('code', ''))
                status = str(pay_json.get('status', ''))
                msg = str(pay_json.get('msg', '')).lower()
                if code in ['200', '0', '1'] or status in ['200', '0', '1'] or msg in ['success', 'ok', 'sucesso'] or 'success' in pay_text:
                    is_success = True
            except:
                if 'success' in pay_text or 'ok' in pay_text or 'sucesso' in pay_text:
                    is_success = True

        if is_success:
            return {"status": "success", "ig_name": ig_name, "order_id": real_order_id, "balances": current_balances, "csrf_token": csrf_token}
        else:
            err_msg = "payment failed."
            try:
                err_json = pay_response.json()
                raw_pay_debug = json.dumps(err_json, ensure_ascii=False)
                if 'msg' in err_json: 
                    err_msg = f"payment failed. ({err_json['msg']})\n\n*(debug: {raw_pay_debug})*"
            except: pass
            return {"status": "error", "message": err_msg}

    except Exception as e: return {"status": "error", "message": f"system error: {str(e)}"}

# ==========================================
# 3.1 magic chess scraper function (mcc)
# ==========================================
def process_mcc_order(user_id, zone_id, product_id, item_price, seen_order_ids):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())

    main_url = 'https://www.smile.one/br/merchant/game/magicchessgogo'
    checkrole_url = 'https://www.smile.one/br/merchant/game/checkrole'
    query_url = 'https://www.smile.one/br/merchant/game/query'
    pay_url = 'https://www.smile.one/br/merchant/game/pay'
    order_api_url = 'https://www.smile.one/br/customer/activationcode/codelist'
    balance_url = 'https://www.smile.one/br/customer/order'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest', 
        'Referer': main_url, 
        'Origin': 'https://www.smile.one'
    }

    try:
        response = scraper.get(main_url, headers=headers)
        if response.status_code in [403, 503] or "cloudflare" in response.text.lower():
             return {"status": "error", "message": "⚠️ cloudflare security blocked the bot."}

        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token: return {"status": "error", "message": "csrf token not found. insert new cookie using /setcookie."}

        current_balances = get_smile_balance(scraper, headers, balance_url)
        if current_balances.get('br_balance', 0.0) < float(item_price):
            return {"status": "error", "message": f"insufficient balance. (required: {item_price} | remaining: {current_balances.get('br_balance', 0.0)})"}

        check_data = {'user_id': user_id, 'zone_id': zone_id, '_csrf': csrf_token}
        role_response = scraper.post(checkrole_url, data=check_data, headers=headers)
        try:
            role_result = role_response.json()
            ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
            if not ig_name or str(ig_name).strip() == "":
                return {"status": "error", "message": "❌ account not found."}
        except Exception:
            return {"status": "error", "message": "⚠️ check role api error"}

        query_data = {
            'user_id': user_id, 'zone_id': zone_id, 'pid': product_id,
            'checkrole': '', 'pay_methond': 'smilecoin', 'channel_method': 'smilecoin', '_csrf': csrf_token
        }
        query_response = scraper.post(query_url, data=query_data, headers=headers)
        try: query_result = query_response.json()
        except Exception: return {"status": "error", "message": "query api error"}
            
        flowid = query_result.get('flowid') or query_result.get('data', {}).get('flowid')
        if not flowid: return {"status": "error", "message": "smile.one response rejected."}

        pay_data = {
            '_csrf': csrf_token, 'user_id': user_id, 'zone_id': zone_id, 'pay_methond': 'smilecoin',
            'product_id': product_id, 'channel_method': 'smilecoin', 'flowid': flowid, 'email': '', 'coupon_id': ''
        }
        
        pay_response = scraper.post(pay_url, data=pay_data, headers=headers)
        pay_text = pay_response.text.lower()
        
        if "saldo insuficiente" in pay_text or "insufficient" in pay_text:
            return {"status": "error", "message": "insufficient balance in your account."}
        
        time.sleep(2) 
        
        real_order_id = "not found"
        is_success = False

        try:
            api_params = {'type': 'orderlist', 'p': '1', 'pageSize': '5'}
            hist_res = scraper.get(order_api_url, params=api_params, headers=headers)
            hist_json = hist_res.json()
            
            if 'list' in hist_json and isinstance(hist_json['list'], list) and len(hist_json['list']) > 0:
                for order in hist_json['list']:
                    if str(order.get('user_id')) == str(user_id) and str(order.get('server_id')) == str(zone_id):
                        check_order_id = str(order.get('increment_id', "not found"))
                        if check_order_id not in seen_order_ids: 
                            if str(order.get('order_status', '')).lower() == 'success' or str(order.get('status')) == '1':
                                real_order_id = check_order_id
                                is_success = True
                                break
        except Exception as e:
            pass

        if not is_success:
            try:
                pay_json = pay_response.json()
                code = str(pay_json.get('code', ''))
                status = str(pay_json.get('status', ''))
                if code in ['200', '0', '1'] or status in ['200', '0', '1']:
                    is_success = True
            except: pass

        if is_success:
            return {"status": "success", "ig_name": ig_name, "order_id": real_order_id, "balances": current_balances}
        else:
            return {"status": "error", "message": "payment failed. (not found in order history)"}

    except Exception as e: return {"status": "error", "message": f"system error: {str(e)}"}

# ==========================================
# 4. 🛡️ check authorization function
# ==========================================
def is_authorized(message):
    if message.from_user.id == OWNER_ID:
        return True
    
    db_data = load_data()
    if message.from_user.id in db_data.get("users", []):
        return True
        
    if message.from_user.username:
        username = message.from_user.username.lower()
        if username in db_data.get("users", []):
            return True
            
    return False

# ==========================================
# 10. 💓 heartbeat (session keep-alive) function
# ==========================================
def keep_cookie_alive():
    while True:
        try:
            time.sleep(10 * 60) # runs every 10 minutes
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
            scraper.cookies.update(get_login_cookies())
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://www.smile.one'
            }
            
            response = scraper.get('https://www.smile.one/customer/order', headers=headers)
            
            if "login" not in response.url.lower() and response.status_code == 200:
                print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}] 💓 heartbeat: session is alive!")
            else:
                print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}] ⚠️ heartbeat: session expired. will auto-login on next request.")
        except Exception as e:
            print(f"❌ heartbeat error: {e}")

# ==========================================
# 5. owner commands (users / cookies)
# ==========================================
@bot.message_handler(commands=['add'])
def add_user(message):
    if message.from_user.id != OWNER_ID: return bot.reply_to(message, "❌ you are not the owner.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "⚠️ usage format - `/add <user_id or @username>`", parse_mode="Markdown")
        
    target = parts[1].strip()
    db_data = load_data()
    
    try:
        if target.startswith('@') or not target.isdigit():
            username = target.replace('@', '').lower()
            if username in db_data["users"]:
                bot.reply_to(message, f"⚠️ username `@{username}` is already in the list.", parse_mode="Markdown")
            else:
                db_data["users"].append(username)
                save_data(db_data)
                bot.reply_to(message, f"✅ username `@{username}` has been allowed.", parse_mode="Markdown")
        else:
            new_user_id = int(target)
            if new_user_id in db_data["users"]:
                bot.reply_to(message, f"⚠️ user id `{new_user_id}` is already in the list.", parse_mode="Markdown")
            else:
                db_data["users"].append(new_user_id)
                save_data(db_data)
                bot.reply_to(message, f"✅ user id `{new_user_id}` has been allowed.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ error: {str(e)}")

@bot.message_handler(commands=['remove'])
def remove_user(message):
    if message.from_user.id != OWNER_ID: return bot.reply_to(message, "❌ you are not the owner.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "⚠️ usage format - `/remove <user_id or @username>`", parse_mode="Markdown")
        
    target = parts[1].strip()
    db_data = load_data()
    
    try:
        if target.startswith('@') or not target.isdigit():
            username = target.replace('@', '').lower()
            if username in db_data["users"]:
                db_data["users"].remove(username)
                save_data(db_data)
                bot.reply_to(message, f"✅ username `@{username}` has been removed.", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ that username is not in the list.")
        else:
            remove_user_id = int(target)
            if remove_user_id == OWNER_ID: return bot.reply_to(message, "❌ cannot remove the owner.")
            
            if remove_user_id in db_data["users"]:
                db_data["users"].remove(remove_user_id)
                save_data(db_data)
                bot.reply_to(message, f"✅ user id `{remove_user_id}` has been removed.", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ that user id is not in the list.")
    except Exception as e:
        bot.reply_to(message, f"❌ error: {str(e)}")

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.from_user.id != OWNER_ID: return bot.reply_to(message, "❌ you are not the owner.")
    
    db_data = load_data()
    user_list = []
    
    for u in db_data.get("users", []):
        if str(u).isdigit():
            role = "owner" if int(u) == OWNER_ID else "user"
            user_list.append(f"🔹 id: `{u}` ({role})")
        else:
            user_list.append(f"🔹 username: `@{u}` (user)")
            
    final_text = "\n".join(user_list) if user_list else "no users found."
    bot.reply_to(message, f"📋 **allowed users list:**\n{final_text}", parse_mode="Markdown")

@bot.message_handler(commands=['setcookie'])
def set_cookie_command(message):
    if message.from_user.id != OWNER_ID: 
        return bot.reply_to(message, "❌ you are not the owner.")
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.reply_to(message, "⚠️ **usage format:**\n`/setcookie <long_cookie>`", parse_mode="Markdown")
    
    raw_cookie_str = parts[1].strip()
    try:
        db_data = load_data()
        db_data["cookie"] = raw_cookie_str
        save_data(db_data)
        bot.reply_to(message, f"✅ **new cookie securely saved.**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ error saving cookie:\n{str(e)}")

@bot.message_handler(commands=['balance'])
def check_balance_command(message):
    if not is_authorized(message): return bot.reply_to(message, "❌ unauthorized access.")
    loading_msg = bot.reply_to(message, "⏳ fetching balance...")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies()) 
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://www.smile.one'}
    try:
        balances = get_smile_balance(scraper, headers, 'https://www.smile.one/customer/order')
        report = f"Balance (BR): ${balances.get('br_balance', 0.00):,.2f}\nBalance (PH): ${balances.get('ph_balance', 0.00):,.2f}"
        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=report)
    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ error:\n{str(e)}")

# ==========================================
# 6. 📌 insert activation code command
# ==========================================
@bot.message_handler(func=lambda message: re.match(r"(?i)^/(activecodebr|activecodeph)\b", message.text.strip()))
def handle_activecode(message):
    if not is_authorized(message): return bot.reply_to(message, "❌ unauthorized access.")
    
    match = re.search(r"(?i)^/(activecodebr|activecodeph)\s+([a-zA-Z0-9]+)", message.text.strip())
    
    if not match: 
        return bot.reply_to(message, "⚠️ usage format - `/activecodebr <code>` or `/activecodeph <code>`", parse_mode="Markdown")
    
    command_used = match.group(1).lower()
    activation_code = match.group(2).strip()
    
    if command_used == 'activecodeph':
        page_url = 'https://www.smile.one/ph/customer/activationcode'
        check_url = 'https://www.smile.one/ph/smilecard/pay/checkcard'
        pay_url = 'https://www.smile.one/ph/smilecard/pay/payajax'
        base_origin = 'https://www.smile.one'
        base_referer = 'https://www.smile.one/ph/'
        api_type = "PH"
    else:
        page_url = 'https://www.smile.one/customer/activationcode'
        check_url = 'https://www.smile.one/smilecard/pay/checkcard'
        pay_url = 'https://www.smile.one/smilecard/pay/payajax'
        base_origin = 'https://www.smile.one'
        base_referer = 'https://www.smile.one/'
        api_type = "BR"

    loading_msg = bot.reply_to(message, f"⏳ checking code `{activation_code}` for {api_type} region...", parse_mode="Markdown")
    
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Referer': base_referer,
    }

    try:
        res = scraper.get(page_url, headers=headers)
        
        if "Just a moment" in res.text or "Cloudflare" in res.text:
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="❌ **cloudflare blocked!** re-insert cookie.")
            
        if "login" in res.url.lower():
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="❌ **session expired!** cookie expired. please re-insert using `/setcookie`.")

        soup = BeautifulSoup(res.text, 'html.parser')
        csrf_token = None
        
        csrf_input = soup.find('input', {'name': '_csrf'})
        if csrf_input: csrf_token = csrf_input.get('value')
            
        if not csrf_token:
            meta_tag = soup.find('meta', {'name': 'csrf-token'})
            if meta_tag: csrf_token = meta_tag.get('content')

        if not csrf_token: 
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="❌ csrf token not obtained.")

        ajax_headers = headers.copy()
        ajax_headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': base_origin,
            'Referer': page_url,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        })

        payload = {'_csrf': csrf_token, 'pin': activation_code}
        check_res = scraper.post(check_url, data=payload, headers=ajax_headers)
        
        try:
            check_json = check_res.json()
        except Exception:
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ **api error!** no json response.\nhttp status: {check_res.status_code}")

        code_status = str(check_json.get('code', check_json.get('status', '')))
        code_msg = str(check_json.get('msg', check_json.get('message', '')))
        
        raw_debug = json.dumps(check_json, ensure_ascii=False) 

        if code_status in ['200', '201', '0', '1'] or 'success' in code_msg.lower() or 'ok' in code_msg.lower():
            bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"⏳ code is valid. depositing...", parse_mode="Markdown")
            
            pay_payload = {'_csrf': csrf_token, 'sec': activation_code} 
            pay_res = scraper.post(pay_url, data=pay_payload, headers=ajax_headers)
            
            try:
                pay_json = pay_res.json()
            except Exception:
                return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ **redeem api error!**\nhttp status: {pay_res.status_code}")

            pay_status = str(pay_json.get('code', pay_json.get('status', '')))
            pay_msg = str(pay_json.get('msg', pay_json.get('message', '')))
            raw_pay_debug = json.dumps(pay_json, ensure_ascii=False)
            
            if pay_status in ['200', '0', '1'] or 'success' in pay_msg.lower() or 'ok' in pay_msg.lower():
                bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"✅ **activation success!**\ncode `{activation_code}` successfully inserted ({api_type}).", parse_mode="Markdown")
            else:
                err_text = pay_msg if pay_msg else "unknown reason"
                bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ **redeem failed!**\nreason: {err_text}\n\n*(debug data: {raw_pay_debug})*")
        else:
            if code_status == '201':
                err_text = "invalid code or wrong region"
            else:
                err_text = code_msg if code_msg else "unknown reason"
                
            bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ **check failed!**\nreason: {err_text}\n\n*(debug data: {raw_debug})*")

    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ error: {str(e)}")

# ==========================================
# 7. 📌 check role command (with auto-retry)
# ==========================================
@bot.message_handler(func=lambda message: re.match(r"(?i)^/?role\b", message.text.strip()))
def handle_check_role(message):
    if not is_authorized(message):
        return bot.reply_to(message, "❌ unauthorized access.", parse_mode="Markdown")

    match = re.search(r"(?i)^/?role\s+(\d+)\s*\(\s*(\d+)\s*\)", message.text.strip())
    if not match:
        return bot.reply_to(message, "❌ invalid format:\n(e.g. - `/role 184224272 (2931)`)", parse_mode="Markdown")

    game_id = match.group(1).strip()
    zone_id = match.group(2).strip()
    
    loading_msg = bot.reply_to(message, "⏳ searching for account and region...")

    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())
    
    main_url = 'https://www.smile.one/merchant/mobilelegends'
    checkrole_url = 'https://www.smile.one/merchant/mobilelegends/checkrole'
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': main_url, 'Origin': 'https://www.smile.one'}

    try:
        res = scraper.get(main_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token:
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="❌ csrf token not found. insert new cookie using /setcookie.")

        check_data = {
            'user_id': game_id, 
            'zone_id': zone_id, 
            '_csrf': csrf_token
        }
        
        role_response = scraper.post(checkrole_url, data=check_data, headers=headers)
        
        try: 
            role_result = role_response.json()
        except: 
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="❌ cannot verify. (smile api error)")
            
        ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
        
        if not ig_name or str(ig_name).strip() == "":
            real_error = role_result.get('msg') or role_result.get('message') or "account not found."
            if "login" in str(real_error).lower() or "unauthorized" in str(real_error).lower():
                return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text="⚠️ cookie expired. please insert new cookie using `/setcookie`.")
            return bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ **invalid account:**\n{real_error}")

        smile_region = role_result.get('zone') or role_result.get('region') or role_result.get('data', {}).get('zone') or "Unknown"

        pizzo_region = "Unknown"
        try:
            pizzo_headers = {
                'authority': 'pizzoshop.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://pizzoshop.com',
                'referer': 'https://pizzoshop.com/mlchecker',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            scraper.get("https://pizzoshop.com/mlchecker", headers=pizzo_headers, timeout=10)
            payload = {'user_id': game_id, 'zone_id': zone_id}
            
            pizzo_res = scraper.post("https://pizzoshop.com/mlchecker/check", data=payload, headers=pizzo_headers, timeout=15)
            pizzo_soup = BeautifulSoup(pizzo_res.text, 'html.parser')
            table = pizzo_soup.find('table', class_='table-modern')
            
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        header = th.get_text(strip=True).lower()
                        value = td.get_text(strip=True)
                        if 'region id' in header or 'region' in header:
                            pizzo_region = value
        except Exception as e:
            pass 

        final_region = pizzo_region if pizzo_region != "Unknown" else smile_region

        report = f"ɢᴀᴍᴇ ɪᴅ : {game_id} ({zone_id})\n"
        report += f"ɪɢɴ ɴᴀᴍᴇ : {ig_name}\n"
        report += f"ʀᴇɢɪᴏɴ : {final_region}"

        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=report)

    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ system error: {str(e)}")


# ==========================================
# 🌟 auto-detect region function
# ==========================================
def get_account_region(game_id, zone_id):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())
    main_url = 'https://www.smile.one/merchant/mobilelegends'
    checkrole_url = 'https://www.smile.one/merchant/mobilelegends/checkrole'
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': main_url, 'Origin': 'https://www.smile.one'}

    try:
        res = scraper.get(main_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')

        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token: return "BR" 

        check_data = {
            'user_id': game_id,
            'zone_id': zone_id,
            '_csrf': csrf_token
        }

        role_response = scraper.post(checkrole_url, data=check_data, headers=headers)
        role_result = role_response.json()

        smile_region = str(role_result.get('zone') or role_result.get('region') or role_result.get('data', {}).get('zone') or "").lower()

        if "philippines" in smile_region or "ph" in smile_region:
            return "PH"
        return "BR"
    except Exception:
        return "BR" 

# ==========================================
# 8. command handler (msc auto-detect - mlbb)
# ==========================================
@bot.message_handler(func=lambda message: re.match(r"(?i)^msc\s+\d+", message.text.strip()))
def handle_direct_buy(message):
    if not is_authorized(message):
        return bot.reply_to(message, f"not authorized user. ❌")

    try:
        lines = message.text.strip().split('\n')
        telegram_user = message.from_user.username
        username_display = f"@{telegram_user}" if telegram_user else "Unknown"
        
        for line in lines:
            line = line.strip()
            if not line: continue 
                
            match = re.search(r"(?i)^(?:msc\s+)?(\d+)\s*\(\s*(\d+)\s*\)\s*([a-zA-Z0-9_]+)", line)
            if not match:
                bot.reply_to(message, f"invalid format: `{line}`\n(e.g. - 12345678 (1234) 11)")
                continue
                
            game_id = match.group(1)
            zone_id = match.group(2)
            item_input = match.group(3).lower() 
            
            if item_input in BR_PACKAGES:
                currency_name = 'BR'
                active_packages = BR_PACKAGES
                used_balance_key = 'br_balance'
            elif item_input in PH_PACKAGES:
                currency_name = 'PH'
                active_packages = PH_PACKAGES
                used_balance_key = 'ph_balance'
            else:
                bot.reply_to(message, f"no package found for selected '{item_input}'.")
                continue
                
            items_to_buy = active_packages[item_input]
            
            loading_msg = bot.reply_to(message, f"recharging diam͟o͟n͟d͟ ● ᥫ᭡")
            
            order_ids_str = ""
            total_price = 0.0
            success_count = 0
            fail_count = 0
            ig_name = "Unknown"
            initial_used_balance = 0.0
            error_msg = ""
            
            seen_order_ids = [] 
            cached_session = None # keep cache for speed up
            
            for item in items_to_buy:
                product_id = item['pid']
                item_price = item['price']
                
                result = process_smile_one_order(game_id, zone_id, product_id, currency_name, item_price, seen_order_ids, cached_session)
                
                if result['status'] == 'success':
                    if not cached_session:
                        initial_used_balance = result['balances'][used_balance_key]
                        ig_name = result['ig_name']
                    
                    success_count += 1
                    total_price += item_price
                    
                    new_id = result['order_id']
                    seen_order_ids.append(new_id)
                    order_ids_str += f"{new_id}\n" 
                    
                    # deduct spent balance and save session data
                    result['balances'][used_balance_key] -= float(item_price)
                    cached_session = {
                        'csrf_token': result['csrf_token'],
                        'ig_name': ig_name,
                        'balances': result['balances']
                    }
                    
                    time.sleep(random.randint(1, 5)) 
                else:
                    fail_count += 1
                    error_msg = result['message']
                    break 
            
            if success_count > 0:
                now = datetime.datetime.now(MMT)
                date_str = now.strftime("%m/%d/%Y, %I:%M:%S %p")
                final_used_balance = initial_used_balance - total_price
                
                # clear html symbols to prevent errors
                safe_ig_name = html.escape(str(ig_name))
                safe_username = html.escape(str(username_display))
                
                # 👈 using blockquote and monospace font as shown in picture
                report = (
                    f"<blockquote><code>=== ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ ʀᴇᴘᴏʀᴛ ===\n\n"
                    f"ᴏʀᴅᴇʀ sᴛᴀᴛᴜs: ✅ Sᴜᴄᴄᴇss\n"
                    f"ɢᴀᴍᴇ ɪᴅ: {game_id} {zone_id}\n"
                    f"ɪɢ ɴᴀᴍᴇ: {safe_ig_name}\n"
                    f"sᴇʀɪᴀʟ:\n{order_ids_str.strip()}\n"
                    f"ɪᴛᴇᴍ: {item_input} 💎\n"
                    f"sᴘᴇɴᴛ: {total_price:.2f} 🪙\n\n"
                    f"ᴅᴀᴛᴇ: {date_str}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ: {safe_username}\n"
                    f"sᴘᴇɴᴛ : ${total_price:.2f}\n"
                    f"ɪɴɪᴛɪᴀʟ: ${initial_used_balance:,.2f}\n"
                    f"ғɪɴᴀʟ : ${final_used_balance:,.2f}\n\n"
                    f"Sᴜᴄᴄᴇss {success_count} / Fᴀɪʟ {fail_count}</code></blockquote>"
                )

                bot.edit_message_text(
                    chat_id=message.chat.id, 
                    message_id=loading_msg.message_id, 
                    text=report, 
                    parse_mode="HTML" 
                )
                
                if fail_count > 0:
                    bot.reply_to(message, f"⚠️ partially successful.\nerror: {error_msg}")
            else:
                bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ order failed:\n{error_msg}")

    except Exception as e:
        bot.reply_to(message, f"system error: {str(e)}")

# ==========================================
# 8.2 command handler (mcc - magic chess go go)
# ==========================================
@bot.message_handler(func=lambda message: re.match(r"(?i)^mcc\s+\d+", message.text.strip()))
def handle_mcc_buy(message):
    if not is_authorized(message):
        return bot.reply_to(message, f"❌ you do not have permission to use this bot.")

    try:
        lines = message.text.strip().split('\n')
        telegram_user = message.from_user.username
        username_display = f"@{telegram_user}" if telegram_user else "Unknown"
        
        for line in lines:
            line = line.strip()
            if not line: continue 
                
            match = re.search(r"(?i)^(?:mcc\s+)?(\d+)\s*\(\s*(\d+)\s*\)\s*([a-zA-Z0-9_]+)", line)
            if not match:
                bot.reply_to(message, f"invalid format: `{line}`\n(e.g. - mcc 12345678 (1234) 86)")
                continue
                
            game_id = match.group(1)
            zone_id = match.group(2)
            item_input = match.group(3).lower() 
            
            if item_input not in globals().get('MCC_PACKAGES', {}):
                bot.reply_to(message, f"❌ no magic chess package for selected '{item_input}'.")
                continue
                
            items_to_buy = MCC_PACKAGES[item_input]
            
            loading_msg = bot.reply_to(message, f"placing order for magic chess ● ᥫ᭡")
            
            order_ids_str = ""
            total_price = 0.0
            success_count = 0
            fail_count = 0
            ig_name = "Unknown"
            initial_used_balance = 0.0
            error_msg = ""
            first_order = True
            
            seen_order_ids = []
            
            for item in items_to_buy:
                product_id = item['pid']
                item_price = item['price']
                
                result = process_mcc_order(game_id, zone_id, product_id, item_price, seen_order_ids)
                
                if result['status'] == 'success':
                    if first_order:
                        initial_used_balance = result['balances']['br_balance']
                        ig_name = result['ig_name']
                        first_order = False
                    
                    success_count += 1
                    total_price += item_price
                    
                    new_id = result['order_id']
                    seen_order_ids.append(new_id)
                    order_ids_str += f"{new_id}\n" 
                    
                    time.sleep(random.randint(2, 5)) 
                else:
                    fail_count += 1
                    error_msg = result['message']
                    break 
            
            if success_count > 0:
                now = datetime.datetime.now(MMT)
                date_str = now.strftime("%m/%d/%Y, %I:%M:%S %p")
                final_used_balance = initial_used_balance - total_price
                
                safe_ig_name = html.escape(str(ig_name))
                safe_username = html.escape(str(username_display))
                
                report = (
                    f"<blockquote><code>mcc {game_id} ({zone_id}) {item_input}\n"
                    f"=== ᴛʀᴀɴsᴀᴄᴛɪᴏɴ ʀᴇᴘᴏʀᴛ ===\n\n"
                    f"ᴏʀᴅᴇʀ sᴛᴀᴛᴜs: ✅ Sᴜᴄᴄᴇss\n"
                    f"ɢᴀᴍᴇ: ᴍᴀɢɪᴄ ᴄʜᴇss ɢᴏ ɢᴏ\n"
                    f"ɢᴀᴍᴇ ɪᴅ: {game_id} {zone_id}\n"
                    f"ɪɢ ɴᴀᴍᴇ: {safe_ig_name}\n"
                    f"sᴇʀɪᴀʟ:\n{order_ids_str.strip()}\n"
                    f"ɪᴛᴇᴍ: {item_input} 💎\n"
                    f"sᴘᴇɴᴛ: {total_price:.2f} 🪙\n\n"
                    f"ᴅᴀᴛᴇ: {date_str}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ: {safe_username}\n"
                    f"sᴘᴇɴᴛ: ${total_price:.2f}\n"
                    f"ɪɴɪᴛɪᴀʟ: ${initial_used_balance:,.2f}\n"
                    f"ғɪɴᴀʟ: ${final_used_balance:,.2f}\n\n"
                    f"Sᴜᴄᴄᴇss {success_count} / Fᴀɪʟ {fail_count}</code></blockquote>"
                )

                bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=report, parse_mode="HTML")
                
                if fail_count > 0:
                    bot.reply_to(message, f"⚠️ partially successful.\nerror: {error_msg}")
            else:
                bot.edit_message_text(chat_id=message.chat.id, message_id=loading_msg.message_id, text=f"❌ order failed:\n{error_msg}")

    except Exception as e:
        bot.reply_to(message, f"system error: {str(e)}")


# ==========================================
# 9. start bot / default command
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        tg_id = str(message.from_user.id)
        
        first_name = message.from_user.first_name or ""
        last_name = message.from_user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = "User"
            
        safe_full_name = full_name.replace('<', '').replace('>', '')
        username_display = f'<a href="tg://user?id={tg_id}">{safe_full_name}</a>'
        
        if is_authorized(message):
            status = "🟢 Aᴄᴛɪᴠᴇ"
        else:
            status = "🔴 Nᴏᴛ Aᴄᴛɪᴠᴇ"
            
        welcome_text = (
            f"ʜᴇʏ ʙᴀʙʏ🥺\n\n"
            f"Usᴇʀɴᴀᴍᴇ: {username_display}\n"
            f"𝐈𝐃: <code>{tg_id}</code>\n"
            f"Sᴛᴀᴛᴜs: {status}\n\n"
            f"Cᴏɴᴛᴀᴄᴛ ᴜs: @iwillgoforwardsalone"
        )
        
        bot.reply_to(message, welcome_text, parse_mode="HTML")
        
    except Exception as e:
        print(f"start cmd error: {e}")
        
        fallback_text = (
            f"ʜᴇʏ ʙᴀʙʏ🥺\n\n"
            f"Usᴇʀɴᴀᴍᴇ: {full_name}\n"
            f"𝐈𝐃: `{tg_id}`\n"
            f"Sᴛᴀᴛᴜs: {status}\n\n"
            f"Cᴏɴᴛᴀᴄᴛ ᴜs: @iwillgoforwardsalone"
        )
        bot.reply_to(message, fallback_text)

if __name__ == '__main__':
    print("clearing old webhooks if any...")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
        
    print("starting heartbeat thread for session keep-alive...")
    threading.Thread(target=keep_cookie_alive, daemon=True).start()

    print("bot is successfully running (with playwright auto-login & mcc)...")
    bot.infinity_polling()
