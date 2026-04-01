import logging
import os
import sys
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters
)
from sqlalchemy import func

# إضافة المسار
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.config.settings import BOT_TOKEN
from bot.database.db_manager import init_db, get_session
from bot.database.models import Quiz, GroupConfig
from bot.handlers.base_handlers import start, profile, leaderboard, help_command
from bot.handlers.admin_handlers import (
    admin_panel, start_broadcast, perform_broadcast, ban_user, BROADCAST_MESSAGE
)
from bot.handlers.quiz_handlers import (
    add_quiz_bulk, list_my_quizzes, delete_quiz, link_channel, post_now
)

# الإعدادات
logging.basicConfig(level=logging.INFO)

# دالة النشر التلقائي (تعمل كل ساعة)
async def auto_post_job(context):
    session = get_session()
    try:
        # اختيار سؤال عشوائي من قاعدة البيانات
        quiz = session.query(Quiz).order_by(func.random()).first()
        # جلب القنوات المرتبطة والمفعلة
        configs = session.query(GroupConfig).filter_by(is_active=True).all()
        
        if quiz and configs:
            q = quiz.questions[0]
            for config in configs:
                try:
                    await context.bot.send_poll(
                        chat_id=config.chat_id,
                        question=q['question'],
                        options=q['options'],
                        type="quiz",
                        correct_option_id=0,
                        explanation="بالتوفيق في الاختبار! ✅"
                    )
                except Exception as e:
                    logging.error(f"Error posting to {config.chat_id}: {e}")
                    continue
    finally:
        session.close()

def main():
    init_db()
    
    # بناء التطبيق
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # تسجيل الأوامر (دعم الصيغتين بـ _ وبدونها)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler(["add_quiz", "addquiz"], add_quiz_bulk))
    application.add_handler(CommandHandler(["my_quizzes", "myquizzes"], list_my_quizzes))
    application.add_handler(CommandHandler(["delete_quiz", "deletequiz"], delete_quiz))
    application.add_handler(CommandHandler(["link_channel", "linkchannel"], link_channel))
    application.add_handler(CommandHandler(["post_now", "postnow"], post_now))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", ban_user))
    
    # معالجة الأزرار (Callback Queries)
    application.add_handler(CallbackQueryHandler(profile, pattern="profile"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="leaderboard"))
    
    # معالجة البث (Broadcast Conversation)
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_broadcast)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ))
    
    # --- تفعيل الجدولة بأمان لضمان عدم حدوث Crash ---
    if application.job_queue:
        # تشغيل النشر التلقائي كل ساعة (3600 ثانية)
        application.job_queue.run_repeating(auto_post_job, interval=3600, first=10)
        print("✅ Job Queue is active: Auto-posting scheduled every 60 mins.")
    else:
        print("⚠️ Job Queue is NOT active. Check your requirements.txt for [job-queue].")

    print("🚀 Bot is starting... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
    
