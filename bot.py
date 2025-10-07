from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import json, os, asyncio

DATA_FILE = "attendance.json"
GROUP_ID = -1001234567890  # ضع هنا ID القروب الذي تريد إرسال التقرير إليه
TZ = pytz.timezone("Asia/Riyadh")  # توقيت الرياض

def load_data():
    return json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else {}

def save_data(data):
    json.dump(data, open(DATA_FILE, "w"))

def parse_duration(d):
    h, m, s = map(int, d.split(":"))
    return timedelta(hours=h, minutes=m, seconds=s)

# ------------------------- IN COMMAND -------------------------
async def in_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.full_name
    data = load_data()
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    data.setdefault(user, {})
    data[user].setdefault(today, [])

    # منع تعدد دخول بدون خروج
    if data[user][today] and "out" not in data[user][today][-1]:
        await update.message.reply_text("⚠️ لديك تسجيل دخول مفتوح، يرجى تسجيل خروج أولاً (out).")
        return

    data[user][today].append({"in": now.isoformat()})
    save_data(data)
    await update.message.reply_text(f"✅ تم تسجيل دخولك الساعة {now.strftime('%H:%M:%S')}")

# ------------------------- OUT COMMAND -------------------------
async def out_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.full_name
    data = load_data()
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    if user not in data or today not in data[user] or not data[user][today]:
        await update.message.reply_text("⚠️ لم يتم تسجيل دخولك أولاً (in).")
        return

    last_entry = data[user][today][-1]
    if "out" in last_entry:
        await update.message.reply_text("⚠️ تم تسجيل خروجك مسبقاً، يرجى تسجيل دخول جديد أولاً (in).")
        return

    time_in = datetime.fromisoformat(last_entry["in"])
    duration = now - time_in

    last_entry["out"] = now.isoformat()
    last_entry["duration"] = str(duration).split(".")[0]
    save_data(data)

    await update.message.reply_text(
        f"👋 تم تسجيل خروجك الساعة {now.strftime('%H:%M:%S')}\n"
        f"⏱ مدة دوامك: {duration}"
    )

# ------------------------- WEEK REPORT -------------------------
async def week_report_text():
    data = load_data()
    now = datetime.now(TZ)

    # تحديد بداية الأسبوع (السبت) ونهايته (الخميس)
    week_start = now - timedelta(days=(now.weekday() + 2) % 7)
    week_end = week_start + timedelta(days=5)

    start_str = week_start.strftime("%d/%m/%Y")
    end_str = week_end.strftime("%d/%m/%Y")

    text = f"📆 **تقرير دوام الأسبوع ({start_str} - {end_str})** 📆\n\n"
    if not data:
        return text + "لا يوجد بيانات لهذا الأسبوع."

    for user, days in data.items():
        total = timedelta()
        for date, entries in days.items():
            try:
                d = datetime.fromisoformat(date)
            except Exception:
                continue
            if week_start.date() <= d.date() <= week_end.date():
                for entry in entries:
                    if "duration" in entry:
                        total += parse_duration(entry["duration"])
        hours = round(total.total_seconds() / 3600, 2)
        text += f"- {user}: {hours} ساعة\n"

    return text or "لا يوجد بيانات لهذا الأسبوع."

# ------------------------- SEND & CLEAN WEEKLY REPORT -------------------------
async def send_weekly_report(app):
    data = load_data()
    now = datetime.now(TZ)

    # تحديد بداية ونهاية الأسبوع
    week_start = now - timedelta(days=(now.weekday() + 2) % 7)
    week_end = week_start + timedelta(days=5)

    # إنشاء التقرير
    text = await week_report_text()
    await app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")

    # حذف بيانات الأسبوع المنتهي
    new_data = {}
    for user, days in data.items():
        for date, entries in days.items():
            try:
                d = datetime.fromisoformat(date)
            except Exception:
                continue
            # احتفظ فقط بالبيانات بعد نهاية الأسبوع الحالي
            if d.date() > week_end.date():
                new_data.setdefault(user, {})[date] = entries

    save_data(new_data)
    print("🧹 تم حذف بيانات الأسبوع القديم بعد إرسال التقرير.")

# ------------------------- WEEK COMMAND -------------------------
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await week_report_text()
    await update.message.reply_text(text)

# ------------------------- SCHEDULER -------------------------
def schedule_weekly_report(app):
    scheduler = BackgroundScheduler(timezone="Asia/Riyadh")
    scheduler.add_job(lambda: asyncio.create_task(send_weekly_report(app)),
                      'cron', day_of_week='fri', hour=18, minute=0)
    scheduler.start()

# ------------------------- GET CHAT ID -------------------------
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await update.message.reply_text(f"📍 Chat ID: `{chat_id}`", parse_mode="Markdown")

# ------------------------- TEXT HANDLER -------------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "in":
        await in_command(update, context)
    elif text == "out":
        await out_command(update, context)

# ------------------------- MAIN -------------------------
async def main():
    app = ApplicationBuilder().token("ضع_توكن_البوت_هنا").build()

    app.add_handler(CommandHandler("in", in_command))
    app.add_handler(CommandHandler("out", out_command))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("getid", get_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    schedule_weekly_report(app)

    print("✅ البوت يعمل... الوقت مضبوط حسب توقيت الرياض والتقرير الأسبوعي كل جمعة الساعة 6:00 مساءً")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
