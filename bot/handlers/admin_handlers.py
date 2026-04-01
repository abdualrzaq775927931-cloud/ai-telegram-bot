from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from ..config.settings import ADMIN_IDS, LOG_CHANNEL
from ..database.db_manager import get_session
from ..database.models import User, Poll, Quiz, Channel
import logging

logger = logging.getLogger(__name__)

# Admin states for broadcasting
BROADCAST_MESSAGE = range(1)

def is_super_admin(user_id):
    """Check if user is a super admin from config."""
    return user_id in ADMIN_IDS

async def check_admin(user_id):
    """Check if user is an admin in database or super admin."""
    if is_super_admin(user_id):
        return True
    session = get_session()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    return user and user.is_admin

async def log_event(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send log message to log channel if configured."""
    if LOG_CHANNEL:
        try:
            await context.bot.send_message(chat_id=LOG_CHANNEL, text=f"🔔 *سجل النشاطات:*\n{message}", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error sending log: {e}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the admin control panel."""
    user_id = update.effective_user.id
    if not await check_admin(user_id):
        await update.effective_message.reply_text("عذراً، ليس لديك صلاحية الوصول إلى هذه اللوحة. 🚫")
        return

    session = get_session()
    total_users = session.query(User).count()
    total_polls = session.query(Poll).count()
    total_quizzes = session.query(Quiz).count()
    total_channels = session.query(Channel).count()
    
    admin_text = (
        f"👑 *لوحة تحكم المشرفين*\n\n"
        f"📊 *إحصائيات النظام:*\n"
        f"👤 إجمالي المستخدمين: {total_users}\n"
        f"📊 إجمالي الاستطلاعات: {total_polls}\n"
        f"📝 إجمالي الاختبارات: {total_quizzes}\n"
        f"📢 القنوات المرتبطة: {total_channels}\n\n"
        f"⚙️ *خيارات التحكم:*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📢 إرسال رسالة جماعية (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"), InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user")],
        [InlineKeyboardButton("🎖️ تعيين مشرف", callback_data="admin_make_admin")],
        [InlineKeyboardButton("📈 تقرير مفصل", callback_data="admin_report")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode="Markdown")

async def make_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to make a user an admin: /makeadmin user_id"""
    user_id = update.effective_user.id
    if not is_super_admin(user_id):
        await update.message.reply_text("هذا الأمر متاح للمالك الأساسي فقط. 👑")
        return
    
    if not context.args:
        await update.message.reply_text("يرجى تزويد معرف المستخدم: `/makeadmin 12345678`", parse_mode="Markdown")
        return
    
    try:
        target_id = int(context.args[0])
        session = get_session()
        user = session.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text("المستخدم غير موجود في قاعدة البيانات.")
            return
        
        user.is_admin = True
        session.commit()
        await update.message.reply_text(f"✅ تم تعيين {user.full_name} كمشرف بنجاح!")
        await log_event(context, f"تم تعيين مشرف جديد: {user.full_name} ({target_id}) بواسطة المالك.")
    except ValueError:
        await update.message.reply_text("معرف المستخدم غير صحيح.")

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to ban a user: /ban user_id"""
    if not await check_admin(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("يرجى تزويد معرف المستخدم: `/ban 12345678`", parse_mode="Markdown")
        return
    
    try:
        target_id = int(context.args[0])
        if is_super_admin(target_id):
            await update.message.reply_text("لا يمكنك حظر المالك! ❌")
            return
            
        session = get_session()
        user = session.query(User).filter(User.telegram_id == target_id).first()
        if not user:
            await update.message.reply_text("المستخدم غير موجود.")
            return
        
        user.is_banned = True
        session.commit()
        await update.message.reply_text(f"🚫 تم حظر {user.full_name} بنجاح.")
        await log_event(context, f"تم حظر مستخدم: {user.full_name} ({target_id}) بواسطة المشرف {update.effective_user.full_name}.")
    except ValueError:
        await update.message.reply_text("معرف غير صحيح.")

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate broadcast process."""
    query = update.callback_query
    if not await check_admin(query.from_user.id):
        await query.answer("غير مصرح لك.")
        return
        
    await query.answer()
    await query.edit_message_text("يرجى إرسال الرسالة التي تود بثها لجميع المستخدمين: 📢")
    return BROADCAST_MESSAGE

async def perform_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message to all users."""
    user_id = update.effective_user.id
    if not await check_admin(user_id):
        return ConversationHandler.END
        
    broadcast_msg = update.message.text
    session = get_session()
    users = session.query(User.telegram_id).all()
    
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(f"جاري الإرسال إلى {len(users)} مستخدم... ⏳")
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=broadcast_msg)
            success_count += 1
        except Exception:
            fail_count += 1
            
    await status_msg.edit_text(
        f"✅ تم الانتهاء من البث!\n\n"
        f"✅ نجاح: {success_count}\n"
        f"❌ فشل (مستخدمين حظروا البوت): {fail_count}"
    )
    await log_event(context, f"تم إرسال رسالة جماعية بواسطة {update.effective_user.full_name}.\nالنجاح: {success_count} | الفشل: {fail_count}")
    return ConversationHandler.END
