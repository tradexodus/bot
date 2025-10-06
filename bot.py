from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import json, os, asyncio

DATA_FILE = "attendance.json"
GROUP_ID = -1001234567890  # ضع هنا ID القروب الذي تريد إرسال التقرير إليه

def load_data():
    return json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else {}

def save_data(data):
    json.dump(data, open(DATA_FILE, "w"))

def parse_duration(d):
    h, m, s = map(int, d.split(":"))
    return timedelta(hours=h, minutes=m, seconds=s)

async def in_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.full_name
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    data.setdefault(user, {})
    data[user][today] = {"in": datetime.now().isoformat()}
    save_data(data)
    await update.message.reply_text(f"✅ تم تسجيل دخولك الساعة {datetime.now().strftime('%H:%M:%S')}")

async def out_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.full_name
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")

    if user not in data or today not in data[user] or "in" not in data[user][today]:
        await update.message.reply_text("⚠️ لم يتم تسجيل دخولك أولاً (in).")
        return

    time_in = datetime.fromisoformat(data[user][today]["in"])
    time_out = datetime.now()
    duration = time_out - time_in

    data[user][today]["out"] = time_out.isoformat()
    data[user][today]["duration"] = str(duration).split(".")[0]
    save_data(data)

    await update.message.reply_text(
        f"👋 تم تسجيل خروجك الساعة {time_out.strftime('%H:%M:%S')}\n"
        f"⏱ مدة دوامك اليوم: {duration}"
    )

async def week_report_text():
    data = load_data()
    now = datetime.now()
    week_start = now - timedelta(days=6)
    text = "📆 **تقرير الأسبوع الأخير** 📆\n\n"

    for user, days in data.items():
        total = timedelta()
        for date, info in days.items():
            try:
                d = datetime.fromisoformat(date)
            except Exception:
                continue
            if week_start.date() <= d.date() <= now.date() and "duration" in info:
                total += parse_duration(info["duration"])
        hours = round(total.total_seconds() / 3600, 2)
        text += f"- {user}: {hours} ساعة\n"

    return text or "لا يوجد بيانات للأسبوع الحالي."

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await week_report_text()
    await update.message.reply_text(text)

async def send_weekly_report(app):
    text = await week_report_text()
    await app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")

def schedule_weekly_report(app):
    scheduler = BackgroundScheduler(timezone="Asia/Riyadh")  # غيّر حسب منطقتك
    scheduler.add_job(lambda: asyncio.create_task(send_weekly_report(app)),
                      'cron', day_of_week='fri', hour=18, minute=0)
    scheduler.start()

async def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()

    app.add_handler(CommandHandler("in", in_command))
    app.add_handler(CommandHandler("out", out_command))
    app.add_handler(CommandHandler("week", week))

    # تفعيل الجدولة الأسبوعية
    schedule_weekly_report(app)

    print("✅ البوت يعمل... التقرير الأسبوعي سيُرسل كل جمعة الساعة 6:00 مساءً")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
