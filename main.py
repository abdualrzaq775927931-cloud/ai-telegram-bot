import os
import logging
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# تحميل المتغيرات من ملف .env
load_dotenv()

# إعداد التسجيل (logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# الحصول على التوكن الخاص ببوت تليجرام من المتغيرات البيئية
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# التحقق من وجود التوكن
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN غير موجود في المتغيرات البيئية.")
    exit(1)

# اسم ملف قاعدة البيانات
DB_NAME = 'news_autoposter.db'

# دالة لتهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feed_name TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            channel_id INTEGER, -- القناة التي سيتم النشر فيها لهذا المستخدم
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

# دالة لإضافة مصدر جديد لقاعدة البيانات
def add_feed_to_db(user_id: int, feed_name: str, feed_url: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_feeds (user_id, feed_name, feed_url) VALUES (?, ?, ?)", (user_id, feed_name, feed_url))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Feed already exists for this user
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
def update_user_channel_id(user_id: int, channel_id: int):
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
    logger.info("بدء عملية جلب ونشر الأخبار المجدولة...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id, feed_name, feed_url, channel_id FROM user_feeds WHERE channel_id IS NOT NULL")
    all_feeds = cursor.fetchall()
    conn.close()

    for user_id, feed_name, feed_url, channel_id in all_feeds:
        if not channel_id:
            continue

        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                
                if not is_news_published(link):
                    message_text = f"**{feed_name}:**\n<a href=\"{link}\">{title}</a>"
                    try:
                        await context.bot.send_message(chat_id=channel_id, text=message_text, parse_mode='HTML', disable_web_page_preview=True)
                        mark_news_as_published(link)
                        logger.info(f"تم نشر خبر جديد في القناة {channel_id}: {title}")
                    except Exception as e:
                        logger.error(f"خطأ في نشر الخبر في القناة {channel_id}: {e}")
                        # يمكن إرسال رسالة خطأ للمستخدم هنا إذا أردت
        except Exception as e:
            logger.error(f"خطأ في جلب الأخبار من {feed_url} للمستخدم {user_id}: {e}")

# دالة لمعالجة أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"مرحباً بك يا {update.effective_user.first_name}! أنا بوت الأخبار الناشر الآلي الخاص بك.\n\n"
        "يمكنك استخدام الأوامر التالية:\n"
        "/add [رابط_RSS] [اسم_المصدر] - لإضافة مصدر إخباري جديد (مثال: /add https://www.aljazeera.net/rss/all.xml الجزيرة)\n"
        "/list - لعرض جميع المصادر التي أضفتها.\n"
        "/remove [رقم_المصدر] - لحذف مصدر إخباري باستخدام رقمه (استخدم /list لمعرفة الأرقام).\n"
        "/set_channel [معرف_القناة_أو_المجموعة] - لتعيين القناة أو المجموعة التي سينشر فيها البوت (يجب أن يكون البوت مشرفاً فيها).\n"
        "/news - لجلب آخر الأخبار من مصادرك المضافة ونشرها يدوياً في القناة المحددة (للتجربة).\n"
        "ملاحظة: البوت سيقوم بالنشر تلقائياً كل دقيقة بعد تعيين القناة."
    )

# دالة لمعالجة أمر /add
async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("الرجاء استخدام الصيغة: /add [رابط_RSS] [اسم_المصدر]")
        return

    feed_url = args[0]
    feed_name = " ".join(args[1:])
    user_id = update.effective_user.id

    if add_feed_to_db(user_id, feed_name, feed_url):
        await update.message.reply_text(f"تمت إضافة المصدر \'{feed_name}\' بنجاح!")
    else:
        await update.message.reply_text(f"المصدر \'{feed_name}\' موجود بالفعل أو الرابط غير صالح.")

# دالة لمعالجة أمر /list
async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    feeds = get_user_feeds_from_db(user_id)

    if not feeds:
        await update.message.reply_text("لم تقم بإضافة أي مصادر إخبارية بعد. استخدم /add لإضافة مصدر جديد.")
        return

    message_text = "مصادر الأخبار الخاصة بك:\n"
    for feed_id, name, url, channel_id in feeds:
        channel_info = f" (القناة: {channel_id})" if channel_id else ""
        message_text += f"{feed_id}. {name} ({url}){channel_info}\n"
    await update.message.reply_text(message_text)

# دالة لمعالجة أمر /remove
async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("الرجاء استخدام الصيغة: /remove [رقم_المصدر]. استخدم /list لمعرفة الأرقام.")
        return

    feed_id = int(args[0])
    user_id = update.effective_user.id

    if remove_feed_from_db(user_id, feed_id):
        await update.message.reply_text(f"تم حذف المصدر رقم {feed_id} بنجاح.")
    else:
        await update.message.reply_text(f"عذراً، لم يتم العثور على المصدر رقم {feed_id} أو أنه لا يخصك.")

# دالة لمعالجة أمر /set_channel
async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].lstrip('-').isdigit(): # يسمح بالأرقام السالبة لمعرفات القنوات
        await update.message.reply_text("الرجاء استخدام الصيغة: /set_channel [معرف_القناة_أو_المجموعة].")
        return
    
    channel_id = int(args[0])
    user_id = update.effective_user.id

    # التحقق مما إذا كان البوت مشرفاً في القناة
    try:
        chat_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
        if not chat_member.can_post_messages:
            await update.message.reply_text("عذراً، يجب أن يكون البوت مشرفاً في القناة/المجموعة ولديه صلاحية النشر.")
            return
    except Exception as e:
        logger.error(f"خطأ في التحقق من صلاحيات البوت في القناة {channel_id}: {e}")
        await update.message.reply_text("عذراً، لم أتمكن من التحقق من صلاحيات البوت في هذه القناة/المجموعة. تأكد من أن المعرف صحيح وأن البوت مشرف.")
        return

    update_user_channel_id(user_id, channel_id)
    await update.message.reply_text(f"تم تعيين القناة/المجموعة {channel_id} كمكان لنشر الأخبار الخاصة بك بنجاح!")

# دالة لمعالجة أمر /news (جلب الأخبار من مصادر المستخدم ونشرها يدوياً)
async def user_news_manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    feeds = get_user_feeds_from_db(user_id)

    if not feeds:
        await update.message.reply_text("لم تقم بإضافة أي مصادر إخبارية بعد. استخدم /add لإضافة مصدر جديد.")
        return
    
    # الحصول على channel_id من أول مصدر للمستخدم (نفترض أن المستخدم سيستخدم قناة واحدة للنشر)
    # يمكن تطوير هذا لاحقاً للسماح بقنوات مختلفة لكل مصدر
    channel_id_to_post = None
    for _, _, _, ch_id in feeds:
        if ch_id:
            channel_id_to_post = ch_id
            break

    if not channel_id_to_post:
        await update.message.reply_text("الرجاء تعيين قناة للنشر أولاً باستخدام أمر /set_channel.")
        return

    await update.message.reply_text("جاري جلب آخر الأخبار من مصادرك ونشرها في القناة المحددة...")
    
    for _, source_name, feed_url, _ in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                
                if not is_news_published(link):
                    message_text = f"**{source_name}:**\n<a href=\"{link}\">{title}</a>"
                    try:
                        await context.bot.send_message(chat_id=channel_id_to_post, text=message_text, parse_mode='HTML', disable_web_page_preview=True)
                        mark_news_as_published(link)
                        logger.info(f"تم نشر خبر جديد يدوياً في القناة {channel_id_to_post}: {title}")
                        await asyncio.sleep(1) # لتجنب تجاوز حدود API
                    except Exception as e:
                        logger.error(f"خطأ في نشر الخبر يدوياً في القناة {channel_id_to_post}: {e}")
                        await update.message.reply_text(f"عذراً، حدث خطأ أثناء نشر خبر من {source_name} في القناة.")
        except Exception as e:
            logger.error(f"خطأ في جلب الأخبار من {feed_url} للمستخدم {user_id}: {e}")
            await update.message.reply_text(f"عذراً، حدث خطأ أثناء جلب الأخبار من المصدر {source_name}.")
    
    await update.message.reply_text("تم الانتهاء من محاولة نشر الأخبار يدوياً.")

# الدالة الرئيسية لتشغيل البوت
def main() -> None:
    # تهيئة قاعدة البيانات عند بدء تشغيل البوت
    init_db()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("remove", remove_feed))
    application.add_handler(CommandHandler("set_channel", set_channel))
    application.add_handler(CommandHandler("news", user_news_manual_post))

    # جدولة مهمة النشر التلقائي
    job_queue = application.job_queue
    # سيتم تشغيل المهمة كل 10 دقائق (600 ثانية)
    job_queue.run_repeating(fetch_and_post_news, interval=60, first=10) 

    logger.info("البوت بدأ العمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
