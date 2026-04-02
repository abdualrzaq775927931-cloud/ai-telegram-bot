from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from ..config.settings import ADMIN_IDS, LOG_CHANNEL
from ..database.db_manager import get_session
from ..database.models import User, Poll, Quiz, Channel, BotSettings
import logging

logger = logging.getLogger(__name__)

# حالات الحوار (States) - يجب أن تطابق المستخدم في main.py
BROADCAST_MESSAGE = "BROADCAST_MESSAGE"
SET_FORCE_SUB = "SET_FORCE_SUB"

def is_super_admin(user_id):
    """التحقق مما إذا كان المستخدم هو المالك الأساسي"""
    return user_id in ADMIN_IDS

async def check_admin(user_id):
    """التحقق من صلاحيات المشرف"""
    if is_super_admin(user_id):
        return True
    session = get_session()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    is_admin = user.is_admin if user else False
    session.close()
    return is_admin

async def log_event(context: ContextTypes.DEFAULT_TYPE, message: str):
    """إرسال تقرير إلى مجموعة السجل"""
    if LOG_CHANNEL:
        try:
            await context.bot.send_message(
                chat_id=LOG_CHANNEL, 
                text=f"🔔 *سجل النشاطات:*\n{message}", 
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error sending log: {e}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم الرئيسية للمشرفين"""
    user_id = update.effective_user.id
    if not await check_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("⚠️ ليس لديك صلاحيات أدمن.", show_alert=True)
        return

    keyboard = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
            InlineKeyboardButton("📢 إذاعة (برودكاست)", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("🔒 ضبط الاشتراك الإجباري", callback_data="admin_set_sub"),
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user")
        ],
        [
            InlineKeyboardButton("🎖️ تعيين مشرف", callback_data="admin_make_admin"),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="start")
        ]
    ]
    
    text = "🛠 *لوحة تحكم المالك:*\n\nمرحباً بك. يمكنك الآن التحكم في إعدادات البوت والاشتراك الإجباري من هنا."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- 1. نظام ضبط الاشتراك الإجباري ---
async def start_set_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *إعداد الاشتراك الإجباري:*\n\n"
        "أرسل الآن يوزر القناة (مع الـ @) التي تريد فرض الاشتراك بها.\n"
        "مثال: `@MyChannel`\n\n"
        "إذ كنت تريد إلغاء الاشتراك الإجباري أرسل كلمة `إلغاء`", 
        parse_mode="Markdown"
    )
    return SET_FORCE_SUB

async def save_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    session = get_session()
    
    setting = session.query(BotSettings).filter_by(key='force_sub_channel').first()
    if not setting:
        setting = BotSettings(key='force_sub_channel')
        session.add(setting)
    
    if val == "إلغاء":
        setting.value = None
        response = "✅ تم إلغاء نظام الاشتراك الإجباري بنجاح."
    else:
        if not val.startswith('@'):
            await update.message.reply_text("❌ خطأ: يوزر القناة يجب أن يبدأ بـ @. حاول مرة أخرى:")
            session.close()
            return SET_FORCE_SUB
        setting.value = val
        response = f"✅ تم تعيين القناة {val} كاشتراك إجباري بنجاح."
    
    session.commit()
    session.close()
    await update.message.reply_text(response)
    await log_event(context, f"⚙️ قام الأدمن بتحديث الاشتراك الإجباري إلى: {val}")
    return ConversationHandler.END

# --- 2. نظام الإحصائيات الشامل ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = get_session()
    
    u_count = session.query(User).count()
    q_count = session.query(Quiz).count()
    c_count = session.query(Channel).count() # عدد القنوات المربوطة للنشر
    b_count = session.query(User).filter_by(is_banned=True).count()
    sub_setting = session.query(BotSettings).filter_by(key='force_sub_channel').first()
    sub_channel = sub_setting.value if sub_setting and sub_setting.value else "❌ غير مفعل"
    
    session.close()
    
    stats_text = (
        "📊 *إحصائيات الإدارة كاملة:*\n\n"
        f"👥 إجمالي المستخدمين: `{u_count}`\n"
        f"📝 إجمالي الاختبارات: `{q_count}`\n"
        f"📢 قنوات النشر المربوطة: `{c_count}`\n"
        f"🚫 عدد المحظورين: `{b_count}`\n"
        f"🔗 قناة الاشتراك الإجباري: `{sub_channel}`"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع للوحة", callback_data="admin_panel")]]
    await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- 3. نظام الإذاعة (Broadcast) ---
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📢 أرسل الآن الرسالة التي تريد بثها لجميع المستخدمين:")
    return BROADCAST_MESSAGE

async def perform_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broadcast_msg = update.message.text
    session = get_session()
    users = session.query(User.telegram_id).all()
    session.close()
    
    success, fail = 0, 0
    sent_msg = await update.message.reply_text("⏳ جاري الإرسال لجميع المستخدمين...")
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=broadcast_msg)
            success += 1
        except:
            fail += 1
            
    await sent_msg.edit_text(f"✅ اكتمل البث!\n\n👍 نجاح: {success}\n👎 فشل: {fail}")
    await log_event(context, f"📢 إذاعة جماعية بواسطة الأدمن وصلت لـ {success} مستخدم.")
    return ConversationHandler.END

# --- 4. أوامر الحظر وتعيين المشرفين ---
async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("❌ أرسل المعرف هكذا: `/ban 1234567`")
        return
    
    try:
        target_id = int(context.args[0])
        session = get_session()
        user = session.query(User).filter_by(telegram_id=target_id).first()
        if user:
            user.is_banned = True
            session.commit()
            await update.message.reply_text(f"🚫 تم حظر المستخدم {user.full_name} بنجاح.")
            await log_event(context, f"🚫 حظر مستخدم: {target_id}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
        session.close()
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")

async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚫 *إدارة الحظر:*\n\nلحظر مستخدم، أرسل الأمر التالي في المحادثة:\n`/ban ID_المستخدم`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
    )

async def admin_make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎖️ *تعيين مشرف جديد:*\n\nلتعيين شخص كمشرف، أرسل:\n`/makeadmin ID_المستخدم`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
    )

async def make_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("👑 عذراً، هذا الأمر للمالك الأساسي فقط.")
        return
    if not context.args:
        await update.message.reply_text("❌ أرسل المعرف هكذا: `/makeadmin 123456`")
        return
    
    try:
        target_id = int(context.args[0])
        session = get_session()
        user = session.query(User).filter(User.telegram_id == target_id).first()
        if user:
            user.is_admin = True
            session.commit()
            await update.message.reply_text(f"✅ تم تعيين {user.full_name} كمشرف بنجاح!")
            await log_event(context, f"🎖️ تعيين مشرف جديد: {target_id}")
        else:
            await update.message.reply_text("❌ المستخدم لم يسبق له الدخول للبوت.")
        session.close()
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
