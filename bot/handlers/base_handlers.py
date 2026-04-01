from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..database.user_manager import UserManager

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    UserManager.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📊 إنشاء استطلاع", callback_data="create_poll"),
            InlineKeyboardButton("📝 إنشاء اختبار", callback_data="create_quiz")
        ],
        [
            InlineKeyboardButton("🏆 لوحة الصدارة", callback_data="leaderboard"),
            InlineKeyboardButton("👤 ملفي الشخصي", callback_data="profile")
        ],
        [
            InlineKeyboardButton("❓ مساعدة", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"مرحباً بك {user.full_name} في بوت استطلاعات الرأي والاختبارات المتطور! 🚀\n\n"
        "يمكنك من خلال هذا البوت إنشاء استطلاعات رأي تفاعلية واختبارات تعليمية ومشاركتها في القنوات والمجموعات.\n\n"
        "استخدم الأزرار أدناه للبدء:"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile and stats."""
    query = update.callback_query
    user_id = query.from_user.id
    stats = UserManager.get_user_stats(user_id)
    
    if stats:
        profile_text = (
            f"👤 *ملفك الشخصي:*\n\n"
            f"✨ المستوى: {stats['level']}\n"
            f"⭐ نقاط الخبرة (XP): {stats['xp']}\n"
            f"📝 الاختبارات المكتملة: {stats['total_quizzes']}\n"
            f"🎯 متوسط النتيجة: {stats['avg_score']:.1f}%\n"
        )
        await query.answer()
        await query.edit_message_text(profile_text, parse_mode="Markdown")
    else:
        await query.answer("لم يتم العثور على بياناتك بعد.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users."""
    query = update.callback_query
    top_users = UserManager.get_leaderboard(10)
    
    leaderboard_text = "🏆 *لوحة الصدارة (أعلى 10 مستخدمين):*\n\n"
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leaderboard_text += f"{medal} {user.full_name} - {user.xp} XP (Lvl {user.level})\n"
    
    await query.answer()
    await query.edit_message_text(leaderboard_text, parse_mode="Markdown")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المساعدة"""
    help_text = (
        "📖 *دليل أوامر البوت:*\n\n"
        "➕ /add_quiz - إنشاء اختبار جديد (العنوان;السؤال;الصح;...)\n"
        "📋 /my_quizzes - عرض اختباراتك التي أنشأتها\n"
        "👤 /profile - عرض ملفك الشخصي ونقاطك\n"
        "🏆 /leaderboard - عرض قائمة المتصدرين\n"
        "🚫 /ban - (للمالك فقط) حظر مستخدم\n"
    )
    # التحقق إذا كان الطلب من رسالة أو من ضغطة زر
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown")
        
