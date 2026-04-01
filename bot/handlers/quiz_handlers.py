from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..database.db_manager import get_session
from ..database.models import User, Quiz, GroupConfig 
from sqlalchemy import func 

# --- الدالات القديمة مع تعديل بسيط للتوافق ---

async def add_quiz_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحليل وإضافة الاختبار بصيغة السطر الواحد"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إرسال البيانات. مثال:\n/add_quiz Title;Question;Correct;Opt1;Opt2")
        return
    
    try:
        raw_text = " ".join(context.args)
        parts = [p.strip() for p in raw_text.split(";")]
        
        if len(parts) < 4:
            await update.message.reply_text("❌ الصيغة ناقصة!")
            return

        title, question_text = parts[0], parts[1]
        options = parts[2:] 

        session = get_session()
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        
        if not user:
            await update.message.reply_text("❌ أرسل /start أولاً.")
            return

        new_quiz = Quiz(
            creator_id=user.id,
            title=title,
            questions=[{"question": question_text, "options": options, "correct_index": 0}],
            is_active=True
        )
        session.add(new_quiz)
        session.commit()
        await update.message.reply_text(f"✅ تم إضافة الاختبار: *{title}* بنجاح!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        session.close()

# --- الدالة المحدثة بالأزرار التفاعلية ---

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اختبارات المستخدم بأزرار إدارة تفاعلية"""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ أرسل /start أولاً.")
            return

        quizzes = session.query(Quiz).filter_by(creator_id=user.id).all()
        if not quizzes:
            await update.message.reply_text("📭 ليس لديك اختبارات حالياً.")
            return
            
        await update.message.reply_text("📋 *قائمة اختباراتك:*", parse_mode="Markdown")

        for q in quizzes:
            # إنشاء الأزرار المدمجة تحت كل اختبار
            keyboard = [[
                InlineKeyboardButton("👁️ عرض", callback_data=f"view_{q.id}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"confirm_del_{q.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🆔 `{q.id}` | 📝 *{q.title}*",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    finally:
        session.close()

# --- باقي الدالات (link_channel, post_now) تبقى كما هي ---

async def link_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ أرسل ID القناة. مثال: `/link_channel -100123`")
        return
    chat_id = context.args[0]
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        new_config = GroupConfig(chat_id=chat_id, owner_id=user.id)
        session.merge(new_config) 
        session.commit()
        await update.message.reply_text(f"✅ تم ربط القناة `{chat_id}` بنجاح!")
    finally:
        session.close()

async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    try:
        quiz = session.query(Quiz).order_by(func.random()).first()
        if not quiz: return
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        configs = session.query(GroupConfig).filter_by(owner_id=user.id).all()
        
        for config in configs:
            try:
                q = quiz.questions[0]
                await context.bot.send_poll(
                    chat_id=config.chat_id,
                    question=q['question'],
                    options=q['options'],
                    type="quiz",
                    correct_option_id=0
                )
            except: continue
        await update.message.reply_text("🚀 تم النشر.")
    finally:
        session.close()

# --- الدالة الجديدة لمعالجة الأزرار (Callback) ---

async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    session = get_session()
    
    try:
        if data.startswith("confirm_del_"):
            quiz_id = data.split("_")[2]
            keyboard = [[
                InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_{quiz_id}"),
                InlineKeyboardButton("❌ تراجع", callback_data="cancel_action")
            ]]
            await query.edit_message_text(
                "⚠️ *هل أنت متأكد من حذف هذا الاختبار؟*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif data.startswith("delete_"):
            quiz_id = int(data.split("_")[1])
            quiz = session.query(Quiz).filter_by(id=quiz_id).first()
            if quiz:
                session.delete(quiz)
                session.commit()
                await query.edit_message_text("✅ تم حذف الاختبار بنجاح.")
            else:
                await query.answer("❌ غير موجود.")

        elif data.startswith("view_"):
            quiz_id = int(data.split("_")[1])
            quiz = session.query(Quiz).filter_by(id=quiz_id).first()
            if quiz and quiz.questions:
                q = quiz.questions[0]
                text = f"📝 *عنوان:* {quiz.title}\n❓ *السؤال:* {q['question']}\n🔹 *الخيارات:* {', '.join(q['options'])}"
            else:
                text = "❌ لا توجد بيانات لهذا الاختبار."
            
            keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="cancel_action")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data == "cancel_action":
            await query.edit_message_text("↩️ تم الإلغاء.")
            
    finally:
        session.close()
        
