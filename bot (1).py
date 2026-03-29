import os
import logging
import json
import random
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

import database

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Admin ID from environment
ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        logger.error("ADMIN_ID environment variable must be an integer.")
        ADMIN_ID = None

# States for poll creation
POLL_QUESTION, POLL_OPTIONS, POLL_CHANNEL_SELECTION = range(3)
# States for quiz publishing
QUIZ_PUBLISH_CHANNEL_SELECTION = range(1)
# States for Admin Broadcast
BROADCAST_TEXT = range(1)

# In-memory storage
user_poll_data = {}
user_quiz_publish_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    database.add_user(user.id, user.username, user.full_name)
    
    welcome_msg = (
        f"مرحباً {user.mention_html()}! 🌟\n\n"
        "أنا بوت استطلاع الرأي والاختبارات المطور. يمكنك استخدامي لإنشاء استطلاعات احترافية أو اختبارات تفاعلية.\n\n"
        "استخدم /help لعرض قائمة الأوامر المتاحة."
    )
    await update.message.reply_html(welcome_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "📜 *قائمة الأوامر المتاحة:*\n\n"
        "*🗳️ استطلاعات الرأي:*\n"
        "- /create_poll: إنشاء استطلاع رأي جديد.\n"
        "- /close_poll: إغلاق استطلاع (بالرد عليه).\n\n"
        "*🧠 الاختبارات (Quizzes):*\n"
        "- /add_quiz: إضافة سؤال (انظر الصيغة في الأسفل).\n"
        "- /start_quiz: بدء اختبار خاص بك.\n"
        "- /publish_quiz: نشر اختبار في قناة/مجموعة.\n"
        "- /my_quizzes: عرض اختباراتك.\n"
        "- /delete_quiz: حذف اختبار معين.\n\n"
        "*🏆 التفاعل:*\n"
        "- /leaderboard: عرض قائمة المتصدرين في الاختبارات.\n\n"
        "*📝 صيغة إضافة سؤال:* \n"
        "`/add_quiz Name;Question;Correct;W1;W2;W3`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Admin Features --- #
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin Dashboard."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    stats = database.get_stats()
    admin_msg = (
        "👨‍✈️ *لوحة تحكم المالك*\n\n"
        f"📊 *إحصائيات البوت:*\n"
        f"- عدد المستخدمين: {stats['users']}\n"
        f"- عدد الاستطلاعات: {stats['polls']}\n"
        f"- عدد الاختبارات: {stats['quizzes']}\n\n"
        "⚙️ *الإجراءات المتاحة:* /broadcast"
    )
    await update.message.reply_text(admin_msg, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the broadcast process."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    await update.message.reply_text("الرجاء إرسال الرسالة التي تريد إذاعتها لجميع المستخدمين.")
    return BROADCAST_TEXT

async def receive_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the broadcast message to all users."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    broadcast_msg = update.message.text
    users = database.get_all_users()
    
    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=broadcast_msg)
            count += 1
            await asyncio.sleep(0.05) # Avoid flood limits
        except Exception:
            pass

    await update.message.reply_text(f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.")
    return ConversationHandler.END

# --- Leaderboard --- #
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the leaderboard."""
    lb = database.get_leaderboard()
    if not lb:
        await update.message.reply_text("لا يوجد متصدرون حالياً. ابدأ الاختبارات لتجمع النقاط!")
        return

    lb_text = "🏆 *قائمة المتصدرين:*\n\n"
    for i, (name, username, score) in enumerate(lb, 1):
        display_name = name or username or "مستخدم"
        lb_text += f"{i}. {display_name} — {score} نقطة\n"
    
    await update.message.reply_text(lb_text, parse_mode='Markdown')

# --- Poll System --- #
async def create_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_poll_data[user_id] = {}
    await update.message.reply_text("الرجاء إرسال سؤال الاستطلاع.")
    return POLL_QUESTION

async def receive_poll_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_poll_data[user_id]["question"] = update.message.text
    await update.message.reply_text("الآن، أرسل خيارات الاستطلاع، كل خيار في سطر منفصل.")
    return POLL_OPTIONS

async def receive_poll_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    options = [opt.strip() for opt in update.message.text.split('\n') if opt.strip()]
    if len(options) < 2:
        await update.message.reply_text("الرجاء إدخال خيارين على الأقل.")
        return POLL_OPTIONS
    user_poll_data[user_id]["options"] = options
    await update.message.reply_text("أرسل معرف القناة/المجموعة (ID) لنشر الاستطلاع.")
    return POLL_CHANNEL_SELECTION

async def receive_poll_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    channel_id_str = update.message.text.strip()
    try:
        channel_id = int(channel_id_str)
        poll_question = user_poll_data[user_id]["question"]
        poll_options = user_poll_data[user_id]["options"]
        message = await context.bot.send_poll(chat_id=channel_id, question=poll_question, options=poll_options, is_anonymous=False)
        database.add_poll(message.poll.id, user_id, poll_question, json.dumps(poll_options), channel_id, message.message_id)
        await update.message.reply_text(f"✅ تم النشر في {channel_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل النشر: {e}")
    finally:
        user_poll_data.pop(user_id, None)
    return ConversationHandler.END

async def close_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message.reply_to_message or not update.message.reply_to_message.poll:
        await update.message.reply_text("يرجى الرد على الاستطلاع لإغلاقه.")
        return
    msg = update.message.reply_to_message
    stored = database.get_poll_by_message_id(msg.message_id, msg.chat.id)
    if stored and stored[1] == update.effective_user.id:
        try:
            await context.bot.stop_poll(msg.chat.id, msg.message_id)
            database.deactivate_poll(stored[0])
            await update.message.reply_text("✅ تم إغلاق الاستطلاع.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
    else:
        await update.message.reply_text("ليس لديك صلاحية لإغلاق هذا الاستطلاع.")

# --- Quiz System --- #
async def add_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lines = [line.strip() for line in update.message.text.split('\n') if line.strip().startswith('/add_quiz')]
    if not lines:
        await update.message.reply_text("استخدم: `/add_quiz Name;Q;Correct;W1;W2;W3`", parse_mode='Markdown')
        return
    count = 0
    for line in lines:
        parts = line.replace('/add_quiz ', '', 1).split(';')
        if len(parts) == 6:
            quiz_name, q, c, w1, w2, w3 = [p.strip() for p in parts]
            database.add_quiz_question(user_id, quiz_name, q, c, json.dumps([w1, w2, w3]))
            count += 1
    await update.message.reply_text(f"✅ تمت إضافة {count} سؤال.")

async def my_quizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    quizzes = database.get_user_quizzes(update.effective_user.id)
    if not quizzes:
        await update.message.reply_text("ليس لديك اختبارات.")
        return
    await update.message.reply_text("اختباراتك:\n- " + "\n- ".join(quizzes))

async def delete_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("حدد اسم الاختبار.")
        return
    name = " ".join(context.args)
    database.delete_quiz(update.effective_user.id, name)
    await update.message.reply_text(f"✅ تم حذف {name}.")

async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    quizzes = database.get_user_quizzes(update.effective_user.id)
    if not quizzes:
        await update.message.reply_text("لا توجد اختبارات.")
        return
    keyboard = [[InlineKeyboardButton(name, callback_data=f"sq_{name}")] for name in quizzes]
    await update.message.reply_text("اختر الاختبار:", reply_markup=InlineKeyboardMarkup(keyboard))

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    quiz_name = query.data.replace('sq_', '')
    questions = database.get_quiz_questions(query.from_user.id, quiz_name)
    if questions:
        context.user_data["cq_questions"] = questions
        context.user_data["cq_name"] = quiz_name
        database.start_user_quiz(query.from_user.id, quiz_name)
        await send_quiz_question(update, context, query.from_user.id, quiz_name, 0)
    else:
        await query.edit_message_text("لا توجد أسئلة.")

async def send_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, quiz_name: str, index: int, chat_id: int = None) -> None:
    questions = context.user_data.get("cq_questions")
    if not questions or index >= len(questions):
        state = database.get_user_current_quiz_state(user_id)
        if state:
            score = state[3]
            total = len(questions)
            # Update global score
            database.update_user_score(user_id, score)
            await context.bot.send_message(chat_id or user_id, f"🏁 انتهى الاختبار! نتيجتك: {score}/{total}.\nتمت إضافة النقاط لرصيدك في المتصدرين!")
            database.end_user_quiz(state[0])
        return

    q_data = questions[index]
    q_text, correct, wrongs = q_data[0], q_data[1], json.loads(q_data[2])
    answers = [correct] + wrongs
    random.shuffle(answers)
    keyboard = [[InlineKeyboardButton(a, callback_data=f"qa_{quiz_name}_{index}_{a}")] for a in answers]
    
    msg = await context.bot.send_message(chat_id or user_id, f"❓ السؤال {index+1}: {q_text}", reply_markup=InlineKeyboardMarkup(keyboard))
    state = database.get_user_current_quiz_state(user_id)
    if state:
        database.update_user_quiz_state(state[0], index, state[3], msg.message_id)

async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # Logic: qa_quizname_index_answer
    parts = query.data.split('_', 3)
    quiz_name, index, chosen = parts[1], int(parts[2]), parts[3]
    
    questions = context.user_data.get("cq_questions")
    if not questions: return

    state = database.get_user_current_quiz_state(query.from_user.id)
    if not state or state[2] != index: return

    correct = questions[index][1]
    new_score = state[3] + (1 if chosen == correct else 0)
    feedback = "✅ صحيح!" if chosen == correct else f"❌ خطأ! الإجابة: {correct}"
    
    await query.edit_message_text(f"{query.message.text}\n\n{feedback}")
    database.update_user_quiz_state(state[0], index + 1, new_score)
    await asyncio.sleep(1.5)
    await send_quiz_question(update, context, query.from_user.id, quiz_name, index + 1, chat_id=state[5])

async def publish_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    quizzes = database.get_user_quizzes(update.effective_user.id)
    if not quizzes:
        await update.message.reply_text("لا توجد اختبارات.")
        return
    keyboard = [[InlineKeyboardButton(n, callback_data=f"pq_{n}")] for n in quizzes]
    await update.message.reply_text("اختر الاختبار لنشره:", reply_markup=InlineKeyboardMarkup(keyboard))

async def publish_quiz_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_quiz_publish_data[query.from_user.id] = {"name": query.data.replace('pq_', '')}
    await query.edit_message_text("أرسل معرف القناة/المجموعة (ID).")
    return QUIZ_PUBLISH_CHANNEL_SELECTION

async def receive_quiz_publish_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        channel_id = int(update.message.text.strip())
        quiz_name = user_quiz_publish_data[user_id]["name"]
        questions = database.get_quiz_questions(user_id, quiz_name)
        context.user_data["cq_questions"] = questions
        database.start_user_quiz(user_id, quiz_name, channel_id=channel_id)
        await send_quiz_question(update, context, user_id, quiz_name, 0, chat_id=channel_id)
        await update.message.reply_text(f"✅ تم النشر في {channel_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Error: {context.error}")

def main() -> None:
    database.init_db()
    token = os.getenv("BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("close_poll", close_poll_command))
    app.add_handler(CommandHandler("add_quiz", add_quiz_command))
    app.add_handler(CommandHandler("my_quizzes", my_quizzes_command))
    app.add_handler(CommandHandler("delete_quiz", delete_quiz_command))
    app.add_handler(CommandHandler("start_quiz", start_quiz_command))
    app.add_handler(CommandHandler("publish_quiz", publish_quiz_command))

    # Poll Conv
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("create_poll", create_poll_command)],
        states={
            POLL_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_question)],
            POLL_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_options)],
            POLL_CHANNEL_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_channel_selection)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    ))

    # Broadcast Conv
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_text)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    ))

    # Quiz Publish Conv
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(publish_quiz_select_callback, pattern='^pq_')],
        states={QUIZ_PUBLISH_CHANNEL_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quiz_publish_channel_selection)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    ))

    app.add_handler(CallbackQueryHandler(start_quiz_callback, pattern='^sq_'))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern='^qa_'))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
