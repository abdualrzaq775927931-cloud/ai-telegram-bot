import os
import logging
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# تحميل المتغيرات من ملف .env (للتطوير المحلي)
load_dotenv()

# إعداد التسجيل (logging) بشكل مفصل جداً للتشخيص
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# تقليل ضجيج مكتبة httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# الحصول على التوكن الخاص ببوت تليجرام من المتغيرات البيئية
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# التحقق من وجود التوكن وإظهار رسالة واضحة في الـ Logs
if not TELEGRAM_BOT_TOKEN:
    logger.error("خطأ فادح: TELEGRAM_BOT_TOKEN غير موجود في المتغيرات البيئية (Variables) في Railway.")
    logger.info("يرجى التأكد من إضافة TELEGRAM_BOT_TOKEN في تبويب Variables في مشروعك على Railway.")
else:
    logger.info(f"تم العثور على التوكن: {TELEGRAM_BOT_TOKEN[:5]}...{TELEGRAM_BOT_TOKEN[-5:]}")

# اسم ملف قاعدة البيانات
DB_NAME = 'news_autoposter.db'

# دالة لتهيئة قاعدة البيانات
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feed_name TEXT NOT NULL,
                feed_url TEXT NOT NULL,
                channel_id TEXT, -- تم تغييره إلى TEXT لدعم المعرفات التي تبدأ بـ @ أو -100
                UNIQUE(user_id, feed_url)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS published_news (
                link TEXT PRIMARY KEY,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("تمت تهيئة قاعدة البيانات بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

# دالة لإضافة مصدر جديد لقاعدة البيانات
def add_feed_to_db(user_id: int, feed_name: str, feed_url: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_feeds (user_id, feed_name, feed_url) VALUES (?, ?, ?)", (user_id, feed_name, feed_url))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# دالة للحصول على مصادر المستخدم من قاعدة البيانات
def get_user_feeds_from_db(user_id: int) -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, feed_name, feed_url, channel_id FROM user_feeds WHERE user_id = ?", (user_id,))
    feeds = cursor.fetchall()
    conn.close()
    return feeds

# دالة لحذف مصدر من قاعدة البيانات
def remove_feed_from_db(user_id: int, feed_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_feeds WHERE user_id = ? AND id = ?", (user_id, feed_id))
    conn.commit()
    return cursor.rowcount > 0

# دالة لتحديث channel_id لمصادر المستخدم
def update_user_channel_id(user_id: int, channel_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_feeds SET channel_id = ? WHERE user_id = ?", (channel_id, user_id))
    conn.commit()
    conn.close()

# دالة للتحقق مما إذا كان الخبر قد تم نشره من قبل
def is_news_published(link: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM published_news WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# دالة لتسجيل الخبر كمنشور
def mark_news_as_published(link: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO published_news (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

# دالة لجلب الأخبار من مصدر RSS معين ونشرها
async def fetch_and_post_news(context: ContextTypes.DEFAULT_TYPE):
    logger.info("جاري فحص المصادر بحثاً عن أخبار جديدة...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id, feed_name, feed_url, channel_id FROM user_feeds WHERE channel_id IS NOT NULL")
    all_feeds = cursor.fetchall()
    conn.close()

    for user_id, feed_name, feed_url, channel_id in all_feeds:
        try:
            feed = feedparser.parse(feed_url)
            # نأخذ آخر 5 أخبار فقط لتجنب الضغط
            for entry in reversed(feed.entries[:5]): 
                title = entry.title
                link = entry.link
                
                if not is_news_published(link):
                    message_text = f"<b>{feed_name}:</b>\n<a href=\"{link}\">{title}</a>"
                    try:
                        await context.bot.send_message(chat_id=channel_id, text=message_text, parse_mode='HTML', disable_web_page_preview=False)
                        mark_news_as_published(link)
                        logger.info(f"تم نشر خبر جديد: {title}")
                        await asyncio.sleep(1) # لتجنب تجاوز حدود API
                    except Exception as e:
                        logger.error(f"خطأ في النشر للقناة {channel_id}: {e}")
        except Exception as e:
            logger.error(f"خطأ في جلب الأخبار من {feed_url}: {e}")

# دالة لمعالجة أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"تلقيت أمر /start من المستخدم {update.effective_user.id}")
    await update.message.reply_text(
        f"مرحباً بك يا {update.effective_user.first_name}! أنا بوت الأخبار الناشر الآلي.\n\n"
        "الأوامر المتاحة:\n"
        "/add [رابط_RSS] [اسم_المصدر] - لإضافة مصدر جديد.\n"
        "/list - لعرض مصادرك.\n"
        "/remove [رقم] - لحذف مصدر.\n"
        "/set_channel [معرف_القناة] - لتعيين القناة (مثال: @MyChannel).\n"
        "/news - للنشر اليدوي الآن.\n\n"
        "البوت سيفحص الأخبار تلقائياً كل دقيقة."
    )

# دالة لمعالجة أمر /add
async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("الصيغة: /add [رابط_RSS] [اسم_المصدر]")
        return

    feed_url = args[0]
    feed_name = " ".join(args[1:])
    user_id = update.effective_user.id

    if add_feed_to_db(user_id, feed_name, feed_url):
        await update.message.reply_text(f"تمت إضافة '{feed_name}' بنجاح!")
    else:
        await update.message.reply_text(f"المصدر موجود بالفعل أو الرابط غير صالح.")

# دالة لمعالجة أمر /list
async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    feeds = get_user_feeds_from_db(user_id)

    if not feeds:
        await update.message.reply_text("لا توجد مصادر مضافة.")
        return

    message_text = "مصادرك:\n"
    for feed_id, name, url, ch_id in feeds:
        message_text += f"{feed_id}. {name} (القناة: {ch_id})\n"
    await update.message.reply_text(message_text)

# دالة لمعالجة أمر /remove
async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("الصيغة: /remove [رقم].")
        return

    feed_id = int(args[0])
    user_id = update.effective_user.id

    if remove_feed_from_db(user_id, feed_id):
        await update.message.reply_text(f"تم حذف المصدر {feed_id}.")
    else:
        await update.message.reply_text(f"لم يتم العثور على المصدر.")

# دالة لمعالجة أمر /set_channel
async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("الصيغة: /set_channel [معرف_القناة].")
        return
    
    channel_id = args[0]
    user_id = update.effective_user.id

    try:
        # محاولة إرسال رسالة تجريبية للتأكد من الصلاحيات
        test_msg = await context.bot.send_message(chat_id=channel_id, text="تم ربط البوت بهذه القناة بنجاح!")
        update_user_channel_id(user_id, channel_id)
        await update.message.reply_text(f"تم تعيين القناة {channel_id} بنجاح!")
    except Exception as e:
        logger.error(f"خطأ في ربط القناة: {e}")
        await update.message.reply_text(f"خطأ: تأكد أن البوت مشرف في القناة '{channel_id}' وأن المعرف صحيح.")

# الدالة الرئيسية لتشغيل البوت
def main() -> None:
    init_db()
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("توقف التشغيل بسبب فقدان التوكن.")
        return

    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("add", add_feed))
        application.add_handler(CommandHandler("list", list_feeds))
        application.add_handler(CommandHandler("remove", remove_feed))
        application.add_handler(CommandHandler("set_channel", set_channel))
        application.add_handler(CommandHandler("news", fetch_and_post_news))

        job_queue = application.job_queue
        job_queue.run_repeating(fetch_and_post_news, interval=60, first=10) 

        logger.info("البوت بدأ العمل بنجاح وجاري الاستماع للرسائل...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"خطأ فادح أثناء تشغيل البوت: {e}")

if __name__ == '__main__':
    main()
