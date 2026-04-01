from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler 
from ..config.settings import ADMIN_IDS
from ..database.db_manager import get_session
from ..database.models import User, Poll, Quiz, GroupConfig # أضفنا GroupConfig هنا
from sqlalchemy import func

# Admin states for broadcasting
BROADCAST_MESSAGE = range(1)

def is_admin(user_id):
    """Check if user is a super admin."""
    return user_id in ADMIN_IDS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم مع إحصائيات القنوات والمستخدمين"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        message = update.message if update.message else update.callback_query.message
        await message.reply_text("عذراً، ليس لديك صلاحية الوصول إلى هذه اللوحة. 🚫")
        return

    session = get_session()
    try:
        total_users = session.query(User).count()
        total_quizzes = session.query(Quiz).count()
        total_channels = session.query(GroupConfig).count() # إحصائية القنوات الجديدة
        
        admin_text = (
            f"👑 *لوحة تحكم المالك (Super Admin)*\n\n"
            f"📊 *إحصائيات النظام:*\n"
            f"👤 إجمالي المستخدمين: {total_users}\n"
            f"📝 إجمالي الاختبارات: {total_quizzes}\n"
            f"📢 القنوات المرتبطة: {total_channels}\n\n"
            f"⚙️ *خيارات التحكم:*"
        )
        
        keyboard = [
            [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🚫 إدارة المحتوى", callback_data="admin_content_manage")],
            [InlineKeyboardButton("📈 تقرير مفصل", callback_data="admin_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.callback_query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode="Markdown")
    finally:
        session.close()

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية البث"""
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("غير مصرح لك.")
        return
        
    await query.answer()
    await query.edit_message_text("يرجى إرسال الرسالة التي تود بثها لجميع المستخدمين: 📢")
    return BROADCAST_MESSAGE

async def perform_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ البث الجماعي"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return ConversationHandler.END
        
    broadcast_msg = update.message.text
    session = get_session()
    try:
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
            f"❌ فشل: {fail_count}"
        )
    finally:
        session.close()
        
    return ConversationHandler.END
    
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("استخدم: /ban [user_id]")
        return
    
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(context.args[0])).first()
        if user:
            user.is_banned = True
            session.commit()
            await update.message.reply_text(f"🚫 تم حظر المستخدم {user.telegram_id}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود.")
    finally:
        session.close()
        
