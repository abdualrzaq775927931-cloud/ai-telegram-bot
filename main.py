import logging
import os
import sys

# إضافة المسار الحالي لضمان عمل الاستدعاءات بشكل صحيح
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# استدعاء الإعدادات وقاعدة البيانات
from bot.config.settings import BOT_TOKEN, ADMIN_IDS
from bot.database.db_manager import init_db

# استدعاء المعالجات (Handlers)
from bot.handlers.base_handlers import start, profile, leaderboard, help_command
from bot.handlers.admin_handlers import (
    admin_panel,
    start_broadcast,
    perform_broadcast,
    ban_user,
    BROADCAST_MESSAGE,
    is_admin
)
# استدعاء معالجات الاختبارات الجديدة
from bot.handlers.quiz_handlers import add_quiz_bulk, list_my_quizzes, delete_quiz

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # 1. تهيئة قاعدة البيانات
    init_db()
    
    # 2. بناء التطبيق
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 3. أوامر المستخدم العادية (Commands)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("my_quizzes", list_my_quizzes))
    application.add_handler(CommandHandler("delete_quiz", delete_quiz))
    
    # 4. أوامر الإدارة (Admin)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", ban_user))
    
    # 5. إضافة أمر إنشاء الاختبار السريع (الذي يدعم الفاصلة المنقوطة ;)
    application.add_handler(CommandHandler("add_quiz", add_quiz_bulk))
    
    # 6. معالجة الأزرار (Callback Handlers)
    application.add_handler(CallbackQueryHandler(profile, pattern="profile"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="leaderboard"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="admin_panel"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="help"))
    
    # 7. نظام المحادثة للبث الجماعي (Admin Broadcast)
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_broadcast)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(broadcast_conv)
    
    # 8. تشغيل البوت
    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
