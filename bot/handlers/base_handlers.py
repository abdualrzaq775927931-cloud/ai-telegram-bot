from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes, ConversationHandler
from ..database.user_manager import UserManager
from ..database.db_manager import get_session
from ..database.models import User, Quiz, Channel, BotSettings
from ..config.settings import SPAM_THRESHOLD
from .admin_handlers import log_event, check_admin
import time
from datetime import datetime

# --- المتغيرات والحالات الجديدة ---
WAITING_CHANNEL = "WAITING_CHANNEL"
user_last_action = {}

async def is_spamming(user_id):
    """التحقق مما إذا كان المستخدم يقوم بعمليات سريعة جداً."""
    current_time = time.time()
    last_time = user_last_action.get(user_id, 0)
    if current_time - last_time < SPAM_THRESHOLD:
        return True
    user_last_action[user_id] = current_time
    return False

# --- 1. دالة التحقق من الاشتراك الإجباري ---
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    setting = session.query(BotSettings).filter_by(key='force_sub_channel').first()
    session.close()

    if not setting or not setting.value:
        return True

    channel_username = setting.value
    user_id = update.effective_user.id

    try:
        member = await context.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass

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
    user = update.effective_user
    if await is_spamming(user.id): return
    if not await check_subscription(update, context): return

    db_user, created = UserManager.get_or_create_user(
        telegram_id=user.id, username=user.username, full_name=user.full_name
    )
    
    if db_user.is_banned:
        await update.message.reply_text("عذراً، لقد تم حظرك من استخدام البوت. 🚫")
        return

    if created:
        await log_event(context, f"👤 مستخدم جديد سجل: {user.full_name} (@{user.username or 'بدون_يوزر'})")
    
    keyboard = [
        [InlineKeyboardButton("📊 إنشاء استطلاع", callback_data="create_poll"), InlineKeyboardButton("📝 إنشاء اختبار", callback_data="help")],
        [InlineKeyboardButton("📚 اختباراتي", callback_data="my_quizzes"), InlineKeyboardButton("🏆 لوحة الصدارة", callback_data="leaderboard")],
        [InlineKeyboardButton("👤 ملفي الشخصي", callback_data="profile"), InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
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

# --- 3. ميزة الإضافة الجماعية /add_bulk (جديد) ---
async def add_bulk_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة عدة اختبارات: كل سطر اختبار بنفس الصيغة"""
    text = update.message.text.replace('/add_bulk', '').strip()
    if not text:
        await update.message.reply_text("❌ أرسل الاختبارات كل واحد في سطر.\nمثال:\nبغداد;عاصمة العراق؟;بغداد;دبي;دمشق")
        return
    
    lines = text.split('\n')
    session = get_session()
    db_user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    
    count = 0
    for line in lines:
        parts = [p.strip() for p in line.split(';')]
        if len(parts) >= 4 and parts[0] in parts[2:]:
            new_quiz = Quiz(
                creator_id=db_user.id,
                title=parts[1][:30],
                questions=[{"question": parts[1], "options": parts[2:], "correct_index": parts[2:].index(parts[0])}],
                is_active=True
            )
            session.add(new_quiz)
            count += 1
    session.commit()
    session.close()
    await update.message.reply_text(f"✅ تم إضافة {count} اختبار بنجاح!")

# --- 4. ميزة النشر الفوري /post_now (جديد) ---
async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نشر آخر اختبار للمستخدم في قناته المرتبطة"""
    session = get_session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    quiz = session.query(Quiz).filter_by(creator_id=user.id).order_by(Quiz.id.desc()).first()
    channel = session.query(Channel).filter_by(owner_id=user.id).first()
    
    if not quiz or not channel:
        await update.message.reply_text("❌ تأكد من إنشاء اختبار وربط قناة أولاً من الإعدادات!")
        session.close()
        return

    q_data = quiz.questions[0]
    try:
        await context.bot.send_poll(
            chat_id=channel.channel_id,
            question=q_data['question'],
            options=q_data['options'],
            type=Poll.QUIZ,
            correct_option_id=q_data['correct_index'],
            is_anonymous=False
        )
        await update.message.reply_text(f"🚀 تم النشر في القناة: {channel.title}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل النشر: تأكد أن البوت مشرف في {channel.channel_id}")
    finally:
        session.close()

# --- 5. ميزة الإعدادات وربط القنوات (معدل) ---
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📢 ربط قناة/مجموعة", callback_data="link_channel")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="start")]
    ]
    await query.edit_message_text("⚙️ *إعدادات المستخدم:*\n\nاربط قناتك لتتمكن من النشر التلقائي باستخدام `/post_now`.", 
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_link_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📥 أرسل الآن يوزر القناة أو المجموعة (مثال: @MyChannel) بشرط وجود البوت كمشرف.")
    return "WAITING_CHANNEL"

async def save_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    if not val.startswith('@'):
        await update.message.reply_text("❌ يرجى إرسال يوزر يبدأ بـ @")
        return "WAITING_CHANNEL"
    
    session = get_session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    try:
        chat = await context.bot.get_chat(val)
        new_channel = Channel(owner_id=user.id, channel_id=val, title=chat.title)
        session.merge(new_channel)
        session.commit()
        await update.message.reply_text(f"✅ تم ربط القناة {chat.title} بنجاح!")
    except:
        await update.message.reply_text("❌ لم يتم العثور على القناة أو البوت ليس مشرفاً.")
    finally:
        session.close()
    return ConversationHandler.END

# --- 6. التحكم في الاختبارات (عرض/حذف) (جديد) ---
async def quiz_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_') # quiz_delete_ID
    action, q_id = data[1], data[2]
    session = get_session()
    
    if action == "delete":
        session.query(Quiz).filter_by(id=q_id).delete()
        session.commit()
        await query.answer("✅ تم الحذف")
        await list_my_quizzes(update, context)
    elif action == "view":
        quiz = session.query(Quiz).filter_by(id=q_id).first()
        await query.answer()
        text = f"📝 *تفاصيل الاختبار:*\n\n❓ السؤال: {quiz.questions[0]['question']}"
        kb = [[InlineKeyboardButton("🗑️ حذف", callback_data=f"quiz_delete_{q_id}")], [InlineKeyboardButton("🔙 رجوع", callback_data="my_quizzes")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    session.close()

# --- بقية الدوال الأصلية (add_quiz_command, profile, leaderboard, etc.) ---
async def add_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update, context): return
    raw_text = " ".join(context.args)
    if not raw_text or ";" not in raw_text:
        await update.message.reply_text("❌ صيغة خاطئة! استخدم:\n`/add_quiz الجواب;السؤال;خيار1;خيار2`", parse_mode="Markdown")
        return
    parts = [p.strip() for p in raw_text.split(";")]
    if len(parts) < 4:
        await update.message.reply_text("❌ خطأ في عدد العناصر.")
        return
    correct_ans, question_text, options = parts[0], parts[1], parts[2:]
    if correct_ans not in options:
        await update.message.reply_text(f"❌ الإجابة `{correct_ans}` غير موجودة بالخيارات!")
        return
    session = get_session()
    try:
        db_user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        new_quiz = Quiz(creator_id=db_user.id, title=question_text[:30], 
                        questions=[{"question": question_text, "options": options, "correct_index": options.index(correct_ans)}], is_active=True)
        session.add(new_quiz)
        session.commit()
        await update.message.reply_text(f"✅ تم الحفظ بنجاح!")
        await log_event(context, f"📝 اختبار جديد من {update.effective_user.full_name}")
    finally:
        session.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "📖 *دليل الاختبارات:*\n\nاستخدم: `/add_quiz الجواب;السؤال;خيار1;خيار2`"
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]
    if update.callback_query: await update.callback_query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    stats = UserManager.get_user_stats(user_id)
    if stats:
        profile_text = f"👤 *ملفك:* \n✨ المستوى: `{stats['level']}`\n⭐ XP: `{stats['xp']}`"
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]), parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    top_users = UserManager.get_leaderboard(10)
    text = "🏆 *لوحة الصدارة:*\n\n"
    for i, user in enumerate(top_users, 1): text += f"{i}. {user.full_name} - {user.xp} XP\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]), parse_mode="Markdown")

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = get_session()
    try:
        db_user = session.query(User).filter(User.telegram_id == query.from_user.id).first()
        quizzes = session.query(Quiz).filter(Quiz.creator_id == db_user.id).all()
        if not quizzes:
            await query.edit_message_text("لا توجد اختبارات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="start")]]))
            return
        keyboard = [[InlineKeyboardButton(f"📝 {q.title}", callback_data=f"quiz_view_{q.id}")] for q in quizzes]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="start")])
        await query.edit_message_text("📚 *اختباراتك:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    finally: session.close()
    
