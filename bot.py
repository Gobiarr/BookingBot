
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN
from keyboards.main_menu import get_main_menu


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! 👋\n\n"
        "Я BookingBot — бот для записи клиентов на услуги.\n\n"
        "Выбери действие в меню ниже.",
        reply_markup=get_main_menu(),
    )


@dp.message()
async def handle_menu(message: Message) -> None:
    if message.text == "📋 Услуги":
        await message.answer("📋 Раздел услуг. Скоро здесь появится список услуг.")

    elif message.text == "📅 Записаться":
        await message.answer("📅 Начнём запись на услугу на следующем этапе.")

    elif message.text == "🗓 Мои записи":
        await message.answer("🗓 Здесь будут отображаться твои записи.")

    elif message.text == "❌ Отменить запись":
        await message.answer("❌ Здесь можно будет отменить свою запись.")

    else:
        await message.answer(
            "Пожалуйста, выбери действие с помощью кнопок меню."
        )


async def main() -> None:
    logging.info("BookingBot запускается...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logging.info("BookingBot остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
