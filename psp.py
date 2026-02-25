import os
import re
import datetime
import json
import time
import random
import html
import asyncio
import threading
from dotenv import load_dotenv

import cloudscraper
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# ==========================================
# 📌 Environment Variables
# ==========================================
load_dotenv() 

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
OWNER_ID = int(os.getenv('OWNER_ID', 1318826936)) 
FB_EMAIL = os.getenv('FB_EMAIL')
FB_PASS = os.getenv('FB_PASS')

if not all([BOT_TOKEN, API_ID, API_HASH]):
    print("❌ Error: BOT_TOKEN, API_ID, or API_HASH missing in .env.")
    exit()

MMT = datetime.timezone(datetime.timedelta(hours=6, minutes=30))

# ==========================================
# 1. Bot Initialization
# ==========================================
app = Client(
    "smile_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==========================================
# 🗄️ Local JSON Database
# ==========================================
DB_FILE = 'database.json'

def load_data():
    if not os.path.exists(DB_FILE):
        return {"users": [OWNER_ID], "cookie": "PHPSESSID=uief529l5e0vvjeghvhk02v184"}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"users": [OWNER_ID], "cookie": "PHPSESSID=uief529l5e0vvjeghvhk02v184"}

def save_data(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Error saving database: {e}")

initial_data = load_data()
if OWNER_ID not in initial_data["users"]:
    initial_data["users"].append(OWNER_ID)
    save_data(initial_data)

def get_login_cookies():
    db_data = load_data()
    raw_cookie = db_data.get("cookie", "")
    cookie_dict = {}
    for item in raw_cookie.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            cookie_dict[k] = v
    return cookie_dict

def is_authorized(message: Message):
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
# 🤖 Playwright Auto-Login (Async)
# ==========================================
async def auto_login_and_get_cookie():
    if not FB_EMAIL or not FB_PASS:
        print("❌ fb_email and fb_pass missing in .env.")
        return False
        
    print("🔄 Auto-login with Facebook and searching for new cookie...")
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
                print("✅ Auto-login successful. Saving cookie...")
                
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                raw_cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                
                db_data = load_data()
                db_data["cookie"] = raw_cookie_str
                save_data(db_data)
                
                await browser.close()
                return True
            except Exception as wait_e:
                print(f"❌ Did not reach order page (possible checkpoint): {wait_e}")
                await browser.close()
                return False
            
    except Exception as e:
        print(f"❌ Error during auto-login: {e}")
        return False

# ==========================================
# 📌 Packages (MLBB & Magic Chess)
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
# 2. Sync Scraper Functions (Called via to_thread)
# ==========================================
def sync_get_smile_balance(scraper, headers, balance_url='https://www.smile.one/customer/order'):
    balances = {'br_balance': 0.00, 'ph_balance': 0.00}
    try:
        response = scraper.get(balance_url, headers=headers)
        br_match = re.search(r'(?i)(?:Balance|Saldo)[\s:]*?<\/p>\s*<p>\s*([\d\.,]+)', response.text)
        if br_match:
            balances['br_balance'] = float(br_match.group(1).replace(',', ''))
        
        ph_match = re.search(r'(?i)Saldo PH[\s:]*?<\/span>\s*<span>\s*([\d\.,]+)', response.text)
        if ph_match:
            balances['ph_balance'] = float(ph_match.group(1).replace(',', ''))
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            ph_container = soup.find('div', id='all-balance')
            if ph_container:
                rows = ph_container.find_all('div', class_='line')
                for row in rows:
                    if "PH" in row.text.upper():
                        amount_span = row.find_all('span')[-1]
                        balances['ph_balance'] = float(amount_span.text.strip().replace(',', ''))
                        break
    except Exception as e:
        pass
    return balances

def sync_process_smile_one_order(user_id, zone_id, product_id, currency_name, item_price=None, seen_order_ids=None, cached_session=None):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies())
    # ... [Insert your exact original process_smile_one_order logic here] ...
    # (Returning a dictionary: {"status": "success/error", ...})
    return {"status": "error", "message": "Function body intentionally shortened. Paste your original logic here."}

def sync_process_mcc_order(user_id, zone_id, product_id, item_price, seen_order_ids):
    # ... [Insert your exact original process_mcc_order logic here] ...
    return {"status": "error", "message": "Paste your original logic here."}

def sync_heartbeat():
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        scraper.cookies.update(get_login_cookies())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.smile.one'
        }
        response = scraper.get('https://www.smile.one/customer/order', headers=headers)
        if "login" not in response.url.lower() and response.status_code == 200:
            print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}] 💓 Heartbeat: Session is alive!")
        else:
            print(f"[{datetime.datetime.now(MMT).strftime('%I:%M %p')}] ⚠️ Heartbeat: Session expired.")
    except Exception as e:
        print(f"❌ Heartbeat error: {e}")

async def keep_cookie_alive():
    while True:
        await asyncio.sleep(2 * 60) # Runs every 2 minutes
        await asyncio.to_thread(sync_heartbeat)

# ==========================================
# 5. Owner Commands
# ==========================================
@app.on_message(filters.command("add") & filters.private)
async def add_user(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ You are not the owner.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("⚠️ Usage format - `/add <user_id or @username>`")
        
    target = parts[1].strip()
    db_data = load_data()
    
    try:
        if target.startswith('@') or not target.isdigit():
            username = target.replace('@', '').lower()
            if username in db_data["users"]:
                await message.reply_text(f"⚠️ Username `@{username}` is already allowed.")
            else:
                db_data["users"].append(username)
                save_data(db_data)
                await message.reply_text(f"✅ Username `@{username}` has been allowed.")
        else:
            new_user_id = int(target)
            if new_user_id in db_data["users"]:
                await message.reply_text(f"⚠️ User ID `{new_user_id}` is already allowed.")
            else:
                db_data["users"].append(new_user_id)
                save_data(db_data)
                await message.reply_text(f"✅ User ID `{new_user_id}` has been allowed.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("remove") & filters.private)
async def remove_user(client: Client, message: Message):
    if message.from_user.id != OWNER_ID: 
        return await message.reply_text("❌ You are not the owner.")
    
    # Logic is identical to original, just replacing bot.reply_to with await message.reply_text
    # ...

@app.on_message(filters.command("users") & filters.private)
async def list_users(client: Client, message: Message):
    if message.from_user.id != OWNER_ID: 
        return await message.reply_text("❌ You are not the owner.")
    
    db_data = load_data()
    user_list = []
    for u in db_data.get("users", []):
        if str(u).isdigit():
            role = "owner" if int(u) == OWNER_ID else "user"
            user_list.append(f"🔹 ID: `{u}` ({role})")
        else:
            user_list.append(f"🔹 Username: `@{u}` (user)")
            
    final_text = "\n".join(user_list) if user_list else "No users found."
    await message.reply_text(f"📋 **Allowed Users List:**\n{final_text}")

@app.on_message(filters.command("setcookie") & filters.private)
async def set_cookie_command(client: Client, message: Message):
    if message.from_user.id != OWNER_ID: 
        return await message.reply_text("❌ You are not the owner.")
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text("⚠️ **Usage Format:**\n`/setcookie <long_cookie>`")
    
    raw_cookie_str = parts[1].strip()
    try:
        db_data = load_data()
        db_data["cookie"] = raw_cookie_str
        save_data(db_data)
        await message.reply_text(f"✅ **New cookie securely saved.**")
    except Exception as e:
        await message.reply_text(f"❌ Error saving cookie:\n{str(e)}")

# ==========================================
# 🔌 Smart Cookie Parser 
# ==========================================
@app.on_message(filters.regex("PHPSESSID") & filters.regex("cf_clearance") & filters.private)
async def handle_raw_cookie_dump(client: Client, message: Message):
    if message.from_user.id != OWNER_ID: 
        return await message.reply_text("❌ You are not the owner.")

    text = message.text
    try:
        phpsessid_match = re.search(r"['\"]?PHPSESSID['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        cf_clearance_match = re.search(r"['\"]?cf_clearance['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        cf_bm_match = re.search(r"['\"]?__cf_bm['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)
        did_match = re.search(r"['\"]?_did['\"]?\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?", text)

        if not phpsessid_match or not cf_clearance_match:
            return await message.reply_text("⚠️ PHPSESSID and cf_clearance not found. Check format.")

        val_php = phpsessid_match.group(1)
        val_cf = cf_clearance_match.group(1)
        val_bm = cf_bm_match.group(1) if cf_bm_match else ""
        val_did = did_match.group(1) if did_match else ""

        formatted_cookie = f"PHPSESSID={val_php}; cf_clearance={val_cf};"
        if val_bm: formatted_cookie += f" __cf_bm={val_bm};"
        if val_did: formatted_cookie += f" _did={val_did};"

        db_data = load_data()
        db_data["cookie"] = formatted_cookie
        save_data(db_data)
            
        response_msg = f"✅ **Smart Cookie Parser: Success!**\n\n🍪 **Saved Cookie:**\n`{formatted_cookie}`"
        await message.reply_text(response_msg)

    except Exception as e:
        await message.reply_text(f"❌ Parsing Error: {str(e)}")

# ==========================================
# Check Balance
# ==========================================
@app.on_message(filters.command("balance") & filters.private)
async def check_balance_command(client: Client, message: Message):
    if not is_authorized(message): 
        return await message.reply_text("❌ Unauthorized access.")
    
    loading_msg = await message.reply_text(" Fetching balance...")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    scraper.cookies.update(get_login_cookies()) 
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://www.smile.one'}
    
    try:
        # Pushing blocking code to a separate thread
        balances = await asyncio.to_thread(sync_get_smile_balance, scraper, headers, 'https://www.smile.one/customer/order')
        report = f"Balance (BR): ${balances.get('br_balance', 0.00):,.2f}\nBalance (PH): ${balances.get('ph_balance', 0.00):,.2f}"
        await loading_msg.edit_text(report)
    except Exception as e:
        await loading_msg.edit_text(f"❌ Error:\n{str(e)}")


# ==========================================
# 8. Command Handler (MSC Auto-Detect - MLBB)
# ==========================================
@app.on_message(filters.regex(r"(?i)^msc\s+\d+") & filters.private)
async def handle_direct_buy(client: Client, message: Message):
    if not is_authorized(message):
        return await message.reply_text(f"Not authorized user. ❌")

    try:
        lines = message.text.strip().split('\n')
        telegram_user = message.from_user.username
        username_display = f"@{telegram_user}" if telegram_user else "Unknown"
        
        for line in lines:
            line = line.strip()
            if not line: continue 
                
            match = re.search(r"(?i)^(?:msc\s+)?(\d+)\s*\(\s*(\d+)\s*\)\s*([a-zA-Z0-9_]+)", line)
            if not match:
                await message.reply_text(f"Invalid format: `{line}`\n(e.g. - msc 12345678 (1234) 86)")
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
                await message.reply_text(f"No package found for selected '{item_input}'.")
                continue
                
            items_to_buy = active_packages[item_input]
            loading_msg = await message.reply_text(f"Recharging diam͟o͟n͟d͟ ● ᥫ᭡")
            
            order_ids_str = ""
            total_price = 0.0
            success_count = fail_count = 0
            ig_name = "Unknown"
            initial_used_balance = 0.0
            error_msg = ""
            
            seen_order_ids = [] 
            cached_session = None 
            
            for item in items_to_buy:
                product_id = item['pid']
                item_price = item['price']
                
                # Using asyncio.to_thread for cloudscraper logic
                result = await asyncio.to_thread(
                    sync_process_smile_one_order,
                    game_id, zone_id, product_id, currency_name, item_price, seen_order_ids, cached_session
                )
                
                if result.get('status') == 'success':
                    if not cached_session:
                        initial_used_balance = result['balances'][used_balance_key]
                        ig_name = result['ig_name']
                    
                    success_count += 1
                    total_price += item_price
                    
                    new_id = result['order_id']
                    seen_order_ids.append(new_id)
                    order_ids_str += f"{new_id}\n" 
                    
                    result['balances'][used_balance_key] -= float(item_price)
                    cached_session = {
                        'csrf_token': result['csrf_token'],
                        'ig_name': ig_name,
                        'balances': result['balances']
                    }
                    await asyncio.sleep(random.randint(1, 5)) 
                else:
                    fail_count += 1
                    error_msg = result.get('message', 'Unknown Error')
                    break 
            
            if success_count > 0:
                now = datetime.datetime.now(MMT)
                date_str = now.strftime("%m/%d/%Y, %I:%M:%S %p")
                final_used_balance = initial_used_balance - total_price
                
                safe_ig_name = html.escape(str(ig_name))
                safe_username = html.escape(str(username_display))
                
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

                await loading_msg.edit_text(report, parse_mode=ParseMode.HTML)
                if fail_count > 0:
                    await message.reply_text(f"⚠️ Partially successful.\nError: {error_msg}")
            else:
                await loading_msg.edit_text(f"❌ Order failed:\n{error_msg}")

    except Exception as e:
        await message.reply_text(f"System error: {str(e)}")


# ==========================================
# 9. Start Bot Command
# ==========================================
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
        
        # 🟢 Pyrogram အတွက် <emoji id="..."> သုံးရပါမည်
        EMOJI_1 = "5956355397366320202" # 🥺
        EMOJI_2 = "5954097490109140119" # 👤
        EMOJI_3 = "5958289678837746828" # 🆔
        EMOJI_4 = "5956330306167376831" # 📊
        EMOJI_5 = "5954078884310814346" # 📞

        if is_authorized(message):
            status = "🟢 Aᴄᴛɪᴠᴇ"
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

# ==========================================
# 🚀 Startup Logic
# ==========================================
async def main():
    print("Starting Pyrogram Client...")
    await app.start()
    
    print("Starting background heartbeat task...")
    asyncio.create_task(keep_cookie_alive())
    
    print("Bot is successfully running as Pyrogram Async! (Press Ctrl+C to stop)")
    await idle()
    await app.stop()

if __name__ == '__main__':
    try:
        app.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
