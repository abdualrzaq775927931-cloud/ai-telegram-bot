import os
import logging
import sqlite3
from dotenv import load_dotenv
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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
DB_NAME = 'news_feeds.db'

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
            UNIQUE(user_id, feed_url)
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
    cursor.execute("SELECT id, feed_name, feed_url FROM user_feeds WHERE user_id = ?", (user_id,))
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

# دالة لجلب الأخبار من مصدر RSS معين
def get_news_from_feed(feed_url: str, limit: int = 3) -> str:
    try:
        feed = feedparser.parse(feed_url)
        news_items = []
        for entry in feed.entries[:limit]:
            title = entry.title
            link = entry.link
            news_items.append(f"<a href=\"{link}\">{title}</a>")
        return "\n".join(news_items) if news_items else "لا توجد أخبار حالياً."
    except Exception as e:
        logger.error(f"خطأ في جلب الأخبار من {feed_url}: {e}")
        return "عذراً، حدث خطأ أثناء جلب الأخبار من هذا المصدر."

# دالة لمعالجة أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"مرحباً بك يا {update.effective_user.first_name}! أنا بوت الأخبار الشخصي الخاص بك.\n\n"
        "يمكنك استخدام الأوامر التالية:\n"
        "/add [رابط_RSS] [اسم_المصدر] - لإضافة مصدر إخباري جديد (مثال: /add https://www.aljazeera.net/rss/all.xml الجزيرة)\n"
        "/list - لعرض جميع المصادر التي أضفتها.\n"
        "/remove [رقم_المصدر] - لحذف مصدر إخباري باستخدام رقمه (استخدم /list لمعرفة الأرقام).\n"
        "/news - لجلب آخر الأخبار من جميع مصادرك المضافة."
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
        await update.message.reply_text(f"تمت إضافة المصدر '{feed_name}' بنجاح!")
    else:
        await update.message.reply_text(f"المصدر '{feed_name}' موجود بالفعل أو الرابط غير صالح.")

# دالة لمعالجة أمر /list
async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    feeds = get_user_feeds_from_db(user_id)

    if not feeds:
        await update.message.reply_text("لم تقم بإضافة أي مصادر إخبارية بعد. استخدم /add لإضافة مصدر جديد.")
        return

    message_text = "مصادر الأخبار الخاصة بك:\n"
    for feed_id, name, url in feeds:
        message_text += f"{feed_id}. {name} ({url})\n"
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

# دالة لمعالجة أمر /news (جلب الأخبار من مصادر المستخدم)
async def user_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    feeds = get_user_feeds_from_db(user_id)

    if not feeds:
        await update.message.reply_text("لم تقم بإضافة أي مصادر إخبارية بعد. استخدم /add لإضافة مصدر جديد.")
        return

    await update.message.reply_text("جاري جلب آخر الأخبار من مصادرك...")
    response_messages = []
    for _, source_name, feed_url in feeds:
        news = get_news_from_feed(feed_url)
        response_messages.append(f"**{source_name}:**\n{news}")
    
    final_message = "\n\n".join(response_messages)
    if not final_message.strip():
        final_message = "عذراً، لم أتمكن من جلب أي أخبار حالياً من مصادرك."
    
    await update.message.reply_text(final_message, parse_mode='HTML', disable_web_page_preview=True)

# الدالة الرئيسية لتشغيل البوت
def main() -> None:
    # تهيئة قاعدة البيانات عند بدء تشغيل البوت
    init_db()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالجات الأوامر الجديدة
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("remove", remove_feed))
    application.add_handler(CommandHandler("news", user_news))

    logger.info("البوت بدأ العمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
