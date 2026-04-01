from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from ..database.db_manager import get_session
from ..database.models import User, Quiz, GroupConfig
# تأكد من أن UserManager مستورد بشكل صحيح إذا كنت تستخدمه، 
# أو استخدم Session مباشرة كما في الكود أدناه لضمان التوافق مع بقية ملفاتك

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب بالمستخدم وعرض قائمة التعليمات والأزرار الرئيسية"""
    user_info = update.effective_user
    
    # 1. تسجيل أو تحديث بيانات المستخدم في قاعدة البيانات
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_info.id).first()
        if not user:
            user = User(
                telegram_id=user_info.id,
                username=user_info.username,
                full_name=user_info.full_name,
                xp=0,
                level=1
            )
            session.add(user)
            session.commit()
    finally:
        session.close()

    # 2. إنشاء "أزرار الكيبورد" (Reply Keyboard) التي تظهر أسفل الشاشة (مثل صورك)
    main_keyboard = [
        [KeyboardButton("📋 اختباراتي"), KeyboardButton("👤 ملفي الشخصي")],
        [KeyboardButton("📢 ربط قناة"), KeyboardButton("🚀 نشر فوري")],
        [KeyboardButton("مساعدة ❓")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

    # 3. نص الترحيب والتعليمات (يظهر فوراً عند /start)
    welcome_text = (
        f"أهلاً بك يا *{user_info.full_name}* في بوت الاختبارات المتطور! ✨\n\n"
        f"📖 *دليل الأوامر السريع:*\n"
        f"➕ `/addquiz` - لإضافة اختبار (العنوان;السؤال;الصح;...)\n"
        f"📢 `/linkchannel` - لربط قناتك أو مجموعتك بالبوت\n"
        f"🚀 `/postnow` - لنشر سؤال عشوائي في قناتك فوراً\n"
        f"🏆 `/leaderboard` - عرض قائمة المتصدرين\n\n"
        f"💡 يمكنك استخدام الأزرار في الأسفل للوصول السريع للخدمات."
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض ملف المستخدم وإحصائياته"""
    user_id = update.effective_user.id
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if user:
            profile_text = (
                f"👤 *ملفك الشخصي:*\n\n"
                f"✨ المستوى: `{user.level}`\n"
                f"⭐ نقاط الخبرة: `{user.xp} XP`\n"
                f"📊 الاختبارات المكتملة: `0`\n" # يمكنك تحديثها لاحقاً
            )
            # التحقق إذا كان الاستدعاء من رسالة نصية أو زر
            if update.message:
                await update.message.reply_text(profile_text, parse_mode="Markdown")
            else:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(profile_text, parse_mode="Markdown")
        else:
            msg = "لم يتم العثور على بياناتك، أرسل /start أولاً."
            if update.message: await update.message.reply_text(msg)
    finally:
        session.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المساعدة التفصيلية"""
    help_text = (
        "📖 *دليل استخدام البوت:*\n\n"
        "🔹 *إضافة اختبار:* أرسل `/addquiz` متبوعاً بالبيانات هكذا:\n"
        "`العنوان;السؤال;الخيار الصح;خطأ1;خطأ2`\n\n"
        "🔹 *ربط القنوات:* أرسل `/linkchannel` ثم ID القناة.\n"
        "💡 تأكد من إضافة البوت كمشرف في القناة أولاً.\n\n"
        "🔹 *إدارة الاختبارات:* استخدم `/myquizzes` لحذف أو تعديل أسئلتك."
    )
    
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown")
        
