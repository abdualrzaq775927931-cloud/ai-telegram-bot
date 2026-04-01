from telegram import Update
from telegram.ext import ContextTypes
from ..database.db_manager import get_session
from ..database.models import User, Quiz

async def add_quiz_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحليل وإضافة الاختبار بصيغة السطر الواحد باستخدام الفاصلة المنقوطة"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إرسال البيانات. مثال:\n/add_quiz Title;Question;Correct;Opt1;Opt2")
        return
    
    # دمج النص وتحليله بناءً على الفاصلة المنقوطة
    raw_text = " ".join(context.args)
    parts = [p.strip() for p in raw_text.split(";")]
    
    if len(parts) < 4:
        await update.message.reply_text("❌ الصيغة ناقصة! تأكد من وجود العنوان والسؤال و3 خيارات على الأقل.")
        return

    title = parts[0]
    question_text = parts[1]
    options = parts[2:] # الخيار الأول بعد السؤال هو الصحيح دائماً

    session = get_session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    
    # حفظ الاختبار في قاعدة البيانات
    new_quiz = Quiz(
        creator_id=user.id,
        title=title,
        questions=[{"question": question_text, "options": options, "correct_index": 0}],
        is_active=True
    )
    session.add(new_quiz)
    session.commit()
    await update.message.reply_text(f"✅ تم إضافة الاختبار: *{title}* بنجاح!", parse_mode="Markdown")

async def list_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اختبارات المستخدم"""
    session = get_session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    quizzes = session.query(Quiz).filter_by(creator_id=user.id).all()
    
    if not quizzes:
        await update.message.reply_text("📭 ليس لديك اختبارات حالياً.")
        return
        
    msg = "📋 *اختباراتك:*\n\n"
    for q in quizzes:
        msg += f"ID: `{q.id}` - {q.title}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")
      
