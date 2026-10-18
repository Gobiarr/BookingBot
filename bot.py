
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
)
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN
from database.db import init_db, get_active_services
from keyboards.main_menu import get_main_menu
from keyboards.booking import get_services_keyboard
from states.booking import BookingStates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Привет! 👋\n\n"
        "Я BookingBot — бот для записи клиентов на услуги.\n\n"
        "Выбери действие в меню ниже.",
        reply_markup=get_main_menu(),
    )


@dp.message(Command("cancel"))
async def cancel_booking(
    message: Message,
    state: FSMContext,
) -> None:
    current_state = await state.get_state()

    if current_state is None:
        await message.answer(
            "Сейчас нет активного действия для отмены."
        )
        return

    await state.clear()

    await message.answer(
        "Действие отменено. Можешь начать заново.",
        reply_markup=get_main_menu(),
    )


@dp.message(F.text == "📋 Услуги")
async def show_services(message: Message) -> None:
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


@dp.message(F.text == "📅 Записаться")
async def start_booking(
    message: Message,
    state: FSMContext,
) -> None:
    services = await get_active_services()

    if not services:
        await message.answer("Сейчас нет доступных услуг.")
        return

    await state.set_state(BookingStates.choosing_service)

    await message.answer(
        "📅 Выбери услугу для записи:",
        reply_markup=get_services_keyboard(services),
    )


@dp.callback_query(
    BookingStates.choosing_service,
    F.data.startswith("service:"),
)
async def choose_service(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.data or callback.message is None:
        await callback.answer()
        return

    try:
        service_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer(
            "Некорректная услуга.",
            show_alert=True,
        )
        return

    services = await get_active_services()
    selected_service = next(
        (
            service
            for service in services
            if service["id"] == service_id
        ),
        None,
    )

    if selected_service is None:
        await callback.answer(
            "Эта услуга больше недоступна.",
            show_alert=True,
        )
        return

    await state.update_data(
        service_id=selected_service["id"],
        service_name=selected_service["name"],
        service_price=selected_service["price"],
        service_duration=selected_service["duration_minutes"],
    )

    await state.set_state(BookingStates.entering_name)

    await callback.answer()

    await callback.message.answer(
        f"Выбрана услуга: {selected_service['name']}.\n"
        f"Стоимость: {selected_service['price']} руб.\n\n"
        "Как тебя зовут? Введи имя."
    )


@dp.message(BookingStates.entering_name)
async def enter_name(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введи имя текстом.")
        return

    name = message.text.strip()

    if len(name) < 2 or len(name) > 100:
        await message.answer(
            "Имя должно содержать от 2 до 100 символов."
        )
        return

    await state.update_data(client_name=name)

    await state.set_state(BookingStates.entering_phone)

    await message.answer(
        "Спасибо! Теперь введи контактный телефон."
    )


@dp.message(BookingStates.entering_phone)
async def enter_phone(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer(
            "Пожалуйста, введи телефон текстом."
        )
        return

    phone = message.text.strip()
    digits = "".join(char for char in phone if char.isdigit())

    if len(digits) < 7 or len(digits) > 15:
        await message.answer(
            "Не удалось распознать телефон. "
            "Введи номер, содержащий от 7 до 15 цифр."
        )
        return

    await state.update_data(client_phone=phone)

    data = await state.get_data()

    await message.answer(
        "Контактные данные получены! ✅\n\n"
        f"Имя: {data['client_name']}\n"
        f"Телефон: {data['client_phone']}\n"
        f"Услуга: {data['service_name']}\n\n"
        "Следующим этапом добавим выбор даты и времени.\n"
        "Запись пока не создана."
    )

    await state.clear()


@dp.message()
async def handle_unknown_message(message: Message) -> None:
    await message.answer(
        "Выбери действие с помощью кнопок меню "
        "или используй /cancel для отмены текущего действия.",
        reply_markup=get_main_menu(),
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
