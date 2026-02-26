# wanglin.py (Updated: Single Shared Wallet System & UI Match)
import io
import os
import re
import datetime
import json
import time
import random
import html
import cloudscraper
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import asyncio
from playwright.async_api import async_playwright

# 🟢 Pyrogram Imports
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# ==========================================
# 📌 ENVIRONMENT VARIABLES
# ==========================================
load_dotenv() 

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = int(os.getenv('API_ID', 123456))  
API_HASH = os.getenv('API_HASH', "your_api_hash_here") 
OWNER_ID = int(os.getenv('OWNER_ID', 1318826936)) 
FB_EMAIL = os.getenv('FB_EMAIL')
FB_PASS = os.getenv('FB_PASS')

if not BOT_TOKEN:
    print("❌ Error: BOT_TOKEN is missing in the .env file.")
    exit()

MMT = datetime.timezone(datetime.timedelta(hours=6, minutes=30))

# 🟢 Initialize Pyrogram Client
app = Client(
    "smile_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

transaction_lock = asyncio.Lock()

# ==========================================
# 🗄️ LOCAL JSON DATABASE SETUP (SHARED WALLET)
# ==========================================
DB_FILE = 'database.json'

def load_data():
    if not os.path.exists(DB_FILE):
        return {
            "users": [str(OWNER_ID)], 
            "shared_wallet": {"br_balance": 0.0, "ph_balance": 0.0}, 
            "cookie": "", 
            "orders": []
        }
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Migrate old Dict format to List format for users
        if "users" in data and isinstance(data["users"], dict):
            data["users"] = list(data["users"].keys())
            save_data(data)
            
        if "users" not in data:
            data["users"] = [str(OWNER_ID)]
        if "shared_wallet" not in data:
            data["shared_wallet"] = {"br_balance": 0.0, "ph_balance": 0.0}
        if "orders" not in data:
            data["orders"] = []
            
        return data
    except Exception:
        return {
            "users": [str(OWNER_ID)], 
            "shared_wallet": {"br_balance": 0.0, "ph_balance": 0.0}, 
            "cookie": "", 
            "orders": []
        }

def save_data(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Error saving database: {e}")

# --- SHARED WALLET & USER ACCESS CONTROL FUNCTIONS ---
async def add_allowed_user(target):
    data = load_data()
    target_str = str(target).lower().replace('@', '')
    if target_str not in data["users"]:
        data["users"].append(target_str)
        save_data(data)
        return True
    return False

async def remove_allowed_user(target):
    data = load_data()
    target_str = str(target).lower().replace('@', '')
    if target_str in data["users"]:
        data["users"].remove(target_str)
        save_data(data)
        return True
    return False

async def get_allowed_users():
    return load_data().get("users", [])

async def get_shared_wallet():
    return load_data().get("shared_wallet", {"br_balance": 0.0, "ph_balance": 0.0})

async def update_shared_wallet(br_amount=0.0, ph_amount=0.0):
    data = load_data()
    data["shared_wallet"]["br_balance"] = round(data["shared_wallet"].get("br_balance", 0.0) + float(br_amount), 2)
    data["shared_wallet"]["ph_balance"] = round(data["shared_wallet"].get("ph_balance", 0.0) + float(ph_amount), 2)
    save_data(data)
# --------------------------------------

async def get_main_cookie():
    return load_data().get("cookie", "")

async def update_main_cookie(cookie_str):
    data = load_data()
    data["cookie"] = cookie_str
    save_data(data)

async def save_order(tg_id, game_id, zone_id, item_name, price, order_id, status="success"):
    data = load_data()
    if "orders" not in data: data["orders"] = []
    now = datetime.datetime.now(MMT)
    
    order_data = {
        "tg_id": str(tg_id),
        "game_id": str(game_id),
        "zone_id": str(zone_id),
        "item_name": item_name,
        "price": round(float(price), 2),
        "order_id": str(order_id),
        "status": status,
        "date_str": now.strftime("%I:%M:%S %p %d.%m.%Y"),
        "timestamp": now.timestamp()
    }
    data["orders"].append(order_data)
    
    # Keep only the latest 200 orders globally or per user (keeping per user limit)
    user_orders = [o for o in data["orders"] if o.get("tg_id") == str(tg_id)]
    other_orders = [o for o in data["orders"] if o.get("tg_id") != str(tg_id)]
    
    if len(user_orders) > 200:
        user_orders.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        user_orders = user_orders[:200]
        
    data["orders"] = other_orders + user_orders
    save_data(data)

async def get_user_history(tg_id, limit=200):
    data = load_data()
    orders = data.get("orders", [])
    user_orders = [o for o in orders if o.get("tg_id") == str(tg_id)]
    user_orders.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return user_orders[:limit]

async def clear_user_history(tg_id):
    data = load_data()
    orders = data.get("orders", [])
    initial_len = len(orders)
    data["orders"] = [o for o in orders if o.get("tg_id") != str(tg_id)]
    save_data(data)
    return initial_len - len(data["orders"])

# ==========================================
# 🍪 MAIN SCRAPER (OWNER'S COOKIE ONLY)
# ==========================================
async def get_main_scraper():
    raw_cookie = await get_main_cookie()
    cookie_dict = {}
    if raw_cookie:
        for item in raw_cookie.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                cookie_dict[k] = v
                
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    if cookie_dict:
        scraper.cookies.update(cookie_dict)
    return scraper

# ==========================================
# 🤖 PLAYWRIGHT AUTO-LOGIN (FACEBOOK) [FULLY ASYNC]
# ==========================================
async def auto_login_and_get_cookie():
    if not FB_EMAIL or not FB_PASS:
        print("❌ FB_EMAIL and FB_PASS are missing in .env.")
        return False
        
    print("Logging in with Facebook to fetch new Cookie...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            page = await context.new_page()
            
            await page.goto("https://www.smile.one/customer/login")
            await asyncio.sleep(5) 
            
            async with context.expect_page() as popup_info:
                await page.locator("a.login-btn-facebook, a[href*='facebook.com']").first.click()
            
            fb_popup = await popup_info.value
            await fb_popup.wait_for_load_state()
            
            await asyncio.sleep(2)
            await fb_popup.fill('input[name="email"]', FB_EMAIL)
            await asyncio.sleep(1)
            await fb_popup.fill('input[name="pass"]', FB_PASS)
            await asyncio.sleep(1)
            
            await fb_popup.click('button[name="login"], input[name="login"]')
            
            try:
                await page.wait_for_url("**/customer/order**", timeout=30000)
                print("✅ Auto-Login successful. Saving Cookie...")
                
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                raw_cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                
                await update_main_cookie(raw_cookie_str)
                await browser.close()
                return True
            except Exception as wait_e:
                print(f"❌ Did not reach the Order page. (Possible Facebook Checkpoint): {wait_e}")
                await browser.close()
                return False
            
    except Exception as e:
        print(f"❌ Error during Auto-Login: {e}")
        return False

# ==========================================
# 📌 PACKAGES
# ==========================================
DOUBLE_DIAMOND_PACKAGES = {
    '55': [{'pid': '22590', 'price': 39.0, 'name': '50+50 💎'}],
    '165': [{'pid': '22591', 'price': 116.9, 'name': '150+150 💎'}],
    '275': [{'pid': '22592', 'price': 187.5, 'name': '250+250 💎'}],
    '565': [{'pid': '22593', 'price': 385, 'name': '500+500 💎'}],
}

BR_PACKAGES = {
    '86': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}],
    '172': [{'pid': '23', 'price': 122.0, 'name': '172 💎'}],
    '257': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '343': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '429': [{'pid': '23', 'price': 122.0, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '514': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '600': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}],
    '706': [{'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '878': [{'pid': '23', 'price': 122.0, 'name': '172 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '963': [{'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '1049': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '1135': [{'pid': '23', 'price': 122.0, 'name': '172 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '1412': [{'pid': '26', 'price': 480.0, 'name': '706 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '1584': [{'pid': '23', 'price': 122.0, 'name': '172 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '1755': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '2195': [{'pid': '27', 'price': 1453.0, 'name': '2195 💎'}],
    '2538': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '27', 'price': 1453.0, 'name': '2195 💎'}],
    '2901': [{'pid': '27', 'price': 1453.0, 'name': '2195 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}],
    '3244': [{'pid': '13', 'price': 61.5, 'name': '86 💎'}, {'pid': '25', 'price': 177.5, 'name': '257 💎'}, {'pid': '26', 'price': 480.0, 'name': '706 💎'}, {'pid': '27', 'price': 1453.0, 'name': '2195 💎'}],
    '3688': [{'pid': '28', 'price': 2424.0, 'name': '3688 💎'}],
    '5532': [{'pid': '29', 'price': 3660.0, 'name': '5532 💎'}],
    '9288': [{'pid': '30', 'price': 6079.0, 'name': '9288 💎'}],
    'meb': [{'pid': '26556', 'price': 196.5, 'name': 'Epic Monthly Package'}],
    'tp': [{'pid': '33', 'price': 402.5, 'name': 'Twilight Passage'}],
    'web': [{'pid': '26555', 'price': 39.0, 'name': 'Elite Weekly Paackage'}],
    'wp': [{'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp2': [{'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp3': [{'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp4': [{'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp5': [{'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '16642', 'price': 76.0, 'name': 'Weekly Pass'}],
}

PH_PACKAGES = {
    '11': [{'pid': '212', 'price': 9.50, 'name': '11 💎'}],
    '22': [{'pid': '213', 'price': 19.0, 'name': '22 💎'}],
    '56': [{'pid': '214', 'price': 47.50, 'name': '56 💎'}],
    '112': [{'pid': '214', 'price': 47.50, 'name': '56 💎'}, {'pid': '214', 'price': 47.50, 'name': '56 💎'}],
    'pwp': [{'pid': '16641', 'price': 95.00, 'name': 'Weekly Pass'}],
}

MCC_PACKAGES = {
    '86': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}],
    '172': [{'pid': '23826', 'price': 125.0, 'name': '172 💎'}],
    '257': [{'pid': '23827', 'price': 187.0, 'name': '257 💎'}],
    '343': [{'pid': '23828', 'price': 250.0, 'name': '343 💎'}],
    '429': [{'pid': '23826', 'price': 122.0, 'name': '172 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}],
    '516': [{'pid': '23829', 'price': 375.0, 'name': '516 💎'}],
    '600': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23827', 'price': 177.5, 'name': '257 💎'}],
    '706': [{'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '878': [{'pid': '23826', 'price': 125.0, 'name': '172 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '963': [{'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '1049': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '1135': [{'pid': '23826', 'price': 125.0, 'name': '172 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '1346': [{'pid': '23831', 'price': 937.5, 'name': '1346 💎'}],
    '1412': [{'pid': '23830', 'price': 500.0, 'name': '706 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '1584': [{'pid': '23826', 'price': 125.0, 'name': '172 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}, {'pid': '23830', 'price': 480.0, 'name': '706 💎'}],
    '1755': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '1825': [{'pid': '23832', 'price': 1250.0, 'name': '1825 💎'}],
    '2195': [{'pid': '23833', 'price': 1500.0, 'name': '2195 💎'}],
    '2538': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23833', 'price': 1500.0, 'name': '2195 💎'}],
    '2901': [{'pid': '23833', 'price': 1500.0, 'name': '2195 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}],
    '3244': [{'pid': '23825', 'price': 62.5, 'name': '86 💎'}, {'pid': '23827', 'price': 187.0, 'name': '257 💎'}, {'pid': '23830', 'price': 500.0, 'name': '706 💎'}, {'pid': '23833', 'price': 1500.0, 'name': '2195 💎'}],
    '3688': [{'pid': '23834', 'price': 2500.0, 'name': '3688 💎'}],
    '5532': [{'pid': '23835', 'price': 3750.0, 'name': '5532 💎'}],
    '9288': [{'pid': '23836', 'price': 6250.0, 'name': '9288 💎'}],
    'b150': [{'pid': '23838', 'price': 120.0, 'name': '150+150 💎'}],
    'b250': [{'pid': '23839', 'price': 200.0, 'name': '250+250 💎'}],
    'b50': [{'pid': '23837', 'price': 40.0, 'name': '50+50 💎'}],
    'b500': [{'pid': '23840', 'price': 400, 'name': '500+500 💎'}],
    'wp': [{'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp2': [{'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp3': [{'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp4': [{'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}],
    'wp5': [{'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}, {'pid': '23841', 'price': 76.0, 'name': 'Weekly Pass'}],
}

# ==========================================
# 2. FUNCTION TO GET REAL BALANCE (ASYNC WRAPPED)
# ==========================================
async def get_smile_balance(scraper, headers, balance_url='https://www.smile.one/customer/order'):
    balances = {'br_balance': 0.00, 'ph_balance': 0.00}
    try:
        response = await asyncio.to_thread(scraper.get, balance_url, headers=headers)
        br_match = re.search(r'(?i)(?:Balance|Saldo)[\s:]*?<\/p>\s*<p>\s*([\d\.,]+)', response.text)
        if br_match: balances['br_balance'] = float(br_match.group(1).replace(',', ''))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            main_balance_div = soup.find('div', class_='balance-coins')
            if main_balance_div:
                p_tags = main_balance_div.find_all('p')
                if len(p_tags) >= 2: balances['br_balance'] = float(p_tags[1].text.strip().replace(',', ''))
                    
        ph_match = re.search(r'(?i)Saldo PH[\s:]*?<\/span>\s*<span>\s*([\d\.,]+)', response.text)
        if ph_match: balances['ph_balance'] = float(ph_match.group(1).replace(',', ''))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            ph_balance_container = soup.find('div', id='all-balance')
            if ph_balance_container:
                span_tags = ph_balance_container.find_all('span')
                if len(span_tags) >= 2: balances['ph_balance'] = float(span_tags[1].text.strip().replace(',', ''))
    except Exception: pass
    return balances

# ==========================================
# 3. SMILE.ONE SCRAPER FUNCTION (MLBB) [FULLY ASYNC & FIXED FALSE POSITIVE]
# ==========================================
async def process_smile_one_order(game_id, zone_id, product_id, currency_name, seen_order_ids=None):
    if seen_order_ids is None:
        seen_order_ids = []
        
    scraper = await get_main_scraper()

    if currency_name == 'PH':
        main_url = 'https://www.smile.one/ph/merchant/mobilelegends'
        checkrole_url = 'https://www.smile.one/ph/merchant/mobilelegends/checkrole'
        query_url = 'https://www.smile.one/ph/merchant/mobilelegends/query'
        pay_url = 'https://www.smile.one/ph/merchant/mobilelegends/pay'
        order_api_url = 'https://www.smile.one/ph/customer/activationcode/codelist'
    else:
        main_url = 'https://www.smile.one/merchant/mobilelegends'
        checkrole_url = 'https://www.smile.one/merchant/mobilelegends/checkrole'
        query_url = 'https://www.smile.one/merchant/mobilelegends/query'
        pay_url = 'https://www.smile.one/merchant/mobilelegends/pay'
        order_api_url = 'https://www.smile.one/customer/activationcode/codelist'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest', 
        'Referer': main_url, 
        'Origin': 'https://www.smile.one'
    }

    try:
        response = await asyncio.to_thread(scraper.get, main_url, headers=headers)
        if response.status_code in [403, 503] or "cloudflare" in response.text.lower():
             return {"status": "error", "message": "Blocked by Cloudflare."}

        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token: return {"status": "error", "message": "CSRF Token not found. Add a new Cookie using /setcookie."}

        check_data = {'user_id': game_id, 'zone_id': zone_id, '_csrf': csrf_token}
        role_response_raw = await asyncio.to_thread(scraper.post, checkrole_url, data=check_data, headers=headers)
        try:
            role_result = role_response_raw.json()
            ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
            if not ig_name or str(ig_name).strip() == "":
                real_error = role_result.get('msg') or role_result.get('message') or "Account not found."
                return {"status": "error", "message": f"❌ Invalid Account: {real_error}"}
        except Exception: return {"status": "error", "message": "Check Role API Error: Cannot verify account."}

        query_data = {'user_id': game_id, 'zone_id': zone_id, 'pid': product_id, 'checkrole': '', 'pay_methond': 'smilecoin', 'channel_method': 'smilecoin', '_csrf': csrf_token}
        query_response_raw = await asyncio.to_thread(scraper.post, query_url, data=query_data, headers=headers)
        
        try: query_result = query_response_raw.json()
        except Exception: return {"status": "error", "message": "Query API Error"}
            
        flowid = query_result.get('flowid') or query_result.get('data', {}).get('flowid')
        
        if not flowid:
            real_error = query_result.get('msg') or query_result.get('message') or ""
            if "login" in str(real_error).lower() or "unauthorized" in str(real_error).lower():
                print("⚠️ Cookie expired. Starting Auto-Login...")
                success = await auto_login_and_get_cookie()
                if success: return {"status": "error", "message": "Session renewed. Please enter the command again."}
                else: return {"status": "error", "message": "❌ Auto-Login failed. Please provide /setcookie again."}
            return {"status": "error", "message": f"❌ **Invalid Account/Server:** {real_error}"}

        pay_data = {'_csrf': csrf_token, 'user_id': game_id, 'zone_id': zone_id, 'pay_methond': 'smilecoin', 'product_id': product_id, 'channel_method': 'smilecoin', 'flowid': flowid, 'email': '', 'coupon_id': ''}
        pay_response_raw = await asyncio.to_thread(scraper.post, pay_url, data=pay_data, headers=headers)
        
        is_success = False
        real_order_id = "Not found"
        
        try:
            pay_json = pay_response_raw.json()
            code = str(pay_json.get('code', pay_json.get('status', '')))
            msg = str(pay_json.get('msg', pay_json.get('message', ''))).lower()
            
            if code in ['200', '0', '1'] or 'success' in msg:
                is_success = True
                real_order_id = str(pay_json.get('data', {}).get('order_id', 'Not found'))
            else:
                err_text = pay_json.get('msg', 'Insufficient balance or API Error')
                return {"status": "error", "message": f"Payment Failed: {err_text}"}
        except Exception:
            pay_text = pay_response_raw.text.lower()
            if 'success' in pay_text or 'sucesso' in pay_text:
                is_success = True
            else:
                return {"status": "error", "message": "Payment Failed: Insufficient balance or Blocked."}

        if is_success and real_order_id in ["Not found", "", "None"]:
            await asyncio.sleep(2) 
            try:
                hist_res_raw = await asyncio.to_thread(scraper.get, order_api_url, params={'type': 'orderlist', 'p': '1', 'pageSize': '5'}, headers=headers)
                hist_json = hist_res_raw.json()
                if 'list' in hist_json and len(hist_json['list']) > 0:
                    for order in hist_json['list']:
                        increment_id = str(order.get('increment_id', ''))
                        
                        if increment_id in seen_order_ids:
                            continue
                            
                        if str(order.get('user_id')) == str(game_id) and str(order.get('server_id')) == str(zone_id):
                            if str(order.get('order_status', '')).lower() == 'success' or str(order.get('status')) == '1':
                                real_order_id = increment_id
                                break
            except Exception: pass

        if is_success:
            if real_order_id in ["Not found", "", "None"]:
                real_order_id = f"AUTO_{int(time.time())}"
            return {"status": "success", "ig_name": ig_name, "order_id": real_order_id}
        else:
            return {"status": "error", "message": "Payment failed (Unknown Error)."}

    except Exception as e: return {"status": "error", "message": f"System Error: {str(e)}"}

# 🌟 NEW: 3.1 MAGIC CHESS SCRAPER FUNCTION [FULLY ASYNC & FIXED FALSE POSITIVE] 🌟
async def process_mcc_order(game_id, zone_id, product_id, seen_order_ids=None):
    if seen_order_ids is None:
        seen_order_ids = []
        
    scraper = await get_main_scraper()

    main_url = 'https://www.smile.one/br/merchant/game/magicchessgogo'
    checkrole_url = 'https://www.smile.one/br/merchant/game/checkrole'
    query_url = 'https://www.smile.one/br/merchant/game/query'
    pay_url = 'https://www.smile.one/br/merchant/game/pay'
    order_api_url = 'https://www.smile.one/br/customer/activationcode/codelist'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest', 
        'Referer': main_url, 
        'Origin': 'https://www.smile.one'
    }

    try:
        response = await asyncio.to_thread(scraper.get, main_url, headers=headers)
        if response.status_code in [403, 503] or "cloudflare" in response.text.lower():
             return {"status": "error", "message": "Blocked by Cloudflare."}

        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token: return {"status": "error", "message": "CSRF Token not found. Add a new Cookie using /setcookie."}

        check_data = {'user_id': game_id, 'zone_id': zone_id, '_csrf': csrf_token}
        role_response_raw = await asyncio.to_thread(scraper.post, checkrole_url, data=check_data, headers=headers)
        try:
            role_result = role_response_raw.json()
            ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
            if not ig_name or str(ig_name).strip() == "":
                return {"status": "error", "message": " Account not found."}
        except Exception: return {"status": "error", "message": "⚠️ Check Role API Error: Cannot verify account."}

        query_data = {'user_id': game_id, 'zone_id': zone_id, 'pid': product_id, 'checkrole': '', 'pay_methond': 'smilecoin', 'channel_method': 'smilecoin', '_csrf': csrf_token}
        query_response_raw = await asyncio.to_thread(scraper.post, query_url, data=query_data, headers=headers)
        
        try: query_result = query_response_raw.json()
        except Exception: return {"status": "error", "message": "Query API Error"}
            
        flowid = query_result.get('flowid') or query_result.get('data', {}).get('flowid')
        
        if not flowid:
            real_error = query_result.get('msg') or query_result.get('message') or ""
            if "login" in str(real_error).lower() or "unauthorized" in str(real_error).lower():
                print("⚠️ Cookie expired. Starting Auto-Login...")
                success = await auto_login_and_get_cookie()
                if success: return {"status": "error", "message": "⚠️ Session renewed. Please enter the command again."}
                else: return {"status": "error", "message": "Auto-Login failed. Please provide /setcookie again."}
            return {"status": "error", "message": "Invalid account or unable to purchase."}

        pay_data = {'_csrf': csrf_token, 'user_id': game_id, 'zone_id': zone_id, 'pay_methond': 'smilecoin', 'product_id': product_id, 'channel_method': 'smilecoin', 'flowid': flowid, 'email': '', 'coupon_id': ''}
        pay_response_raw = await asyncio.to_thread(scraper.post, pay_url, data=pay_data, headers=headers)
        
        is_success = False
        real_order_id = "Not found"
        
        try:
            pay_json = pay_response_raw.json()
            code = str(pay_json.get('code', pay_json.get('status', '')))
            msg = str(pay_json.get('msg', pay_json.get('message', ''))).lower()
            
            if code in ['200', '0', '1'] or 'success' in msg:
                is_success = True
                real_order_id = str(pay_json.get('data', {}).get('order_id', 'Not found'))
            else:
                err_text = pay_json.get('msg', 'Insufficient balance or API Error')
                return {"status": "error", "message": f"Payment Failed: {err_text}"}
        except Exception:
            pay_text = pay_response_raw.text.lower()
            if 'success' in pay_text or 'sucesso' in pay_text:
                is_success = True
            else:
                return {"status": "error", "message": "Payment Failed: Insufficient balance or Blocked."}

        if is_success and real_order_id in ["Not found", "", "None"]:
            await asyncio.sleep(2) 
            try:
                hist_res_raw = await asyncio.to_thread(scraper.get, order_api_url, params={'type': 'orderlist', 'p': '1', 'pageSize': '5'}, headers=headers)
                hist_json = hist_res_raw.json()
                if 'list' in hist_json and len(hist_json['list']) > 0:
                    for order in hist_json['list']:
                        increment_id = str(order.get('increment_id', ''))
                        
                        if increment_id in seen_order_ids:
                            continue
                            
                        if str(order.get('user_id')) == str(game_id) and str(order.get('server_id')) == str(zone_id):
                            if str(order.get('order_status', '')).lower() == 'success' or str(order.get('status')) == '1':
                                real_order_id = increment_id
                                break
            except Exception: pass

        if is_success:
            if real_order_id in ["Not found", "", "None"]:
                real_order_id = f"AUTO_{int(time.time())}"
            return {"status": "success", "ig_name": ig_name, "order_id": real_order_id}
        else:
            return {"status": "error", "message": "Payment failed."}

    except Exception as e: return {"status": "error", "message": f"System Error: {str(e)}"}

# ==========================================
# 4. 🛡️ FUNCTION TO CHECK AUTHORIZATION
# ==========================================
async def is_authorized(message: Message):
    if message.from_user.id == OWNER_ID:
        return True
    
    users = await get_allowed_users()
    
    # Check by User ID
    if str(message.from_user.id) in users:
        return True
        
    # Check by Username
    if message.from_user.username:
        username_lower = message.from_user.username.lower()
        if username_lower in users:
            return True
            
    return False

# ==========================================
# 5. OWNER COMMANDS (Add, Remove, Users, Cookie)
# ==========================================

@app.on_message((filters.command("add") | filters.regex(r"(?i)^\.add\b")) & filters.private)
async def add_user_cmd(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ You are not the owner.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Usage: `/add <user_id or @username>` or `.add <user_id or @username>`")
    
    target = parts[1].strip()
    if await add_allowed_user(target):
        await message.reply(f"✅ User `{target}` has been allowed to use the shared wallet.")
    else:
        await message.reply(f"⚠️ User `{target}` is already in the allowed list.")

@app.on_message((filters.command("remove") | filters.regex(r"(?i)^\.remove\b")) & filters.private)
async def remove_user_cmd(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ You are not the owner.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("⚠️ Usage: `/remove <user_id or @username>` or `.remove <user_id or @username>`")
    
    target = parts[1].strip()
    if str(target) == str(OWNER_ID):
        return await message.reply("❌ Cannot remove the owner.")
        
    if await remove_allowed_user(target):
        await message.reply(f"✅ User `{target}` has been removed.")
    else:
        await message.reply(f"⚠️ User `{target}` is not in the allowed list.")

@app.on_message((filters.command("users") | filters.regex(r"(?i)^\.users\b")) & filters.private)
async def list_users_cmd(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ You are not the owner.")
    
    users = await get_allowed_users()
    user_list = []
    for u in users:
        role = "👑 Owner" if str(u) == str(OWNER_ID) else "👤 User"
        if str(u).isdigit():
            user_list.append(f"🔹 ID: `{u}` ({role})")
        else:
            user_list.append(f"🔹 Username: `@{u}` ({role})")
            
    final_text = "\n".join(user_list) if user_list else "No users found."
    await message.reply(f"📋 **Allowed Users List:**\n\n{final_text}")


@app.on_message(filters.command("setcookie"))
async def set_cookie_command(client, message: Message):
    if not await is_authorized(message): return await message.reply("❌ Only the Owner can set the Cookie.")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.reply("⚠️ **Usage format:**\n`/setcookie <Long_Main_Cookie>`")
    
    await update_main_cookie(parts[1].strip())
    await message.reply("✅ **Main Cookie has been successfully updated securely.**")

@app.on_message(filters.regex("PHPSESSID") & filters.regex("cf_clearance"))
async def handle_raw_cookie_dump(client, message: Message):
    if message.from_user.id != OWNER_ID: 
        return await message.reply("❌ You are not the owner.")

    text = message.text
    
    try:
        phpsessid_match = re.search(r"['\"]?PHPSESSID['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        cf_clearance_match = re.search(r"['\"]?cf_clearance['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        cf_bm_match = re.search(r"['\"]?__cf_bm['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        did_match = re.search(r"['\"]?_did['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)

        if not phpsessid_match or not cf_clearance_match:
            return await message.reply("PHPSESSID နှင့် cf_clearance ကို ရှာမတွေ့ပါ။ Format မှန်ကန်ကြောင်း စစ်ဆေးပါ။")

        val_php = phpsessid_match.group(1)
        val_cf = cf_clearance_match.group(1)

        formatted_cookie = f"PHPSESSID={val_php}; cf_clearance={val_cf};"
        
        if cf_bm_match:
            formatted_cookie += f" __cf_bm={cf_bm_match.group(1)};"
        if did_match:
            formatted_cookie += f" _did={did_match.group(1)};"

        await update_main_cookie(formatted_cookie)
            
        response_msg = f"✅ **Smart Cookie Parser: Success!**\n\n"
        response_msg += f"🍪 **Saved Cookie:**\n`{formatted_cookie}`"
        await message.reply(response_msg)

    except Exception as e:
        await message.reply(f"❌ Parsing Error: {str(e)}")

@app.on_message(filters.command("balance") | filters.regex(r"(?i)^\.balance\b"))
async def check_balance_command(client, message: Message):
    if not await is_authorized(message): return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")
    
    shared_wallet = await get_shared_wallet()
    report = f"💳 **Sʜᴀʀᴇᴅ Wᴀʟʟᴇᴛ Bᴀʟᴀɴᴄᴇ:**\n\n"
    report += f"🇧🇷 ʙʀ-ʙᴀʟᴀɴᴄᴇ  :  ${shared_wallet.get('br_balance', 0.00):,.2f}\n"
    report += f"🇵🇭 ᴘʜ-ʙᴀʟᴀɴᴄᴇ  :  ${shared_wallet.get('ph_balance', 0.00):,.2f}\n\n"
    
    # Only Owner can see the real physical account balance to avoid confusing normal users
    if message.from_user.id == OWNER_ID:
        loading_msg = await message.reply("Fetching real balance from the official account...")
        scraper = await get_main_scraper()
        headers = {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://www.smile.one'}
        try:
            balances = await get_smile_balance(scraper, headers, 'https://www.smile.one/customer/order')
            report += f"💳 **Oғғɪᴄɪᴀʟ ᴀᴄᴄᴏᴜɴᴛ-ʙᴀʟᴀɴᴄᴇ:**\n\n"
            report += f"🇧🇷 ʙʀ-ʙᴀʟᴀɴᴄᴇ  :  ${balances.get('br_balance', 0.00):,.2f}\n"
            report += f"🇵🇭 ᴘʜ-ʙᴀʟᴀɴᴄᴇ  :  ${balances.get('ph_balance', 0.00):,.2f}"
            await loading_msg.edit(report)
        except Exception as e:
            await loading_msg.edit(report + f"\n❌ Error fetching official balance: {str(e)}")
    else:
        await message.reply(report)


# 📜 HISTORY COMMAND (.his / /history) 

@app.on_message(filters.command("history") | filters.regex(r"(?i)^\.his$"))
async def send_order_history(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    tg_id = str(message.from_user.id)
    user_name = message.from_user.username or message.from_user.first_name
    
    history_data = await get_user_history(tg_id, limit=200)
    
    if not history_data:
        return await message.reply("📜 **No Order History Found.**")

    response_text = f"==== Order History for @{user_name} ====\n\n"
    
    for order in history_data:
        response_text += (
            f"🆔 Game ID: {order['game_id']}\n"
            f"🌏 Zone ID: {order['zone_id']}\n"
            f"💎 Pack: {order['item_name']}\n"
            f"🆔 Order ID: {order['order_id']}\n"
            f"📅 Date: {order['date_str']}\n"
            f"💲 Rate: ${order['price']:,.2f}\n"
            f"📊 Status: {order['status']}\n"
            f"────────────────\n"
        )
    
    file_obj = io.BytesIO(response_text.encode('utf-8'))
    file_obj.name = f"History_{tg_id}.txt"
    
    await message.reply_document(
        document=file_obj,
        caption=f"<emoji id='{EMOJI_3}'>📊</emoji> **Order History**\n<emoji id='{EMOJI_1}'>📊</emoji> User: @{user_name}\n<emoji id='{EMOJI_2}'>📊</emoji> Records: {len(history_data)} (Max: 200)"
    )

# 🧹 CLEAN HISTORY COMMAND (.clean / /clean)

@app.on_message(filters.command("clean") | filters.regex(r"(?i)^\.clean$"))
async def clean_order_history_cmd(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    tg_id = str(message.from_user.id)
    deleted_count = await clear_user_history(tg_id)
    
    if deleted_count > 0:
        await message.reply(f"🗑️ **History Cleaned Successfully.**\nDeleted {deleted_count} order records from your history.")
    else:
        await message.reply("📜 **No Order History Found to Clean.**")


# ==========================================
# 6. 📌 ACTIVATION CODE (.topup AUTO DETECT)
# ==========================================
@app.on_message(filters.regex(r"(?i)^\.topup\s+([a-zA-Z0-9]+)"))
async def handle_topup(client, message: Message):
    if not await is_authorized(message): return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")
    
    match = re.search(r"(?i)^\.topup\s+([a-zA-Z0-9]+)", message.text.strip())
    if not match: return await message.reply("Usage format - `.topup <Code>`")
    
    activation_code = match.group(1).strip()
    
    loading_msg = await message.reply(f"Checking Code `{activation_code}`...")
    
    async with transaction_lock:
        scraper = await get_main_scraper()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        }
        
        async def try_redeem(api_type):
            if api_type == 'PH':
                page_url = 'https://www.smile.one/ph/customer/activationcode'
                check_url = 'https://www.smile.one/ph/smilecard/pay/checkcard'
                pay_url = 'https://www.smile.one/ph/smilecard/pay/payajax'
                base_origin = 'https://www.smile.one'
                base_referer = 'https://www.smile.one/ph/'
                balance_check_url = 'https://www.smile.one/ph/customer/order'
            else:
                page_url = 'https://www.smile.one/customer/activationcode'
                check_url = 'https://www.smile.one/smilecard/pay/checkcard'
                pay_url = 'https://www.smile.one/smilecard/pay/payajax'
                base_origin = 'https://www.smile.one'
                base_referer = 'https://www.smile.one/'
                balance_check_url = 'https://www.smile.one/customer/order'

            req_headers = headers.copy()
            req_headers['Referer'] = base_referer

            try:
                res = await asyncio.to_thread(scraper.get, page_url, headers=req_headers)
                if "login" in res.url.lower(): return "expired", None

                soup = BeautifulSoup(res.text, 'html.parser')
                csrf_token = soup.find('meta', {'name': 'csrf-token'})
                csrf_token = csrf_token.get('content') if csrf_token else (soup.find('input', {'name': '_csrf'}).get('value') if soup.find('input', {'name': '_csrf'}) else None)
                if not csrf_token: return "error", "❌ CSRF Token not obtained."

                ajax_headers = req_headers.copy()
                ajax_headers.update({'X-Requested-With': 'XMLHttpRequest', 'Origin': base_origin, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

                check_res_raw = await asyncio.to_thread(scraper.post, check_url, data={'_csrf': csrf_token, 'pin': activation_code}, headers=ajax_headers)
                check_res = check_res_raw.json()
                code_status = str(check_res.get('code', check_res.get('status', '')))
                
                if code_status in ['200', '201', '0', '1'] or 'success' in str(check_res.get('msg', '')).lower():
                    old_bal = await get_smile_balance(scraper, headers, balance_check_url)
                    pay_res_raw = await asyncio.to_thread(scraper.post, pay_url, data={'_csrf': csrf_token, 'sec': activation_code}, headers=ajax_headers)
                    pay_res = pay_res_raw.json()
                    pay_status = str(pay_res.get('code', pay_res.get('status', '')))
                    
                    if pay_status in ['200', '0', '1'] or 'success' in str(pay_res.get('msg', '')).lower():
                        await asyncio.sleep(5) 
                        new_bal = await get_smile_balance(scraper, headers, balance_check_url)
                        added = round(new_bal['br_balance' if api_type == 'BR' else 'ph_balance'] - old_bal['br_balance' if api_type == 'BR' else 'ph_balance'], 2)
                        return "success", added
                    else:
                        return "fail", "Payment failed."
                else:
                    return "invalid", "Invalid Code"
                    
            except Exception as e:
                return "error", str(e)

        status, result = await try_redeem('BR')
        active_region = 'BR'
        
        if status in ['invalid', 'fail']: 
            status, result = await try_redeem('PH')
            active_region = 'PH'

        if status == "expired":
            await loading_msg.edit("ʏᴏᴜʀ ᴄᴏᴏᴋɪᴇs ɪs ᴇxᴘɪʀᴇᴅ.")
        elif status == "error":
            await loading_msg.edit(f"❌ Error: {result}")
        elif status in ['invalid', 'fail']:
            await loading_msg.edit("Cʜᴇᴄᴋ Fᴀɪʟᴇᴅ❌\n(Code is invalid or might have been used)")
        elif status == "success":
            added_amount = result
            
            if added_amount <= 0:
                await loading_msg.edit(f"sᴍɪʟᴇ ᴏɴᴇ ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ sᴜᴄᴄᴇss ✅\n(Cannot retrieve exact amount due to System Delay.)")
            else:
                fmt_amount = int(added_amount) if added_amount % 1 == 0 else added_amount
                
                # Add to Shared Wallet
                if active_region == 'BR':
                    await update_shared_wallet(br_amount=added_amount)
                else:
                    await update_shared_wallet(ph_amount=added_amount)

                new_wallet = await get_shared_wallet()
                new_bal = new_wallet.get('br_balance' if active_region == 'BR' else 'ph_balance', 0.0)

                msg = (
                    f"✅ <b>Code Top-Up Successful</b>\n\n"
                    f"<code>"
                    f"Code   : {activation_code} ({active_region})\n"
                    f"Added  : +{fmt_amount:,} 🪙\n"
                    f"Total Shared Bal: {new_bal:,.2f} 🪙\n"
                    f"</code>"
                )
                
                await loading_msg.edit(msg, parse_mode=ParseMode.HTML)


# ==========================================
# 7. 📌 COMMAND TO CHECK ROLE
# ==========================================
@app.on_message(filters.regex(r"(?i)^/?role\b"))
async def handle_check_role(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    match = re.search(r"(?i)^/?role\s+(\d+)\s*\(\s*(\d+)\s*\)", message.text.strip())
    if not match:
        return await message.reply("❌ Invalid format:\n(Example - `/role 123456789 (12345)`)")

    game_id = match.group(1).strip()
    zone_id = match.group(2).strip()
    
    loading_msg = await message.reply("💻")

    scraper = await get_main_scraper()
    
    main_url = 'https://www.smile.one/merchant/mobilelegends'
    checkrole_url = 'https://www.smile.one/merchant/mobilelegends/checkrole'
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': main_url, 'Origin': 'https://www.smile.one'}

    try:
        res = await asyncio.to_thread(scraper.get, main_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        csrf_token = None
        meta_tag = soup.find('meta', {'name': 'csrf-token'})
        if meta_tag: csrf_token = meta_tag.get('content')
        else:
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input: csrf_token = csrf_input.get('value')

        if not csrf_token:
            return await loading_msg.edit("❌ CSRF Token not found. Add a new Cookie using /setcookie.")

        check_data = {'user_id': game_id, 'zone_id': zone_id, '_csrf': csrf_token}
        role_response_raw = await asyncio.to_thread(scraper.post, checkrole_url, data=check_data, headers=headers)
        
        try: 
            role_result = role_response_raw.json()
        except: 
            return await loading_msg.edit("❌ Cannot verify. (Smile API Error)")
            
        ig_name = role_result.get('username') or role_result.get('data', {}).get('username')
        
        if not ig_name or str(ig_name).strip() == "":
            real_error = role_result.get('msg') or role_result.get('message') or "Account not found."
            if "login" in str(real_error).lower() or "unauthorized" in str(real_error).lower():
                return await loading_msg.edit("⚠️ Cookie expired. Please add a new one using `/setcookie`.")
            return await loading_msg.edit(f"❌ **Invalid Account:**\n{real_error}")

        smile_region = role_result.get('zone') or role_result.get('region') or role_result.get('data', {}).get('zone') or "Unknown"

        pizzo_region = "Unknown"
        try:
            pizzo_headers = {
                'authority': 'pizzoshop.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://pizzoshop.com',
                'referer': 'https://pizzoshop.com/mlchecker',
                'user-agent': 'Mozilla/5.0'
            }
            await asyncio.to_thread(scraper.get, "https://pizzoshop.com/mlchecker", headers=pizzo_headers, timeout=10)
            pizzo_res_raw = await asyncio.to_thread(scraper.post, "https://pizzoshop.com/mlchecker/check", data={'user_id': game_id, 'zone_id': zone_id}, headers=pizzo_headers, timeout=15)
            pizzo_soup = BeautifulSoup(pizzo_res_raw.text, 'html.parser')
            table = pizzo_soup.find('table', class_='table-modern')
            
            if table:
                for row in table.find_all('tr'):
                    th, td = row.find('th'), row.find('td')
                    if th and td and ('region id' in th.get_text(strip=True).lower() or 'region' in th.get_text(strip=True).lower()):
                        pizzo_region = td.get_text(strip=True)
        except: pass

        final_region = pizzo_region if pizzo_region != "Unknown" else smile_region

        report = f"ɢᴀᴍᴇ ɪᴅ : {game_id} ({zone_id})\nɪɢɴ ɴᴀᴍᴇ : {ig_name}\nʀᴇɢɪᴏɴ : {final_region}"
        await loading_msg.edit(report)

    except Exception as e:
        await loading_msg.edit(f"❌ System Error: {str(e)}")

# ==========================================
# 8. 💎 PURCHASE (SHARED WALLET SYSTEM)
# ==========================================
@app.on_message(filters.regex(r"(?i)^(?:msc|br|ph|mlb|mlp|b|p)\s+\d+"))
async def handle_direct_buy(client, message: Message):
    if not await is_authorized(message):
        return await message.reply(f"ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.❌")

    try:
        tg_id = str(message.from_user.id)
        lines = message.text.strip().split('\n')
        
        telegram_user = message.from_user.username
        username_display = f"@{telegram_user}" if telegram_user else tg_id
        
        async with transaction_lock: 
            for line in lines:
                line = line.strip()
                if not line: continue 
                
                match = re.search(r"(?i)^(?:(?:msc|br|ph|mlb|mlp|b|p)\s+)?(\d+)\s*(?:[\(]?\s*(\d+)\s*[\)]?)\s+([a-zA-Z0-9_]+)", line)
                
                if not match:
                    await message.reply(f"Invalid format: `{line}`\n(Example: msc 12345678 1234 11 OR br 12345678 (1234) wp)")
                    continue
                    
                game_id = match.group(1)
                zone_id = match.group(2)
                item_input = match.group(3).lower() 
                
                currency_name = ''
                active_packages = {}
                v_bal_key = ''

                if item_input in DOUBLE_DIAMOND_PACKAGES:
                    currency_name = 'BR'
                    active_packages = DOUBLE_DIAMOND_PACKAGES
                    v_bal_key = 'br_balance'
                elif item_input in BR_PACKAGES:
                    currency_name = 'BR'
                    active_packages = BR_PACKAGES
                    v_bal_key = 'br_balance'
                elif item_input in PH_PACKAGES:
                    currency_name = 'PH'
                    active_packages = PH_PACKAGES
                    v_bal_key = 'ph_balance'
                else:
                    await message.reply(f"❌ No Package found for the selected '{item_input}'.")
                    continue
                    
                items_to_buy = active_packages[item_input]
                total_required_price = sum(item['price'] for item in items_to_buy)
                
                # Check Shared Wallet Balance First
                shared_wallet = await get_shared_wallet()
                current_bal = shared_wallet.get(v_bal_key, 0.0)
                
                if current_bal < total_required_price:
                    error_text = (
                        f"Nᴏᴛ ᴇɴᴏᴜɢʜ ᴍᴏɴᴇʏ ɪɴ sʜᴀʀᴇᴅ ᴡᴀʟʟᴇᴛ.\n"
                        f"Nᴇᴇᴅ ʙᴀʟᴀɴᴄᴇ ᴀᴍᴏᴜɴᴛ: {total_required_price} {currency_name}\n"
                        f"Cᴜʀʀᴇɴᴛ ʙᴀʟᴀɴᴄᴇ: {current_bal} {currency_name}"
                    )
                    await message.reply(error_text)
                    continue
                
                loading_msg = await message.reply(f"Recharging Diam͟o͟n͟d͟ ● ᥫ᭡")
                
                success_count = 0
                fail_count = 0
                total_spent = 0.0
                order_ids_str = ""
                ig_name = "Unknown"
                error_msg = ""
                first_order = True
                
                seen_order_ids = []
                
                for item in items_to_buy:
                    result = await process_smile_one_order(game_id, zone_id, item['pid'], currency_name, seen_order_ids)
                    
                    if result['status'] == 'success':
                        if first_order:
                            ig_name = result['ig_name']
                            first_order = False
                        
                        success_count += 1
                        total_spent += item['price']
                        
                        order_id = result['order_id']
                        seen_order_ids.append(order_id)
                        order_ids_str += f"{order_id}\n" 
                        
                        await asyncio.sleep(random.randint(2, 5)) 
                    else:
                        fail_count += 1
                        error_msg = result['message']
                        break 
                
                if success_count > 0:
                    now = datetime.datetime.now(MMT)
                    date_str = now.strftime("%m/%d/%Y, %I:%M:%S %p")
                    
                    # Deduct from shared wallet
                    if currency_name == 'BR':
                        await update_shared_wallet(br_amount=-total_spent)
                    else:
                        await update_shared_wallet(ph_amount=-total_spent)
                        
                    new_wallet = await get_shared_wallet()
                    new_bal = new_wallet.get(v_bal_key, 0.0)
                    
                    final_order_ids = order_ids_str.strip().replace('\n', ', ')
                    
                    await save_order(
                        tg_id=tg_id,
                        game_id=game_id,
                        zone_id=zone_id,
                        item_name=item_input,
                        price=total_spent,
                        order_id=final_order_ids,
                        status="success"
                    )
                 
                    safe_ig_name = html.escape(str(ig_name))
                    safe_username = html.escape(str(username_display))
                    
                    
                    report = (
                        f"<blockquote><code>=== ᴛʀᴀɴsᴀᴄᴛɪᴏɴ ʀᴇᴘᴏʀᴛ ===\n\n"
                        f"ᴏʀᴅᴇʀ sᴛᴀᴛᴜs : ✅ Sᴜᴄᴄᴇss\n"
                        f"ɢᴀᴍᴇ ɪᴅ      : {game_id} {zone_id}\n"
                        f"ɪɢ ɴᴀᴍᴇ      : {safe_ig_name}\n"
                        f"sᴇʀɪᴀʟ       :\n{order_ids_str.strip()}\n"
                        f"ɪᴛᴇᴍ         : {item_input} 💎\n"
                        f"sᴘᴇɴᴛ        : {total_spent:.2f} 🪙\n\n"
                        f"ᴅᴀᴛᴇ         : {date_str}\n"
                        f"ᴜsᴇʀɴᴀᴍᴇ     : {safe_username}\n"
                        f"sᴘᴇɴᴛ        : ${total_spent:.2f}\n"
                        f"ɪɴɪᴛɪᴀʟ      : ${current_bal:,.2f}\n"
                        f"ғɪɴᴀʟ        : ${new_bal:,.2f}\n\n"
                        f"Sᴜᴄᴄᴇss {success_count} / Fᴀɪʟ {fail_count}</code></blockquote>"
                    )

                    await loading_msg.edit(report, parse_mode=ParseMode.HTML)
                    
                    if fail_count > 0:
                        await message.reply(f"Only partially successful.\nError: {error_msg}")
                else:
                    await loading_msg.edit(f"❌ Order failed:\n{error_msg}")

    except Exception as e:
        await message.reply(f"System Error: {str(e)}")


# 🌟 NEW: 8.1 MAGIC CHESS (SHARED WALLET ဖြင့် ဝယ်ယူခြင်း) 🌟

@app.on_message(filters.regex(r"(?i)^mcc\s+\d+"))
async def handle_mcc_buy(client, message: Message):
    if not await is_authorized(message):
        return await message.reply(f"ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    try:
        tg_id = str(message.from_user.id)
        lines = message.text.strip().split('\n')
        
        telegram_user = message.from_user.username
        username_display = f"@{telegram_user}" if telegram_user else tg_id
        
        async with transaction_lock:
            for line in lines:
                line = line.strip()
                if not line: continue 
                
                match = re.search(r"(?i)^(?:mcc\s+)?(\d+)\s*(?:[\(]?\s*(\d+)\s*[\)]?)\s+([a-zA-Z0-9_]+)", line)
                
                if not match:
                    await message.reply(f"❌ Invalid format: `{line}`\n(Example: mcc 12345678 1234 86)")
                    continue
                    
                game_id = match.group(1)
                zone_id = match.group(2)
                item_input = match.group(3).lower()
                
                if item_input not in MCC_PACKAGES:
                    await message.reply(f"❌ No Magic Chess Package found for '{item_input}'.")
                    continue
                    
                items_to_buy = MCC_PACKAGES[item_input]
                total_required_price = sum(item['price'] for item in items_to_buy)
                
                shared_wallet = await get_shared_wallet()
                current_bal = shared_wallet.get("br_balance", 0.0)
                
                if current_bal < total_required_price:
                    error_text = (
                        f"Nᴏᴛ ᴇɴᴏᴜɢʜ ᴍᴏɴᴇʏ ɪɴ sʜᴀʀᴇᴅ ᴡᴀʟʟᴇᴛ.\n"
                        f"Nᴇᴇᴅ ʙᴀʟᴀɴᴄᴇ ᴀᴍᴏᴜɴᴛ: {total_required_price} BR\n"
                        f"Cᴜʀʀᴇɴᴛ ʙᴀʟᴀɴᴄᴇ: {current_bal} BR"
                    )
                    await message.reply(error_text)
                    continue
                
                loading_msg = await message.reply(f"💻")
                
                success_count = 0
                fail_count = 0
                total_spent = 0.0
                order_ids_str = ""
                ig_name = "Unknown"
                error_msg = ""
                first_order = True
                
                seen_order_ids = []
                
                for item in items_to_buy:
                    result = await process_mcc_order(game_id, zone_id, item['pid'], seen_order_ids)
                    
                    if result['status'] == 'success':
                        if first_order:
                            ig_name = result['ig_name']
                            first_order = False
                        
                        success_count += 1
                        total_spent += item['price']
                        
                        order_id = result['order_id']
                        seen_order_ids.append(order_id)
                        order_ids_str += f"{order_id}\n"
                        
                        await asyncio.sleep(random.randint(5, 10)) 
                    else:
                        fail_count += 1
                        error_msg = result['message']
                        break 
                
                if success_count > 0:
                    now = datetime.datetime.now(MMT)
                    date_str = now.strftime("%m/%d/%Y, %I:%M:%S %p")
                    
                    # Deduct from shared wallet
                    await update_shared_wallet(br_amount=-total_spent)
                    new_wallet = await get_shared_wallet()
                    new_bal = new_wallet.get("br_balance", 0.0)
                    
                    final_order_ids = order_ids_str.strip().replace('\n', ', ')
                    
                    await save_order(
                        tg_id=tg_id,
                        game_id=game_id,
                        zone_id=zone_id,
                        item_name=item_input,
                        price=total_spent,
                        order_id=final_order_ids,
                        status="success"
                    )
                 
                    safe_ig_name = html.escape(str(ig_name))
                    safe_username = html.escape(str(username_display))

                    report = (
                        f"<blockquote><code>**MCC {game_id} ({zone_id}) {item_input}**\n"
                        f"=== ᴛʀᴀɴsᴀᴄᴛɪᴏɴ ʀᴇᴘᴏʀᴛ ===\n\n"
                        f"ᴏʀᴅᴇʀ sᴛᴀᴛᴜs : ✅ Sᴜᴄᴄᴇss\n"
                        f"ɢᴀᴍᴇ         : ᴍᴀɢɪᴄ ᴄʜᴇss ɢᴏ ɢᴏ\n"
                        f"ɢᴀᴍᴇ ɪᴅ      : {game_id} {zone_id}\n"
                        f"ɪɢ ɴᴀᴍᴇ      : {safe_ig_name}\n"
                        f"ᴏʀᴅᴇʀ ɪᴅ     :\n{order_ids_str.strip()}\n"
                        f"ɪᴛᴇᴍ         : {item_input} 💎\n"
                        f"sᴘᴇɴᴛ        : {total_spent:.2f} 🪙\n\n"
                        f"ᴅᴀᴛᴇ         : {date_str}\n"
                        f"ᴜsᴇʀɴᴀᴍᴇ     : {safe_username}\n"
                        f"sᴘᴇɴᴛ        : ${total_spent:.2f}\n"
                        f"ɪɴɪᴛɪᴀʟ      : ${current_bal:,.2f}\n"
                        f"ғɪɴᴀʟ        : ${new_bal:,.2f}\n\n"
                        f"Sᴜᴄᴄᴇss {success_count} / Fᴀɪʟ {fail_count}</code></blockquote>" 
                    )

                    await loading_msg.edit(report, parse_mode=ParseMode.HTML)
                    
                    if fail_count > 0: 
                        await message.reply(f"⚠️ Only partially successful.\nError: {error_msg}")
                else:
                    await loading_msg.edit(f"Oʀᴅᴇʀ ғᴀɪʟ❌\n{error_msg}")

    except Exception as e:
        await message.reply(f"Sʏsᴛᴇᴍ ᴇʀʀᴏʀ: {str(e)}")


# 11. 📜 BR PRICE LIST COMMAND (.listb / /listb)

@app.on_message(filters.command("listb") | filters.regex(r"(?i)^\.listb$"))
async def show_price_list_br(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    def generate_list(package_dict):
        lines = []
        for key, items in package_dict.items():
            total_price = sum(item['price'] for item in items)
            lines.append(f"{key:<5} : ${total_price:,.2f}")
        return "\n".join(lines)

    br_list = generate_list(BR_PACKAGES)
    bonus_list = generate_list(DOUBLE_DIAMOND_PACKAGES)

    response_text = (
        f"🇧🇷 <b>𝘿𝙤𝙪𝙗𝙡𝙚 𝙋𝙖𝙘𝙠𝙖𝙜𝙚𝙨</b>\n"
        f"<code>{bonus_list}</code>\n\n"
        f"🇧🇷 <b>𝘽𝙧 𝙋𝙖𝙘𝙠𝙖𝙜𝙚𝙨</b>\n"
        f"<code>{br_list}</code>"
    )

    await message.reply(response_text, parse_mode=ParseMode.HTML)


# 11.1 📜 PH PRICE LIST COMMAND (.listp / /listp)

@app.on_message(filters.command("listp") | filters.regex(r"(?i)^\.listp$"))
async def show_price_list_ph(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    def generate_list(package_dict):
        lines = []
        for key, items in package_dict.items():
            total_price = sum(item['price'] for item in items)
            lines.append(f"{key:<5} : ${total_price:,.2f}")
        return "\n".join(lines)

    ph_list = generate_list(PH_PACKAGES)

    response_text = (
        f"🇵🇭 <b>𝙋𝙝 𝙋𝙖𝙘𝙠𝙖𝙜𝙚𝙨</b>\n"
        f"<code>{ph_list}</code>"
    )

    await message.reply(response_text, parse_mode=ParseMode.HTML)


# 11.2 BR MCC PRICE LIST COMMAND (.listmb / /listmb)

@app.on_message(filters.command("listmb") | filters.regex(r"(?i)^\.listmb$"))
async def show_price_list_mcc(client, message: Message):
    if not await is_authorized(message):
        return await message.reply("ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ.")

    def generate_list(package_dict):
        lines = []
        for key, items in package_dict.items():
            total_price = sum(item['price'] for item in items)
            lines.append(f"{key:<5} : ${total_price:,.2f}")
        return "\n".join(lines)

    mcc_list = generate_list(MCC_PACKAGES)

    response_text = (
        f"🇧🇷 <b>𝙈𝘾𝘾 𝙋𝘼𝘾𝙆𝘼𝙂𝙀𝙎</b>\n"
        f"<code>{mcc_list}</code>"
    )

    await message.reply(response_text, parse_mode=ParseMode.HTML)


# 🧮 SMART CALCULATOR FUNCTION

@app.on_message(filters.text & filters.regex(r"^[\d\s\.\(\)]+[\+\-\*\/][\d\s\+\-\*\/\(\)\.]+$"))
async def auto_calculator(client, message: Message):
    try:
        expr = message.text.strip()
        
        if re.match(r"^09[-\s]?\d+", expr):
            return
            
        clean_expr = expr.replace(" ", "")
        
        result = eval(clean_expr, {"__builtins__": None})
        
        if isinstance(result, float):
            formatted_result = f"{result:.4f}".rstrip('0').rstrip('.')
        else:
            formatted_result = str(result)
            
        response = f"{expr} = {formatted_result}"
        
        await message.reply_text(response, quote=False)
        
    except Exception:
        pass


# 10. 💓 HEARTBEAT FUNCTION

async def keep_cookie_alive():
    while True:
        try:
            await asyncio.sleep(2 * 60) 
            scraper = await get_main_scraper()
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://www.smile.one'
            }
            response = await asyncio.to_thread(scraper.get, 'https://www.smile.one/customer/order', headers=headers)
            if "login" not in response.url.lower() and response.status_code == 200:
                print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}] 💓 Main Cookie is alive!")
            else:
                print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}]  Main Cookie expired. Auto-login triggered.")
                await auto_login_and_get_cookie()
        except Exception as e:
            pass


# ℹ️ HELP COMMAND (.help / /help)

@app.on_message(filters.command("help") | filters.regex(r"(?i)^\.help$"))
async def send_help_message(client, message: Message):
    is_owner = (message.from_user.id == OWNER_ID)

    help_text = (
        f"<b>🤖 𝐁𝐎𝐓 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒 𝐌𝐄𝐍𝐔</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
    )

    help_text += (
        f"<b>💎 𝐌𝐋𝐁Ｂ 𝐃𝐢𝐚𝐦𝐨𝐧𝐝𝐬</b>\n"
        f"<blockquote><code>msc ID (Zone) Pack</code></blockquote>\n"
        f"Ex: <code>msc 12345678 12345 172</code>\n"
        f"<i>(command : msc, br, ph, mlb, mlp)</i>\n\n"

        f"<b>♟️ 𝐌𝐚𝐠𝐢𝐜 𝐂𝐡𝐞𝐬𝐬</b>\n"
        f"<blockquote><code>mcc ID (Zone) Pack</code></blockquote>\n"
        f"Ex: <code>mcc 12345678 1234 86</code>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
    )

    help_text += (
        f"<b>👤 𝐔𝐬𝐞𝐫 𝐓𝐨𝐨𝐥𝐬</b>\n"
        f"🔹 <code>.balance</code>  : Check Shared Wallet Balance\n"
        f"🔹 <code>.his</code>      : View Order History\n"
        f"🔹 <code>.listb</code>     : View Price List\n"
        f"🔹 <code>.listp</code>     : View Price List\n"
        f"🔹 <code>.listmb</code>     : View Price List\n"
        f"🔹 <code>.role ID (Zone)</code> : Check IGN\n"
        f"🔹 <code>.topup Code</code> : Redeem Voucher (Adds to Shared)\n\n"
    )

    if is_owner:
        help_text += (
            f"<b>👑 𝐎𝐰𝐧𝐞𝐫 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            f"🔸 <code>.add ID/Username</code>    : Add User\n"
            f"🔸 <code>.remove ID/Username</code> : Remove User\n"
            f"🔸 <code>.users</code>              : User List\n"
            f"🔸 <code>/setcookie</code>         : Update Cookie\n"
        )
        
    help_text += f"━━━━━━━━━━━━━━━━"

    await message.reply(help_text, parse_mode=ParseMode.HTML)


# 9. START BOT / DEFAULT COMMAND (FIXED)

@app.on_message(filters.command("start"))
async def send_welcome(client, message: Message):
    try:
        tg_id = str(message.from_user.id)
        
        first_name = message.from_user.first_name or ""
        last_name = message.from_user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = "User"
            
        safe_full_name = full_name.replace('<', '').replace('>', '')
        username_display = f'<a href="tg://user?id={tg_id}">{safe_full_name}</a>'
        
        EMOJI_1 = "5956355397366320202" # 🥺
        EMOJI_2 = "5954097490109140119" # 👤
        EMOJI_3 = "5958289678837746828" # 🆔
        EMOJI_4 = "5956330306167376831" # 📊
        EMOJI_5 = "5954078884310814346" # 📞

        if await is_authorized(message):
            status = "🟢 Aᴄᴛɪᴠᴇ" if message.from_user.id != OWNER_ID else "🟢 Aᴄᴛɪᴠᴇ (OWNER)"
        else:
            status = "🔴 Nᴏᴛ Aᴄᴛɪᴠᴇ"
            
        welcome_text = (
            f"ʜᴇʏ ʙᴀʙʏ <emoji id='{EMOJI_1}'>🥺</emoji>\n\n"
            f"<emoji id='{EMOJI_2}'>👤</emoji> Usᴇʀɴᴀᴍᴇ: {username_display}\n"
            f"<emoji id='{EMOJI_3}'>🆔</emoji> 𝐈𝐃: <code>{tg_id}</code>\n"
            f"<emoji id='{EMOJI_4}'>📊</emoji> Sᴛᴀᴛᴜs: {status}\n\n"
            f"<emoji id='{EMOJI_5}'>📞</emoji> Cᴏɴᴛᴀᴄᴛ ᴜs: @iwillgoforwardsalone"
        )
        
        await message.reply(welcome_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        print(f"Start Cmd Error: {e}")
        
        fallback_text = (
            f"ʜᴇʏ ʙᴀʙʏ 🥺\n\n"
            f"👤 Usᴇʀɴᴀᴍᴇ: {full_name}\n"
            f"🆔 𝐈𝐃: <code>{tg_id}</code>\n"
            f"📊 Sᴛᴀᴛᴜs: {status}\n\n"
            f"📞 Cᴏɴᴛᴀᴄᴛ ᴜs: @iwillgoforwardsalone"
        )
        await message.reply(fallback_text, parse_mode=ParseMode.HTML)



# 10. RUN BOT

if __name__ == '__main__':
    print("Starting Heartbeat & Auto-login thread...")
    print("နှလုံးသားမပါရင် ဘယ်အရာမှတရားမဝင်.....")
    
    loop = asyncio.get_event_loop()
    loop.create_task(keep_cookie_alive())

    print("Bot is successfully running (With Shared Wallet & UI Match)...")
    app.run()
