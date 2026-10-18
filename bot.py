
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN
from database.db import init_db, get_active_services
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
    if not message.text:
        return

    if message.text == "📋 Услуги":
        services = await get_active_services()

        if not services:
            await message.answer("Пока нет доступных услуг.")
            return

        response = "📋 Наши услуги\n\n"

        for service in services:
            response += (
                f"✂️ {service['name']}\n"
                f"💬 {service['description']}\n"
                f"💰 Цена: {service['price']} руб.\n"
                f"⏱ Длительность: "
                f"{service['duration_minutes']} мин.\n\n"
            )

        await message.answer(response)

    elif message.text == "📅 Записаться":
        await message.answer(
            "📅 Скоро здесь можно будет выбрать услугу и время."
        )

    elif message.text == "🗓 Мои записи":
        await message.answer(
            "🗓 Здесь будут отображаться твои записи."
        )

    elif message.text == "❌ Отменить запись":
        await message.answer(
            "❌ Здесь можно будет отменить своё бронирование."
        )

    else:
        await message.answer(
            "Пожалуйста, выбери действие с помощью кнопок меню."
        )


async def main() -> None:
    logging.info("BookingBot запускается...")

    try:
        await init_db()
        logging.info("База данных готова.")

        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        logging.info("BookingBot остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
