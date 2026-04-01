from telegram import Update
from telegram.ext import ContextTypes
from ..database.db_manager import get_session
# أضفنا GroupConfig هنا لكي يتعرف الكود عليه
from ..database.models import User, Quiz, GroupConfig 
# أضفنا func لاستخدامه في اختيار سؤال عشوائي
from sqlalchemy import func 

async def add_quiz_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحليل وإضافة الاختبار بصيغة السطر الواحد باستخدام الفاصلة المنقوطة"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إرسال البيانات. مثال:\n/add_quiz Title;Question;Correct;Opt1;Opt2")
        return
    
    try:
        raw_text = " ".join(context.args)
        parts = [p.strip() for p in raw_text.split(";")]
        
        if len(parts) < 4:
            await update.message.reply_text("❌ الصيغة ناقصة! تأكد من وجود العنوان والسؤال و3 خيارات على الأقل.")
            return

        title = parts[0]
        question_text = parts[1]
        options = parts[2:] 

        session = get_session()
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        
        if not user:
            await update.message.reply_text("❌ يرجى إرسال /start أولاً لتسجيل حسابك.")
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
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    finally:
        session.close()

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اختبارات المستخدم"""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ يرجى إرسال /start أولاً.")
            return

        quizzes = session.query(Quiz).filter_by(creator_id=user.id).all()
        if not quizzes:
            await update.message.reply_text("📭 ليس لديك اختبارات حالياً.")
            return
            
        msg = "📋 *اختباراتك:*\n\n"
        for q in quizzes:
            msg += f"ID: `{q.id}` - {q.title}\n"
        
        msg += "\nلحذف اختبار استخدم: `/delete_quiz ID`"
        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        session.close()

async def delete_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف اختبار معين عبر الـ ID"""
    if not context.args:
        await update.message.reply_text("⚠️ يرجى تزويد ID الاختبار. مثال: `/delete_quiz 1`")
        return

    try:
        quiz_id = int(context.args[0])
        session = get_session()
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        
        quiz = session.query(Quiz).filter_by(id=quiz_id, creator_id=user.id).first()
        
        if quiz:
            session.delete(quiz)
            session.commit()
            await update.message.reply_text(f"🗑 تم حذف الاختبار رقم `{quiz_id}` بنجاح.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ لم يتم العثور على الاختبار أو لا تملك صلاحية حذفه.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
    finally:
        session.close()

async def link_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ربط قناة أو مجموعة بالبوت"""
    if not context.args:
        await update.message.reply_text("❌ أرسل ID القناة بعد الأمر. مثال: `/link_channel -1001234567`")
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
    """نشر اختبار عشوائي فوراً في القنوات المرتبطة"""
    session = get_session()
    try:
        quiz = session.query(Quiz).order_by(func.random()).first()
        if not quiz:
            await update.message.reply_text("❌ لا توجد اختبارات في القاعدة لنشرها.")
            return

        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        configs = session.query(GroupConfig).filter_by(owner_id=user.id).all()
        
        if not configs:
            await update.message.reply_text("⚠️ لم تربط أي قناة بعد. استخدم `/link_channel ID`")
            return

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
            except Exception:
                continue
        await update.message.reply_text("🚀 تم إرسال الاختبار للقنوات المرتبطة.")
    finally:
        session.close()
        
