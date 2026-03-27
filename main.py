from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os
from ai import ask_ai
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply("🤖 بوت AI جاهز! اكتب أي شيء")

@dp.message_handler()
async def chat(message: types.Message):
    try:
        reply = ask_ai(message.text)
        await message.reply(reply)
    except Exception as e:
        await message.reply(f"خطأ: {e}")

if __name__ == "__main__":
    executor.start_polling(dp)
