from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from ..database.db_manager import get_session
from ..database.models import User

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب وعرض القائمة والتعليمات"""
    user_info = update.effective_user
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_info.id).first()
        if not user:
            user = User(telegram_id=user_info.id, username=user_info.username, full_name=user_info.full_name)
            session.add(user)
            session.commit()
    finally:
        session.close()

    # الأزرار التي ظهرت في صورتك
    main_keyboard = [
        [KeyboardButton("📋 اختباراتي"), KeyboardButton("👤 ملفي الشخصي")],
        [KeyboardButton("📢 ربط قناة"), KeyboardButton("🚀 نشر فوري")],
        [KeyboardButton("مساعدة ❓")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

    welcome_text = (
        f"أهلاً بك يا *{user_info.full_name}* 👋\n\n"
        "📖 *دليل سريع:*\n"
        "➕ `/addquiz` - إضافة اختبار\n"
        "📢 `/linkchannel` - ربط قناتك\n"
        "🚀 `/postnow` - نشر فوري\n"
        "🏆 `/leaderboard` - المتصدرين"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الملف الشخصي"""
    user_id = update.effective_user.id
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        txt = f"👤 *ملفك الشخصي:*\n\n⭐ النقاط: `{user.xp if user else 0} XP`"
        if update.message:
            await update.message.reply_text(txt, parse_mode="Markdown")
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(txt, parse_mode="Markdown")
    finally:
        session.close()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة المتصدرين (تمت إضافتها الآن لإصلاح الخطأ)"""
    session = get_session()
    try:
        top_users = session.query(User).order_by(User.xp.desc()).limit(10).all()
        text = "🏆 *لوحة المتصدرين:*\n\n"
        for i, user in enumerate(top_users, 1):
            text += f"{i}. {user.full_name} - `{user.xp} XP`\n"
        
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    finally:
        session.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة المساعدة"""
    help_text = "💡 استخدم الأوامر أو الأزرار بالأسفل للتحكم بالبوت."
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown")
        
