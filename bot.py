import time
import os
from threading import Thread
from datetime import datetime, timezone, timedelta
import urllib.parse
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from flask import Flask
from pymongo import MongoClient

# التوكين ويوزر القناة الخاصين بك
API_TOKEN = '8949480557:AAGcv4NC8wrcXd2ls1PPRtersqAIa7RGQJg'
CHANNEL_ID = '@Client128945'

# إعدادات الاتصال بـ MongoDB
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    MONGO_URI = "mongodb+srv://peter128945:peter128945@telegrambot.nvnzi6z.mongodb.net/?appName=TelegramBot"

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_bot_dev"]
accounts_col = db["accounts"]
settings_col = db["settings"]

bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

active_admin_panels = {}

# دوال التعامل مع MongoDB
def get_last_posted_message_id():
    doc = settings_col.find_one({"key": "last_posted_message_id"})
    return doc["value"] if doc else None

def set_last_posted_message_id(msg_id):
    settings_col.update_one(
        {"key": "last_posted_message_id"},
        {"$set": {"value": msg_id}},
        upsert=True
    )

def load_accounts():
    return list(accounts_col.find({}, {"_id": 0}).sort("id", 1))

def save_account(acc):
    accounts_col.update_one({"id": acc["id"]}, {"$set": acc}, upsert=True)

def delete_account_from_db(acc_id):
    accounts_col.delete_one({"id": acc_id})

# تهيئة الحسابات الأولية إذا كانت قاعدة البيانات فارغة
if accounts_col.count_documents({}) == 0:
    initial_accounts = [
        {
            "id": 0,
            "name": "Account 1",
            "reserved": False,
            "time_from": "",
            "time_to": "",
            "post_url": "https://t.me/Rarezone1/1",
            "client_username": "",
            "warned_near_expiry": False,
            "is_vip": False
        },
        {
            "id": 1,
            "name": "Account 2",
            "reserved": False,
            "time_from": "",
            "time_to": "",
            "post_url": "https://t.me/Rarezone1/2",
            "client_username": "",
            "warned_near_expiry": False,
            "is_vip": False
        }
    ]
    accounts_col.insert_many(initial_accounts)

def parse_time_to_minutes(time_str):
    try:
        time_str = time_str.strip()
        is_pm = any(word in time_str for word in ["pm", "PM"])
        is_am = any(word in time_str for word in ["am", "AM"])
        
        clean_time = time_str
        for word in ["pm", "am", "PM", "AM"]:
            clean_time = clean_time.replace(word, "")
        clean_time = clean_time.strip()

        parts = clean_time.split(":")
        
        if len(parts) == 2:
            hours = int(parts[0])
            minutes = int(parts[1])
        elif len(parts) == 1 and parts[0].isdigit():
            hours = int(parts[0])
            minutes = 0
        else:
            return None
            
        if is_pm and hours < 12: hours += 12
        elif is_am and hours == 12: hours = 0
        return hours * 60 + minutes
    except Exception:
        pass
    return None

def format_minutes_to_time_str(minutes):
    hours = minutes // 60
    mins = minutes % 60
    am_pm = "PM" if hours >= 12 else "AM"
    display_hour = hours % 12
    if display_hour == 0: display_hour = 12
    return f"{display_hour}:{mins:02d} {am_pm}"

def compress_time(t_str):
    if not t_str: return ""
    t = t_str.replace(" AM", "AM").replace(" PM", "PM")
    t = t.replace(":00", "") 
    t = t.replace(":", ".")  
    t = t.replace(" ", "")   
    return t

def channel_booking_markup():
    markup = InlineKeyboardMarkup()
    accounts = load_accounts()
    total_accounts = len(accounts)
    available_accounts = sum(1 for acc in accounts if not acc["reserved"])
    
    # واجهة العميل (إنجليزي)
    header_title = f"💼 Accounts Status ({available_accounts} of {total_accounts} Available) 💼"
    markup.add(InlineKeyboardButton(header_title, callback_data="ignore"))
    
    markup.row(
        InlineKeyboardButton("Activity & Booking 🛒", callback_data="ignore"),
        InlineKeyboardButton("Account 💳", callback_data="ignore")
    )
    
    for a in accounts:
        is_account_vip = a.get("is_vip", False)
        
        display_name = "💎 VIP Account" if is_account_vip else a['name']
        booking_intent = f"I want to book the VIP account 💎 ({a['name']}) for the evening" if is_account_vip else f"I want to book or inquire about {a['name']}"
        
        encoded_msg = urllib.parse.quote(booking_intent)
        booking_link = f"https://t.me/RareZone11?text={encoded_msg}"
        post_link = a['post_url'] if a.get('post_url') and str(a['post_url']).startswith("http") else booking_link
        
        if a["reserved"]:
            t_from = compress_time(a['time_from'])
            t_to = compress_time(a['time_to'])
            
            if t_from and t_to:
                status_text = f"❌ {t_from}-{t_to}"
            elif t_to:
                status_text = f"❌ Until {t_to}"
            else:
                status_text = "❌ Busy"
        else:
            status_text = "Available ✅" if is_account_vip else "Available ✅"
        
        markup.row(
            InlineKeyboardButton(status_text, url=booking_link),
            InlineKeyboardButton(display_name, url=post_link)
        )
        
    return markup

def main_menu_markup(chat_id):
    markup = InlineKeyboardMarkup()
    # واجهة الأدمن (عربي)
    for acc in load_accounts():
        if acc["reserved"]:
            status_str = f"من {acc['time_from']} إلى {acc['time_to']}" if acc['time_from'] else f"حتى {acc['time_to']}"
            client_tag = f" | @{acc['client_username']}" if acc.get("client_username") else ""
            status_icon = f"❌ {status_str}{client_tag}"
        else:
            status_icon = "متاح ✅"
            
        vip_star = "💎 " if acc.get("is_vip") else ""
        markup.add(InlineKeyboardButton(f"{vip_star}{acc['name']} {status_icon}", callback_data=f"toggle_{acc['id']}"))
        
        vip_action_text = "إلغاء VIP ✖️" if acc.get("is_vip") else "VIP 💎"
        markup.row(
            InlineKeyboardButton(f"🔗 تعديل رابط {acc['name']}", callback_data=f"seturl_{acc['id']}"),
            InlineKeyboardButton(vip_action_text, callback_data=f"togglevip_{acc['id']}"),
            InlineKeyboardButton(f"🗑️ حذف", callback_data=f"delete_{acc['id']}")
        )
        
    markup.add(InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add_account"))
    markup.add(InlineKeyboardButton("📢 نشر / تحديث الجدول في القناة", callback_data="post_now"))
    return markup


def update_all_active_admin_panels():
    egypt_time = datetime.now(timezone.utc) + timedelta(hours=3)
    time_fmt = egypt_time.strftime("%I:%M:%S").lstrip("0")
    am_pm = "PM" if egypt_time.hour >= 12 else "AM"
    current_time_str = f"{time_fmt} {am_pm}"

    for chat_id, msg_id in list(active_admin_panels.items()):
        try:
            bot.edit_message_text(
                f"<b>لوحة تحكم الحسابات ⚙️</b>\nتحديث تلقائي ⏱ ({current_time_str})",
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="HTML",
                reply_markup=main_menu_markup(chat_id)
            )
        except Exception:
            pass

def auto_update_channel_message():
    last_posted_id = get_last_posted_message_id()
    if last_posted_id is None:
        return
    try:
        banner_image_url = "https://kommodo.ai/i/sakX2px5W1I2zT1ryoeb"
        media = InputMediaPhoto(banner_image_url, parse_mode="HTML")
        bot.edit_message_media(
            media=media,
            chat_id=CHANNEL_ID,
            message_id=last_posted_id,
            reply_markup=channel_booking_markup()
        )
    except Exception:
        pass

def check_expiration_loop():
    while True:
        try:
            egypt_time = datetime.now(timezone.utc) + timedelta(hours=3)
            now_minutes = parse_time_to_minutes(egypt_time.strftime("%H:%M"))
            updated = False
            
            accounts_data = load_accounts()
            for acc in accounts_data:
                if acc["reserved"] and acc["time_to"]:
                    target_minutes = parse_time_to_minutes(acc["time_to"])
                    if target_minutes is not None and now_minutes is not None:
                        time_diff = target_minutes - now_minutes
                        
                        if 0 < time_diff <= 5 and not acc.get("warned_near_expiry", False):
                            acc["warned_near_expiry"] = True
                            save_account(acc)
                            
                            # تنبيه للأدمن (عربي)
                            alert_msg = f"⚠️ <b>تنبيه:</b> حجز <b>{acc['name']}</b> سينتهي خلال 5 دقائق!"
                            
                            alert_markup = None
                            if acc.get("client_username"):
                                alert_markup = InlineKeyboardMarkup()
                                # رسالة التنبيه التي تذهب للعميل (إنجليزي)
                                ready_msg = f"Hello, alert regarding your booking for ({acc['name']}): time will end in 5 minutes ⏳. Would you like to renew?"
                                encoded_ready_msg = urllib.parse.quote(ready_msg)
                                client_url = f"https://t.me/{acc['client_username']}?text={encoded_ready_msg}"
                                alert_markup.add(InlineKeyboardButton(f"💬 مراسلة العميل (@{acc['client_username']})", url=client_url))
                            
                            for chat_id in list(active_admin_panels.keys()):
                                try: bot.send_message(chat_id, alert_msg, parse_mode="HTML", reply_markup=alert_markup)
                                except: pass

                        if now_minutes >= target_minutes:
                            acc["reserved"] = False
                            acc["time_from"] = ""
                            acc["time_to"] = ""
                            acc["client_username"] = ""
                            acc["warned_near_expiry"] = False
                            save_account(acc)
                            updated = True
            
            if updated:
                auto_update_channel_message()
                update_all_active_admin_panels()
                
        except Exception as e:
            print(f"Error in background time checker: {e}")
            
        time.sleep(15)

def post_table_to_channel(admin_chat_id):
    last_posted_id = get_last_posted_message_id()
    accounts = load_accounts()
    if not accounts:
        bot.send_message(admin_chat_id, "لا توجد حسابات للنشر.")
        return

    try:
        banner_image_url = "https://kommodo.ai/i/sakX2px5W1I2zT1ryoeb"
        
        if last_posted_id is None:
            sent_msg = bot.send_photo(
                CHANNEL_ID, 
                banner_image_url,
                parse_mode="HTML",
                reply_markup=channel_booking_markup()
            )
            set_last_posted_message_id(sent_msg.message_id)
            bot.pin_chat_message(CHANNEL_ID, sent_msg.message_id)
            bot.send_message(admin_chat_id, "تم النشر والتثبيت في القناة بنجاح ✅", reply_markup=main_menu_markup(admin_chat_id))
        else:
            try:
                media = InputMediaPhoto(banner_image_url, parse_mode="HTML")
                bot.edit_message_media(
                    media=media,
                    chat_id=CHANNEL_ID,
                    message_id=last_posted_id,
                    reply_markup=channel_booking_markup()
                )
                bot.send_message(admin_chat_id, "تم تحديث المنشور في القناة بنجاح 🔄", reply_markup=main_menu_markup(admin_chat_id))
            except Exception as edit_err:
                err_str = str(edit_err).lower()
                if "message is not modified" in err_str:
                    bot.send_message(admin_chat_id, "الجدول في القناة محدث بالفعل 🔄", reply_markup=main_menu_markup(admin_chat_id))
                elif "message_id_invalid" in err_str or "message to edit not found" in err_str or "message can't be edited" in err_str:
                    sent_msg = bot.send_photo(
                        CHANNEL_ID, 
                        banner_image_url, 
                        parse_mode="HTML",
                        reply_markup=channel_booking_markup()
                    )
                    set_last_posted_message_id(sent_msg.message_id)
                    try:
                        bot.pin_chat_message(CHANNEL_ID, sent_msg.message_id)
                    except:
                        pass
                    bot.send_message(admin_chat_id, "تم إرسال الجدول الجديد وتثبيته بنجاح ✅", reply_markup=main_menu_markup(admin_chat_id))
                else:
                    raise edit_err

    except Exception as e:
        bot.send_message(admin_chat_id, f"فشل التحديث:\n{e}")

@bot.message_handler(commands=['start', 'admin', 'control'])
def send_welcome(message):
    sent_msg = bot.send_message(
        message.chat.id, 
        "<b>مرحباً بك في لوحة تحكم الحسابات ⚙️</b>\nاضغط على أي حساب لتغيير حالته:", 
        parse_mode="HTML", 
        reply_markup=main_menu_markup(message.chat.id)
    )
    active_admin_panels[message.chat.id] = sent_msg.message_id

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):

    if call.data == "ignore":
        bot.answer_callback_query(call.id)
        return

    active_admin_panels[call.message.chat.id] = call.message.message_id

    if call.data == "post_now":
        bot.answer_callback_query(call.id, "جاري تحديث منشور القناة...")
        post_table_to_channel(call.message.chat.id)
        
    elif call.data == "add_account":
        bot.answer_callback_query(call.id, "أرسل رابط الفيديو للحساب الجديد")
        msg = bot.edit_message_text(
            "<b>➕ إضافة حساب جديد</b>\nالرجاء إرسال رابط الحساب الآن:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_new_account_url)
        
    elif call.data.startswith("seturl_"):
        acc_id = int(call.data.split("_")[1])
        acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
        if acc:
            bot.answer_callback_query(call.id, f"أرسل الرابط لـ {acc['name']}")
            msg = bot.edit_message_text(
                f"<b>🔗 تعديل رابط الحساب: {acc['name']}</b>\nالرجاء إرسال الرابط الجديد:",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
            bot.register_next_step_handler(msg, process_url_update, acc_id)

    elif call.data.startswith("togglevip_"):
        acc_id = int(call.data.split("_")[1])
        acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
        if acc:
            acc["is_vip"] = not acc.get("is_vip", False)
            save_account(acc)
            
            status_msg = "تم تمييز الحساب كـ VIP ⭐" if acc["is_vip"] else "تمت إزالة حالة VIP ✖️"
            bot.answer_callback_query(call.id, status_msg)
            
            bot.edit_message_text(
                "<b>لوحة تحكم الحسابات ⚙️</b>\nتم تحديث حالة الحساب:", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML", 
                reply_markup=main_menu_markup(call.message.chat.id)
            )
            auto_update_channel_message()

    elif call.data.startswith("delete_"):
        acc_id = int(call.data.split("_")[1])
        delete_account_from_db(acc_id)
        
        remaining_accounts = load_accounts()
        for index, acc in enumerate(remaining_accounts):
            acc["id"] = index
            acc["name"] = f"Account {index + 1}"
            
        accounts_col.delete_many({})
        
        if remaining_accounts:
            accounts_col.insert_many(remaining_accounts)
            
        bot.answer_callback_query(call.id, "تم حذف الحساب وإعادة ترتيب الحسابات المتبقية بنجاح ✅")
        bot.edit_message_text(
            "<b>لوحة تحكم الحسابات ⚙️</b>\nتم تحديث القائمة بعد الحذف (تم الحفاظ على الروابط الأصلية):", 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="HTML", 
            reply_markup=main_menu_markup(call.message.chat.id)
        )
        auto_update_channel_message()
        
    elif call.data.startswith("toggle_"):
        acc_id = int(call.data.split("_")[1])
        acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
        if not acc: return
        
        if acc["reserved"]:
            acc["reserved"] = False
            acc["time_from"] = ""
            acc["time_to"] = ""
            acc["client_username"] = ""
            acc["warned_near_expiry"] = False
            save_account(acc)
            bot.answer_callback_query(call.id, f"الحساب {acc['name']} متاح الآن ✅")
            bot.edit_message_text(
                "<b>لوحة تحكم الحسابات ⚙️</b>\nتم التحديث:", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML", 
                reply_markup=main_menu_markup(call.message.chat.id)
            )
            auto_update_channel_message()
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("1️⃣ إدخال وقت الانتهاء فقط", callback_data=f"timeopt_1_{acc_id}"))
            markup.add(InlineKeyboardButton("2️⃣ إدخال وقت البدء والانتهاء", callback_data=f"timeopt_2_{acc_id}"))
            
            bot.edit_message_text(
                f"<b>تعديل الحساب: {acc['name']} ⚙️</b>\nاختر طريقة تحديد الوقت:", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML", 
                reply_markup=markup
            )

    elif call.data.startswith("timeopt_1_"):
        acc_id = int(call.data.split("_")[2])
        acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
        if acc:
            msg = bot.edit_message_text(
                f"<b>الطريقة 1: وقت الانتهاء فقط ⏰</b>\nأدخل وقت الانتهاء لـ {acc['name']} (مثال: <code>9PM</code> أو <code>9:30 PM</code>):", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML"
            )
            bot.register_next_step_handler(msg, process_time_input_end_only, acc_id)

    elif call.data.startswith("timeopt_2_"):
        acc_id = int(call.data.split("_")[2])
        acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
        if acc:
            msg = bot.edit_message_text(
                f"<b>الطريقة 2: وقت البدء والانتهاء ⏳</b>\nأدخل وقت البدء، ثم فاصلة (,)، ثم وقت الانتهاء لـ {acc['name']}\n(مثال: <code>8PM, 10PM</code>):", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML"
            )
            bot.register_next_step_handler(msg, process_time_input_start_end, acc_id)

    # --- معالجة طلب الفاتورة ---
    elif call.data.startswith("invoice_"):
        parts = call.data.split("_")
        action = parts[1]
        acc_id = int(parts[2])
        
        if action == "skip":
            bot.answer_callback_query(call.id, "تم تخطي الفاتورة ✅")
            bot.edit_message_text(
                "<b>لوحة تحكم الحسابات ⚙️</b>\nتم حفظ الحجز بنجاح ✅", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML", 
                reply_markup=main_menu_markup(call.message.chat.id)
            )
        elif action == "create":
            bot.answer_callback_query(call.id, "جاري تجهيز الفاتورة...")
            msg = bot.edit_message_text(
                "<b>🧾 إنشاء فاتورة جديدة</b>\nأدخل السعر المطلوب (أرقام فقط، مثال: <code>8</code> أو <code>25</code>):", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="HTML"
            )
            bot.register_next_step_handler(msg, process_invoice_price, acc_id)

def process_new_account_url(message):
    url_text = message.text.strip()
    accounts = load_accounts()
    
    new_id = len(accounts)
    new_name = f"Account {new_id + 1}"
    
    new_account = {
        "id": new_id,
        "name": new_name,
        "reserved": False,
        "time_from": "",
        "time_to": "",
        "post_url": url_text if url_text.startswith("http") else "",
        "client_username": "",
        "warned_near_expiry": False,
        "is_vip": False
    }
    
    save_account(new_account)
    
    sent_msg = bot.send_message(
        message.chat.id, 
        f"<b>لوحة تحكم الحسابات ⚙️</b>\nتمت إضافة ({new_name}) بنجاح ✅", 
        parse_mode="HTML", 
        reply_markup=main_menu_markup(message.chat.id)
    )
    active_admin_panels[message.chat.id] = sent_msg.message_id
    auto_update_channel_message()

def process_time_input_end_only(message, acc_id):
    time_text = message.text.strip()
    acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
    if not acc: return
    
    target_minutes = parse_time_to_minutes(time_text)
    
    if target_minutes is None:
        sent_msg = bot.send_message(message.chat.id, "<b>⚠️ صيغة الوقت غير صحيحة. يرجى المحاولة مرة أخرى.</b>", parse_mode="HTML", reply_markup=main_menu_markup(message.chat.id))
        active_admin_panels[message.chat.id] = sent_msg.message_id
        return

    clean_time_str = format_minutes_to_time_str(target_minutes)

    acc["reserved"] = True
    acc["time_to"] = clean_time_str
    acc["time_from"] = ""
    acc["warned_near_expiry"] = False
    save_account(acc)
    
    msg = bot.send_message(
        message.chat.id, 
        f"<b>👤 ربط يوزر العميل (اختياري)</b>\nأرسل يوزر العميل لـ {acc['name']} (مثال: <code>@username</code>) لتنبيهه قبل الانتهاء بـ 5 دقائق، أو أرسل <b>skip</b>:", 
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_client_username, acc_id)

def process_time_input_start_end(message, acc_id):
    text = message.text.strip()
    acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
    if not acc: return
    
    if "," in text:
        parts = text.split(",")
    else:
        parts = text.split(",")
        
    if len(parts) != 2:
        sent_msg = bot.send_message(message.chat.id, "<b>⚠️ يجب إدخال وقتين يفصل بينهما فاصلة (,)</b>", parse_mode="HTML", reply_markup=main_menu_markup(message.chat.id))
        active_admin_panels[message.chat.id] = sent_msg.message_id
        return
        
    start_time_str = parts[0].strip()
    end_time_str = parts[1].strip()
    
    start_minutes = parse_time_to_minutes(start_time_str)
    end_minutes = parse_time_to_minutes(end_time_str)
    
    if start_minutes is None or end_minutes is None:
        sent_msg = bot.send_message(message.chat.id, "<b>⚠️ صيغة الوقت غير صحيحة. يرجى المحاولة مرة أخرى.</b>", parse_mode="HTML", reply_markup=main_menu_markup(message.chat.id))
        active_admin_panels[message.chat.id] = sent_msg.message_id
        return
        
    clean_start_str = format_minutes_to_time_str(start_minutes)
    clean_end_str = format_minutes_to_time_str(end_minutes)

    acc["reserved"] = True
    acc["time_from"] = clean_start_str
    acc["time_to"] = clean_end_str
    acc["warned_near_expiry"] = False
    save_account(acc)
    
    msg = bot.send_message(
        message.chat.id, 
        f"<b>👤 ربط يوزر العميل (اختياري)</b>\nأرسل يوزر العميل لـ {acc['name']} (مثال: <code>@username</code>) لتنبيهه قبل الانتهاء بـ 5 دقائق، أو أرسل <b>skip</b>:", 
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_client_username, acc_id)

def process_client_username(message, acc_id):
    acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
    if not acc: return
    
    raw_user = message.text.strip()
    if raw_user.lower() not in ["skip", "no", "-"]:
        clean_user = raw_user.replace("@", "").strip()
        acc["client_username"] = clean_user
    else:
        acc["client_username"] = ""
        
    save_account(acc)
    
    auto_update_channel_message()
    
    invoice_markup = InlineKeyboardMarkup()
    invoice_markup.row(
        InlineKeyboardButton("🧾 إنشاء فاتورة", callback_data=f"invoice_create_{acc_id}"),
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"invoice_skip_{acc_id}")
    )
    
    sent_msg = bot.send_message(
        message.chat.id, 
        f"<b>تم حفظ الحجز لـ {acc['name']} بنجاح ✅</b>\nهل تريد إنشاء فاتورة سريعة وإرسالها للعميل؟", 
        parse_mode="HTML", 
        reply_markup=invoice_markup
    )
    active_admin_panels[message.chat.id] = sent_msg.message_id

def process_invoice_price(message, acc_id):
    price_text = message.text.strip()
    acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
    if not acc: return
    
    # واجهة الأدمن (عربي)
    time_display_admin = f"من {acc['time_from']} إلى {acc['time_to']}" if acc['time_from'] else f"حتى {acc['time_to']}"
    acc_name_display_admin = "حساب VIP 💎" if acc.get("is_vip") else acc['name']
    
    admin_invoice_text = (
        f"<b>⚜️ R A R E   Z O N E ⚜️</b>\n"
        f"تأجير الحسابات المميزة\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"أهلاً بك عزيزي 🤍\n"
        f"طلبك جاهز. تفاصيل الحجز:\n\n"
        f"🛒 | <b>الحساب:</b> {acc_name_display_admin}\n"
        f"⏳ | <b>المدة:</b> {time_display_admin}\n"
        f"💵 | <b>الإجمالي المطلوب:</b> {price_text}$\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>الرجاء إتمام التحويل وإرسال إثبات الدفع (سكرين شوت)\n"
        f"لاستلام بيانات الدخول فوراً ✅</i>"
    )

    # واجهة العميل (إنجليزي)
    time_display_client = f"From {acc['time_from']} to {acc['time_to']}" if acc['time_from'] else f"Until {acc['time_to']}"
    acc_name_display_client = "💎 VIP Account 💎" if acc.get("is_vip") else acc['name']

    client_invoice_text = (
        f"⚜️ R A R E   Z O N E ⚜️\n"
        f"Luxury Account Rentals\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome dear 🤍\n"
        f"Your order is ready. Booking details:\n\n"
        f"🛒 | Account: {acc_name_display_client}\n"
        f"⏳ | Duration: {time_display_client}\n"
        f"💵 | Total Required: {price_text}$\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Please complete the transfer and send the payment proof (screenshot)\n"
        f"to receive login details immediately ✅"
    )
    
    encoded_invoice = urllib.parse.quote(client_invoice_text)
    client_action_markup = InlineKeyboardMarkup()
    
    if acc.get("client_username"):
        client_link = f"https://t.me/{acc['client_username']}?text={encoded_invoice}"
        client_action_markup.add(InlineKeyboardButton(f"💬 إرسال الفاتورة إلى @{acc['client_username']}", url=client_link))
    else:
        client_action_markup.add(InlineKeyboardButton("نسخ الفاتورة (بدون يوزر)", callback_data="ignore"))
    
    client_action_markup.add(InlineKeyboardButton("🔙 رجوع للوحة التحكم", callback_data=f"invoice_skip_{acc_id}"))

    sent_msg = bot.send_message(
        message.chat.id, 
        f"<b>الفاتورة جاهزة:</b>\n\n{admin_invoice_text}", 
        parse_mode="HTML", 
        reply_markup=client_action_markup
    )
    active_admin_panels[message.chat.id] = sent_msg.message_id


def process_url_update(message, acc_id):
    url_text = message.text.strip()
    acc = accounts_col.find_one({"id": acc_id}, {"_id": 0})
    if not acc: return
    
    if url_text.startswith("http"):
        acc["post_url"] = url_text
        save_account(acc)
        
    sent_msg = bot.send_message(
        message.chat.id, 
        f"<b>لوحة تحكم الحسابات ⚙️️</b>\nتم تحديث الرابط بنجاح ✅", 
        parse_mode="HTML", 
        reply_markup=main_menu_markup(message.chat.id)
    )
    active_admin_panels[message.chat.id] = sent_msg.message_id
    auto_update_channel_message()

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()

    t = Thread(target=check_expiration_loop, daemon=True)
    t.start()
    
    print("Admin bot running successfully with MongoDB persistence & Flask & VIP & Invoices...")
    bot.infinity_polling()
