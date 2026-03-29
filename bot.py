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
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# State for poll creation
POLL_QUESTION, POLL_OPTIONS, POLL_CHANNEL_SELECTION = range(3)

# State for quiz publishing
QUIZ_PUBLISH_CHANNEL_SELECTION = range(1)

# In-memory storage for ongoing poll creation (user_id: {"question": "", "options": []})
user_poll_data = {}

# In-memory storage for quiz publishing (user_id: {"quiz_name": ""})
user_quiz_publish_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    database.add_user(user.id)
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا بوت استطلاع الرأي والاختبارات. كيف يمكنني مساعدتك اليوم؟",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "أهلاً بك في بوت استطلاع الرأي والاختبارات!\n\n"
        "*ميزات استطلاع الرأي:*\n"
        "- /create_poll: لإنشاء استطلاع رأي جديد.\n"
        "- بعد إنشاء الاستطلاع، سأطلب منك اختيار القناة/المجموعة لنشره فيها.\n"
        "- /close_poll (بالرد على رسالة الاستطلاع): لإغلاق استطلاع قمت بإنشائه.\n\n"
        "*ميزات الاختبارات:*\n"
        "- /add_quiz Name;Question;CorrectAnswer;WrongAnswer1;WrongAnswer2;WrongAnswer3: لإضافة سؤال اختبار. يمكنك إضافة عدة أسئلة في رسالة واحدة.\n"
        "- /start_quiz: لبدء اختبار قمت بإنشائه.\n"
        "- /publish_quiz: لنشر اختبار في قناة/مجموعة.\n"
        "- /my_quizzes: لعرض قائمة بالاختبارات التي أنشأتها.\n"
        "- /delete_quiz Name: لحذف اختبار معين.\n"
        "- /delete_all_quizzes: لحذف جميع اختباراتك.\n\n"
        "*ملاحظات هامة:*\n"
        "- يجب أن أكون مشرفاً في القناة/المجموعة التي تريد نشر الاستطلاعات/الاختبارات فيها.\n"
        "- جميع الاستطلاعات والاختبارات يتم تخزينها لكل مستخدم على حدة.\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    try:
        if update.effective_message:
            await update.effective_message.reply_text("حدث خطأ! يرجى المحاولة مرة أخرى.")
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")

# --- Poll System --- #
async def create_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the poll creation process."""
    user_id = update.effective_user.id
    user_poll_data[user_id] = {}
    await update.message.reply_text("الرجاء إرسال سؤال الاستطلاع.")
    return POLL_QUESTION

async def receive_poll_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the poll question from the user."""
    user_id = update.effective_user.id
    user_poll_data[user_id]["question"] = update.message.text
    await update.message.reply_text("الآن، أرسل خيارات الاستطلاع، كل خيار في سطر منفصل.")
    return POLL_OPTIONS

async def receive_poll_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the poll options from the user."""
    user_id = update.effective_user.id
    options = [opt.strip() for opt in update.message.text.split('\n') if opt.strip()]
    if len(options) < 2:
        await update.message.reply_text("الرجاء إدخال خيارين على الأقل، كل خيار في سطر منفصل.")
        return POLL_OPTIONS
    
    user_poll_data[user_id]["options"] = options

    await update.message.reply_text(
        "الرجاء إرسال معرف القناة أو المجموعة (Chat ID) حيث تريد نشر الاستطلاع. "
        "(تأكد أن البوت مشرف في هذه القناة/المجموعة)"
    )
    return POLL_CHANNEL_SELECTION

async def receive_poll_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the channel ID and publishes the poll."""
    user_id = update.effective_user.id
    channel_id_str = update.message.text.strip()
    try:
        channel_id = int(channel_id_str)
    except ValueError:
        await update.message.reply_text("معرف القناة/المجموعة غير صالح. الرجاء إدخال رقم صحيح.")
        return POLL_CHANNEL_SELECTION

    poll_question = user_poll_data[user_id]["question"]
    poll_options = user_poll_data[user_id]["options"]

    try:
        message = await context.bot.send_poll(
            chat_id=channel_id,
            question=poll_question,
            options=poll_options,
            is_anonymous=False,
            allows_multiple_answers=False,
        )
        
        database.add_poll(
            poll_id=message.poll.id,
            user_id=user_id,
            question=poll_question,
            options=json.dumps(poll_options),
            channel_id=channel_id,
            message_id=message.message_id
        )

        await update.message.reply_text(
            f"تم نشر الاستطلاع بنجاح في القناة/المجموعة (ID: {channel_id}). "
            f"يمكنك إغلاق الاستطلاع لاحقاً بالرد على رسالة الاستطلاع في القناة بـ /close_poll"
        )

    except Exception as e:
        logger.error(f"Failed to send poll to channel {channel_id}: {e}")
        await update.message.reply_text(
            f"فشل نشر الاستطلاع في القناة/المجموعة (ID: {channel_id}). يرجى التأكد من أن البوت مشرف ولديه صلاحية نشر الاستطلاعات."
        )
    finally:
        if user_id in user_poll_data:
            del user_poll_data[user_id]
    return ConversationHandler.END

async def cancel_poll_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the poll creation process."""
    user_id = update.effective_user.id
    if user_id in user_poll_data:
        del user_poll_data[user_id]
    await update.message.reply_text("تم إلغاء إنشاء الاستطلاع.")
    return ConversationHandler.END

async def close_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Closes a poll by its message ID in a specific chat."""
    if not update.message.reply_to_message or not update.message.reply_to_message.poll:
        await update.message.reply_text("الرجاء الرد على رسالة الاستطلاع التي تريد إغلاقها.")
        return

    original_poll_message = update.message.reply_to_message
    poll_id = original_poll_message.poll.id
    channel_id = original_poll_message.chat.id
    message_id = original_poll_message.message_id
    user_id = update.effective_user.id

    stored_poll = database.get_poll_by_message_id(message_id, channel_id)
    if not stored_poll:
        await update.message.reply_text("عذراً، لا يمكن العثور على معلومات هذا الاستطلاع.")
        return

    if stored_poll[1] != user_id:
        await update.message.reply_text("عذراً، لا يمكنك إغلاق هذا الاستطلاع لأنك لست منشئه.")
        return
    
    if not stored_poll[4]: # is_active
        await update.message.reply_text("هذا الاستطلاع مغلق بالفعل.")
        return

    try:
        await context.bot.stop_poll(chat_id=channel_id, message_id=message_id)
        database.deactivate_poll(poll_id)
        await update.message.reply_text("تم إغلاق الاستطلاع بنجاح.")
    except Exception as e:
        logger.error(f"Failed to close poll {poll_id} in chat {channel_id}: {e}")
        await update.message.reply_text("فشل إغلاق الاستطلاع. يرجى التأكد من أن البوت مشرف.")

# --- Quiz System --- #
async def add_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adds quiz questions from a batch message."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    quiz_lines = [line.strip() for line in message_text.split('\n') if line.strip().startswith('/add_quiz')]

    if not quiz_lines:
        await update.message.reply_text("الرجاء استخدام الصيغة الصحيحة: /add_quiz Name;Question;CorrectAnswer;WrongAnswer1;WrongAnswer2;WrongAnswer3")
        return

    added_count = 0
    for line in quiz_lines:
        parts = line.replace('/add_quiz ', '', 1).split(';')
        if len(parts) == 6:
            quiz_name, question, correct_answer, wa1, wa2, wa3 = parts
            wrong_answers = json.dumps([wa1, wa2, wa3])
            database.add_quiz_question(user_id, quiz_name.strip(), question.strip(), correct_answer.strip(), wrong_answers)
            added_count += 1
        else:
            await update.message.reply_text(f"تنسيق غير صحيح للسؤال: {line}. تم تخطي هذا السؤال.")

    if added_count > 0:
        await update.message.reply_text(f"تمت إضافة {added_count} سؤال(أسئلة) بنجاح.")
    else:
        await update.message.reply_text("لم يتم إضافة أي أسئلة. يرجى التحقق من التنسيق.")

async def my_quizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all quizzes created by the user."""
    user_id = update.effective_user.id
    quizzes = database.get_user_quizzes(user_id)

    if not quizzes:
        await update.message.reply_text("لم تقم بإنشاء أي اختبارات بعد. استخدم /add_quiz لإضافة اختبارات.")
        return

    quiz_list_text = "اختباراتك:\n"
    for quiz_name in quizzes:
        quiz_list_text += f"- {quiz_name}\n"
    await update.message.reply_text(quiz_list_text)

async def delete_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes a specific quiz by name."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("الرجاء تحديد اسم الاختبار الذي تريد حذفه. مثال: /delete_quiz MyQuiz")
        return
    
    quiz_name = " ".join(context.args)
    database.delete_quiz(user_id, quiz_name)
    await update.message.reply_text(f"تم حذف الاختبار '{quiz_name}' بنجاح (إذا كان موجوداً).")

async def delete_all_quizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes all quizzes for the user."""
    user_id = update.effective_user.id
    database.delete_all_quizzes(user_id)
    await update.message.reply_text("تم حذف جميع اختباراتك بنجاح.")

async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a quiz for the user."""
    user_id = update.effective_user.id
    quizzes = database.get_user_quizzes(user_id)

    if not quizzes:
        await update.message.reply_text("لم تقم بإنشاء أي اختبارات بعد. استخدم /add_quiz لإضافة اختبارات.")
        return

    keyboard = [[InlineKeyboardButton(quiz_name, callback_data=f"start_quiz_{quiz_name}")] for quiz_name in quizzes]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("الرجاء اختيار الاختبار الذي تريد البدء به:", reply_markup=reply_markup)

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the selection of a quiz to start."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    quiz_name = query.data.replace('start_quiz_', '')

    questions = database.get_quiz_questions(user_id, quiz_name)
    if not questions:
        await query.edit_message_text("عذراً، لا توجد أسئلة لهذا الاختبار.")
        return
    
    context.user_data["current_quiz_questions"] = questions
    context.user_data["current_quiz_name"] = quiz_name

    database.start_user_quiz(user_id, quiz_name)

    await send_quiz_question(update, context, user_id, quiz_name, 0)

async def send_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, quiz_name: str, question_index: int, chat_id: int = None) -> None:
    """Sends a single quiz question to the user or channel."""
    questions = context.user_data.get("current_quiz_questions")
    if not questions or question_index >= len(questions):
        state = database.get_user_current_quiz_state(user_id)
        if state:
            final_score = state[3]
            total_questions = len(context.user_data["current_quiz_questions"])
            await context.bot.send_message(
                chat_id=chat_id or user_id,
                text=f"انتهى الاختبار! نتيجتك النهائية هي: {final_score} من {total_questions}."
            )
            database.end_user_quiz(state[0])
        return

    question_data = questions[question_index]
    question_text = question_data[0]
    correct_answer = question_data[1]
    wrong_answers = json.loads(question_data[2])

    all_answers = [correct_answer] + wrong_answers
    random.shuffle(all_answers)

    keyboard = []
    for answer in all_answers:
        keyboard.append([InlineKeyboardButton(answer, callback_data=f"quiz_answer_{quiz_name}_{question_index}_{answer}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await context.bot.send_message(
        chat_id=chat_id or user_id,
        text=f"السؤال {question_index + 1}: {question_text}",
        reply_markup=reply_markup
    )
    
    state = database.get_user_current_quiz_state(user_id)
    if state:
        database.update_user_quiz_state(state[0], question_index, state[3], message.message_id)

async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user's answer to a quiz question."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # query.data is quiz_answer_quizname_index_answer
    # We need to split carefully as quiz_name might contain underscores
    parts = query.data.split('_')
    # parts[0] = quiz, parts[1] = answer, parts[2] = quiz_name, parts[3] = index, parts[4:] = answer
    # This split logic in the original code was: _, _, quiz_name, question_index_str, chosen_answer = query.data.split('_', 4)
    # Which assumes quiz_name doesn't have underscores. Let's keep it for now as per original.
    _, _, quiz_name, question_index_str, chosen_answer = query.data.split('_', 4)
    question_index = int(question_index_str)

    questions = context.user_data.get("current_quiz_questions")
    if not questions or question_index >= len(questions):
        await query.edit_message_text("عذراً، هذا الاختبار لم يعد متاحاً أو انتهى.")
        return

    question_data = questions[question_index]
    correct_answer = question_data[1]

    state = database.get_user_current_quiz_state(user_id)
    if not state or state[2] != question_index:
        await query.edit_message_text("لقد أجبت بالفعل على هذا السؤال أو أن هذا ليس السؤال الحالي.")
        return

    user_quiz_id, _, _, current_score, message_id, channel_id = state

    if chosen_answer == correct_answer:
        feedback = "صحيح! ✅"
        new_score = current_score + 1
    else:
        feedback = f"خطأ! ❌ الإجابة الصحيحة هي: {correct_answer}"
        new_score = current_score
    
    await query.edit_message_text(
        text=f"{query.message.text}\n\n{feedback}",
        reply_markup=None
    )

    next_question_index = question_index + 1
    database.update_user_quiz_state(user_quiz_id, next_question_index, new_score)

    await asyncio.sleep(2)
    await send_quiz_question(update, context, user_id, quiz_name, next_question_index, chat_id=channel_id)

async def publish_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts the quiz publishing process."""
    user_id = update.effective_user.id
    quizzes = database.get_user_quizzes(user_id)

    if not quizzes:
        await update.message.reply_text("لم تقم بإنشاء أي اختبارات بعد. استخدم /add_quiz لإضافة اختبارات.")
        return

    keyboard = [[InlineKeyboardButton(quiz_name, callback_data=f"publish_quiz_select_{quiz_name}")] for quiz_name in quizzes]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("الرجاء اختيار الاختبار الذي تريد نشره:", reply_markup=reply_markup)

async def publish_quiz_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the selection of a quiz to publish."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    quiz_name = query.data.replace('publish_quiz_select_', '')

    user_quiz_publish_data[user_id] = {"quiz_name": quiz_name}

    await query.edit_message_text(
        "الرجاء إرسال معرف القناة أو المجموعة (Chat ID) حيث تريد نشر الاختبار. "
        "(تأكد أن البوت مشرف في هذه القناة/المجموعة)"
    )
    return QUIZ_PUBLISH_CHANNEL_SELECTION

async def receive_quiz_publish_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the channel ID and publishes the quiz."""
    user_id = update.effective_user.id
    channel_id_str = update.message.text.strip()
    try:
        channel_id = int(channel_id_str)
    except ValueError:
        await update.message.reply_text("معرف القناة/المجموعة غير صالح. الرجاء إدخال رقم صحيح.")
        return QUIZ_PUBLISH_CHANNEL_SELECTION

    quiz_name = user_quiz_publish_data[user_id]["quiz_name"]

    try:
        # Start the quiz in the channel/group
        questions = database.get_quiz_questions(user_id, quiz_name)
        if not questions:
            await update.message.reply_text("عذراً، لا توجد أسئلة لهذا الاختبار.")
            return ConversationHandler.END

        context.user_data["current_quiz_questions"] = questions
        context.user_data["current_quiz_name"] = quiz_name

        database.start_user_quiz(user_id, quiz_name, channel_id=channel_id)

        await send_quiz_question(update, context, user_id, quiz_name, 0, chat_id=channel_id)

        await update.message.reply_text(
            f"تم نشر الاختبار '{quiz_name}' بنجاح في القناة/المجموعة (ID: {channel_id})."
        )

    except Exception as e:
        logger.error(f"Failed to publish quiz {quiz_name} to channel {channel_id}: {e}")
        await update.message.reply_text(
            f"فشل نشر الاختبار في القناة/المجموعة (ID: {channel_id}). يرجى التأكد من أن البوت مشرف ولديه صلاحية نشر الرسائل."
        )
    finally:
        if user_id in user_quiz_publish_data:
            del user_quiz_publish_data[user_id]
    return ConversationHandler.END

async def cancel_quiz_publishing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the quiz publishing process."""
    user_id = update.effective_user.id
    if user_id in user_quiz_publish_data:
        del user_quiz_publish_data[user_id]
    await update.message.reply_text("تم إلغاء نشر الاختبار.")
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    database.init_db()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable not set.")

    application = Application.builder().token(bot_token).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("close_poll", close_poll_command))
    application.add_handler(CommandHandler("add_quiz", add_quiz_command))
    application.add_handler(CommandHandler("my_quizzes", my_quizzes_command))
    application.add_handler(CommandHandler("delete_quiz", delete_quiz_command))
    application.add_handler(CommandHandler("delete_all_quizzes", delete_all_quizzes_command))
    application.add_handler(CommandHandler("start_quiz", start_quiz_command))
    application.add_handler(CommandHandler("publish_quiz", publish_quiz_command))

    # Conversation handler for poll creation
    poll_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create_poll", create_poll_command)],
        states={
            POLL_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_question)],
            POLL_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_options)],
            POLL_CHANNEL_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_poll_channel_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel_poll_creation)],
    )
    application.add_handler(poll_conv_handler)

    # Conversation handler for quiz publishing
    quiz_publish_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(publish_quiz_select_callback, pattern='^publish_quiz_select_')],
        states={
            QUIZ_PUBLISH_CHANNEL_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quiz_publish_channel_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel_quiz_publishing)],
    )
    application.add_handler(quiz_publish_conv_handler)

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(start_quiz_callback, pattern='^start_quiz_'))
    application.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern='^quiz_answer_'))

    # Error handler
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
