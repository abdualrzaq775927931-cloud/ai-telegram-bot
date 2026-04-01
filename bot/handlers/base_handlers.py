from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..database.user_manager import UserManager
from ..database.db_manager import get_session
from ..database.models import User, Quiz, Channel, BotSettings
from ..config.settings import SPAM_THRESHOLD
from .admin_handlers import log_event, check_admin
import time
from datetime import datetime

# تخزين مؤقت لمنع السبام
user_last_action = {}

async def is_spamming(user_id):
    """التحقق مما إذا كان المستخدم يقوم بعمليات سريعة جداً."""
    current_time = time.time()
    last_time = user_last_action.get(user_id, 0)
    if current_time - last_time < SPAM_THRESHOLD:
        return True
    user_last_action[user_id] = current_time
    return False

# --- 1. دالة التحقق من الاشتراك الإجباري (الديناميكية) ---
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    # جلب يوزر القناة من قاعدة البيانات (التي يحددها الأدمن من البوت)
    setting = session.query(BotSettings).filter_by(key='force_sub_channel').first()
    session.close()

    # إذا لم يحدد الأدمن قناة بعد، اسمح للمستخدم بالمرور
    if not setting or not setting.value:
        return True

    channel_username = setting.value  # مثال: @MyChannel
    user_id = update.effective_user.id

    try:
        member = await context.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        # في حال وجود خطأ في المعرف أو لم يتم العثور على العضو
        pass

    # إذا لم يكن مشتركاً، أرسل رسالة تطلب الاشتراك
    keyboard = [[InlineKeyboardButton("📢 اشترك في القناة أولاً", url=f"https://t.me/{channel_username.replace('@','')}")]]
    text = f"⚠️ عذراً! يجب عليك الاشتراك في قناة البوت الرسمية لتتمكن من استخدامه:\n\n{channel_username}\n\nبعد الاشتراك، أرسل /start مجدداً."
    
    if update.callback_query:
        await update.callback_query.answer("يجب الاشتراك أولاً!", show_alert=True)
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return False

# --- 2. دالة البداية (Start) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع أمر /start."""
    user = update.effective_user
    
    if await is_spamming(user.id):
        return

    # التحقق من الاشتراك الإجباري
    if not await check_subscription(update, context):
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
        await log_event(context, f"👤 مستخدم جديد سجل: {user.full_name} (@{user.username or 'بدون_يوزر'})")
    
    keyboard = [
        [
            InlineKeyboardButton("📊 إنشاء استطلاع", callback_data="create_poll"),
            InlineKeyboardButton("📝 إنشاء اختبار", callback_data="help")
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
    
    welcome_text = (
        f"مرحباً بك {user.full_name} في بوت الاختبارات! 🚀\n\n"
        "لإضافة اختبار جديد بسرعة، استخدم التنسيق التالي:\n"
        "`/add_quiz الجواب الصحيح;نص السؤال;خيار1;خيار2;خيار3`"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- 3. أمر إضافة اختبار بالصيغة المطلوبة (;) ---
async def add_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة اختبار بصيغة: الجواب;السؤال;خيارات"""
    if not await check_subscription(update, context): return

    raw_text = " ".join(context.args)
    if not raw_text or ";" not in raw_text:
        await update.message.reply_text(
            "❌ *صيغة خاطئة!*\nالرجاء استخدام التنسيق التالي:\n"
            "`/add_quiz الجواب الصحيح;السؤال;الخيار1;الخيار2;الخيار3`",
            parse_mode="Markdown"
        )
        return

    # تقسيم النص باستخدام الفاصلة المنقوطة
    parts = [p.strip() for p in raw_text.split(";")]
    if len(parts) < 4:
        await update.message.reply_text("❌ خطأ: يجب توفر (جواب، سؤال، وخيارين على الأقل).")
        return

    correct_ans = parts[0]
    question_text = parts[1]
    options = parts[2:]

    # التحقق من وجود الجواب الصحيح ضمن الخيارات
    if correct_ans not in options:
        await update.message.reply_text(f"❌ خطأ: الإجابة الصحيحة `{correct_ans}` غير موجودة ضمن الخيارات التي أرسلتها!")
        return

    session = get_session()
    try:
        db_user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        new_quiz = Quiz(
            creator_id=db_user.id,
            title=question_text[:30],
            questions=[{
                "question": question_text,
                "options": options,
                "correct_index": options.index(correct_ans)
            }],
            is_active=True
        )
        session.add(new_quiz)
        session.commit()
        
        await update.message.reply_text(f"✅ تم حفظ الاختبار بنجاح!\n❓ السؤال: {question_text}")
        # إرسال تقرير لقناة السجل (Railway)
        await log_event(context, f"📝 مستخدم أنشأ اختباراً جديداً:\nالمنشئ: {update.effective_user.full_name}\nالسؤال: {question_text}")
    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ أثناء الحفظ في قاعدة البيانات.")
    finally:
        session.close()

# --- 4. دالة المساعدة ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تعليمات الاستخدام."""
    help_text = (
        "📖 *دليل إضافة الاختبارات:*\n\n"
        "أرسل الأمر `/add_quiz` متبوعاً بالبيانات مقسمة بـ (`;`) كالتالي:\n"
        "1️⃣ الجواب الصحيح\n"
        "2️⃣ نص السؤال\n"
        "3️⃣ الخيارات (من 2 إلى 10 خيارات)\n\n"
        "*مثال:*\n"
        "`/add_quiz بغداد;ماهي عاصمة العراق؟;القاهرة;بغداد;دمشق`"
    )
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 5. بقية الدوال (الملف الشخصي، لوحة الصدارة، اختباراتي) ---
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    stats = UserManager.get_user_stats(user_id)
    
    if stats:
        profile_text = (
            f"👤 *ملفك الشخصي:*\n\n"
            f"✨ المستوى: `{stats['level']}`\n"
            f"⭐ نقاط الخبرة (XP): `{stats['xp']}`\n"
            f"📝 الاختبارات المكتملة: `{stats['total_quizzes']}`\n"
            f"🎯 متوسط النتيجة: `{stats['avg_score']:.1f}%`"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
        await query.answer()
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await query.answer("لم يتم العثور على بياناتك.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    top_users = UserManager.get_leaderboard(10)
    
    leaderboard_text = "🏆 *لوحة الصدارة (أعلى 10 مستخدمين):*\n\n"
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leaderboard_text += f"{medal} {user.full_name} - {user.xp} XP\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
    await query.answer()
    await query.edit_message_text(leaderboard_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    session = get_session()
    try:
        db_user = session.query(User).filter(User.telegram_id == user_id).first()
        quizzes = session.query(Quiz).filter(Quiz.creator_id == db_user.id).all()
        
        if not quizzes:
            await query.edit_message_text("لم تقم بإنشاء أي اختبارات بعد. 📝", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]))
            return

        text = "📚 *قائمة اختباراتك:*"
        keyboard = []
        for quiz in quizzes:
            keyboard.append([InlineKeyboardButton(f"📝 {quiz.title}", callback_data=f"quiz_view_{quiz.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    finally:
        session.close()

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة الإعدادات (يمكنك توسيعها لاحقاً)"""
    text = "⚙️ *إعدادات المستخدم:*\n\nهذا القسم سيسمح لك بتغيير لغة البوت أو تنبيهات الإشعارات قريباً."
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
