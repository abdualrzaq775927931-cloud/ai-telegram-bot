import logging
import os
import sys
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
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

# --- دالة جديدة لترجمة أزرار الكيبورد العربية إلى وظائف ---
async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الاستجابة للنصوص العربية القادمة من أزرار ReplyKeyboardMarkup"""
    text = update.message.text
    
    if text == "📋 اختباراتي":
        await list_my_quizzes(update, context)
    elif text == "👤 ملفي الشخصي":
        await profile(update, context)
    elif text == "مساعدة ❓" or text == "❓ مساعدة":
        await help_command(update, context)
    elif text == "🚀 نشر فوري":
        await post_now(update, context)
    elif text == "📢 ربط قناة":
        await update.message.reply_text("🔗 لربط قناة، أرسل الأمر التالي مع ID القناة:\n`/linkchannel -100xxxxxxxx`", parse_mode="Markdown")
    elif text == "🚫 إدارة المحتوى":
        await admin_panel(update, context)
    elif text == "📈 تقرير مفصل":
        # يمكنك توجيهه للوحة الإدارة أو دالة التقارير
        await admin_panel(update, context)

# دالة النشر التلقائي (تعمل كل ساعة)
async def auto_post_job(context):
    session = get_session()
    try:
        quiz = session.query(Quiz).order_by(func.random()).first()
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
    
    # 1. تسجيل الأوامر المباشرة
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler(["add_quiz", "addquiz"], add_quiz_bulk))
    application.add_handler(CommandHandler(["my_quizzes", "myquizzes"], list_my_quizzes))
    application.add_handler(CommandHandler(["delete_quiz", "deletequiz"], delete_quiz))
    application.add_handler(CommandHandler(["link_channel", "linkchannel"], link_channel))
    application.add_handler(CommandHandler(["post_now", "postnow"], post_now))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("ban", ban_user))
    
    # 2. تسجيل معالج الأزرار النصية (العربية) - هام جداً لصورك
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    
    # 3. معالجة الأزرار المدمجة (Inline Callback Queries)
    application.add_handler(CallbackQueryHandler(profile, pattern="profile"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="leaderboard"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="help"))
    
    # 4. معالجة البث (Broadcast)
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_broadcast)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    ))
    
    # 5. تفعيل الجدولة
    if application.job_queue:
        application.job_queue.run_repeating(auto_post_job, interval=3600, first=10)
        print("✅ Job Queue is active: Auto-posting scheduled.")
    
    print("🚀 Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
            
