import logging
import os
import sys

# إضافة المسار الحالي لحل مشاكل الاستيراد لضمان عمل الموديلات
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

# استيراد الإعدادات والبيانات
from bot.config.settings import BOT_TOKEN
from bot.database.db_manager import init_db
from bot.handlers import base_handlers, admin_handlers

# إعداد اللوج (Logging) لتتبع الأخطاء في Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # 1. تهيئة قاعدة البيانات (إنشاء الجداول الجديدة)
    init_db()
    
    # 2. إنشاء التطبيق باستخدام التوكن
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # --- 3. نظام المحادثات للأدمن (Broadcast & Force Sub) ---
    # per_message=True تضمن أن البوت يفرق بين رسائل المستخدمين المختلفة في نفس الوقت
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_handlers.start_broadcast, pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_handlers.start_set_sub, pattern="^admin_set_sub$")
        ],
        states={
            admin_handlers.BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.perform_broadcast)
            ],
            admin_handlers.SET_FORCE_SUB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.save_force_sub)
            ]
        },
        fallbacks=[CommandHandler("start", base_handlers.start)],
        per_message=True 
    )
    application.add_handler(admin_conv)
    
    # --- 4. أوامر المستخدم والأدمن (Commands) ---
    application.add_handler(CommandHandler("start", base_handlers.start))
    application.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
    
    # أوامر التحكم في المستخدمين
    application.add_handler(CommandHandler("makeadmin", admin_handlers.make_admin_command))
    application.add_handler(CommandHandler("ban", admin_handlers.ban_user_command))
    application.add_handler(CommandHandler("help", base_handlers.help_command))
    
    # أمر إضافة الاختبار المطور بالفاصلة المنقوطة (;)
    application.add_handler(CommandHandler("add_quiz", base_handlers.add_quiz_command))
    
    # --- 5. معالجات الأزرار (Callback Handlers) ---
    # أزرار المستخدم الأساسية
    application.add_handler(CallbackQueryHandler(base_handlers.start, pattern="^start$"))
    application.add_handler(CallbackQueryHandler(base_handlers.profile, pattern="^profile$"))
    application.add_handler(CallbackQueryHandler(base_handlers.leaderboard, pattern="^leaderboard$"))
    application.add_handler(CallbackQueryHandler(base_handlers.list_my_quizzes, pattern="^my_quizzes$"))
    application.add_handler(CallbackQueryHandler(base_handlers.help_command, pattern="^help$"))
    
    # أزرار لوحة تحكم الأدمن
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_handlers.ban_user_command, pattern="^admin_ban_user$"))

    # --- 6. تشغيل البوت ---
    print("🚀 البوت انطلق الآن بنجاح وهو قيد التشغيل...")
    application.run_polling()

if __name__ == '__main__':
    main()
    
