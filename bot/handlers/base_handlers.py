from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..database.user_manager import UserManager
from ..database.db_manager import get_session
from ..database.models import User, Quiz, Channel
from ..config.settings import SPAM_THRESHOLD
from .admin_handlers import log_event, check_admin
import time
from datetime import datetime

# Simple anti-spam storage
user_last_action = {}

async def is_spamming(user_id):
    """Check if user is performing actions too fast."""
    current_time = time.time()
    last_time = user_last_action.get(user_id, 0)
    if current_time - last_time < SPAM_THRESHOLD:
        return True
    user_last_action[user_id] = current_time
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    
    if await is_spamming(user.id):
        return

    db_user, created = UserManager.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name
    )
    
    if db_user.is_banned:
        await update.message.reply_text("عذراً، لقد تم حظرك من استخدام البوت. 🚫")
        return

    if created:
        await log_event(context, f"مستخدم جديد سجل: {user.full_name} (@{user.username or 'بدون_يوزر'})")
    
    keyboard = [
        [
            InlineKeyboardButton("📊 إنشاء استطلاع", callback_data="create_poll"),
            InlineKeyboardButton("📝 إنشاء اختبار", callback_data="create_quiz")
        ],
        [
            InlineKeyboardButton("📚 اختباراتي", callback_data="my_quizzes"),
            InlineKeyboardButton("🏆 لوحة الصدارة", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton("👤 ملفي الشخصي", callback_data="profile"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
        ],
        [InlineKeyboardButton("❓ مساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"مرحباً بك {user.full_name} في بوت استطلاعات الرأي والاختبارات المتطور! 🚀\n\n"
        "يمكنك من خلال هذا البوت إنشاء استطلاعات رأي تفاعلية واختبارات تعليمية ومشاركتها في القنوات والمجموعات.\n\n"
        "استخدم الأزرار أدناه للبدء:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user's quizzes with interactive buttons."""
    query = update.callback_query
    user_id = query.from_user.id
    
    session = get_session()
    db_user = session.query(User).filter(User.telegram_id == user_id).first()
    quizzes = session.query(Quiz).filter(Quiz.creator_id == db_user.id).all()
    
    if not quizzes:
        await query.answer("ليس لديك أي اختبارات حالياً.")
        await query.edit_message_text("لم تقم بإنشاء أي اختبارات بعد. 📝", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]))
        return

    await query.answer()
    text = "📚 *قائمة اختباراتك:*\nإليك الاختبارات التي قمت بإنشائها:"
    
    keyboard = []
    for quiz in quizzes:
        # Each quiz gets a row with title and action buttons
        keyboard.append([InlineKeyboardButton(f"📝 {quiz.title}", callback_data=f"quiz_view_{quiz.id}")])
        keyboard.append([
            InlineKeyboardButton("👁️ عرض", callback_data=f"quiz_view_{quiz.id}"),
            InlineKeyboardButton("✏️ تعديل", callback_data=f"quiz_edit_{quiz.id}"),
            InlineKeyboardButton("🗑️ حذف", callback_data=f"quiz_confirm_delete_{quiz.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def publish_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to publish a specific quiz: /publish [quiz_title_or_id]"""
    user_id = update.effective_user.id
    if not await check_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("يرجى تزويد اسم الاختبار أو معرفه: `/publish اسم_الاختبار`", parse_mode="Markdown")
        return

    search_term = " ".join(context.args)
    session = get_session()
    quiz = session.query(Quiz).filter((Quiz.title.ilike(f"%{search_term}%")) | (Quiz.id == (int(search_term) if search_term.isdigit() else 0))).first()

    if not quiz:
        await update.message.reply_text("عذراً، لم يتم العثور على هذا الاختبار. ❌")
        return

    # Show questions in an inline menu for selection or just publish the whole thing
    text = f"📢 *نشر اختبار: {quiz.title}*\n\n{quiz.description or ''}\n\nاختر السؤال للبدء بنشره:"
    keyboard = []
    for i, q in enumerate(quiz.questions):
        keyboard.append([InlineKeyboardButton(f"❓ {q['question'][:30]}...", callback_data=f"pub_q_{quiz.id}_{i}")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
        await query.answer()
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
    await query.answer()
    await query.edit_message_text(leaderboard_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
