
import asyncio
import logging

from datetime import date, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import BOT_TOKEN
from database.db import (
    init_db,
    get_active_services,
    get_available_dates,
    get_available_slots,
    create_booking,
)
from keyboards.main_menu import get_main_menu
from keyboards.booking import (
    get_services_keyboard,
    get_dates_keyboard,
    get_slots_keyboard,
    get_confirmation_keyboard,
)
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
            "Сейчас нет активного действия для отмены.",
            reply_markup=get_main_menu(),
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

    await state.clear()
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
        await callback.answer("Некорректная услуга.", show_alert=True)
        return

    services = await get_active_services()
    selected_service = next(
        (
            service for service in services
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
        await message.answer("Пожалуйста, введи телефон текстом.")
        return

    phone = message.text.strip()
    digits = "".join(char for char in phone if char.isdigit())

    if len(digits) < 7 or len(digits) > 15:
        await message.answer(
            "Введи номер, содержащий от 7 до 15 цифр."
        )
        return

    await state.update_data(client_phone=phone)

    dates = await get_available_dates()

    if not dates:
        await state.clear()
        await message.answer(
            "К сожалению, свободного времени пока нет.",
            reply_markup=get_main_menu(),
        )
        return

    await state.set_state(BookingStates.choosing_date)

    await message.answer(
        "📆 Выбери дату записи:",
        reply_markup=get_dates_keyboard(dates),
    )


@dp.callback_query(
    BookingStates.choosing_date,
    F.data.startswith("date:"),
)
async def choose_date(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.data or callback.message is None:
        await callback.answer()
        return

    booking_date = callback.data.split(":", 1)[1]

    try:
        date.fromisoformat(booking_date)
    except ValueError:
        await callback.answer("Некорректная дата.", show_alert=True)
        return

    slots = await get_available_slots(booking_date)

    if not slots:
        await callback.answer(
            "На эту дату свободного времени нет.",
            show_alert=True,
        )
        await callback.message.answer(
            "Выбери другую дату:",
            reply_markup=get_dates_keyboard(
                await get_available_dates()
            ),
        )
        return

    await state.update_data(booking_date=booking_date)
    await state.set_state(BookingStates.choosing_slot)

    await callback.answer()
    await callback.message.answer(
        f"📆 Дата: {datetime.strptime(booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n\n"
        "Выбери свободное время:",
        reply_markup=get_slots_keyboard(slots),
    )


@dp.callback_query(
    BookingStates.choosing_slot,
    F.data.startswith("slot:"),
)
async def choose_slot(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not callback.data or callback.message is None:
        await callback.answer()
        return

    try:
        slot_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректное время.", show_alert=True)
        return

    data = await state.get_data()
    booking_date = data.get("booking_date")

    if not booking_date:
        await callback.answer(
            "Сначала выбери дату заново.",
            show_alert=True,
        )
        return

    slots = await get_available_slots(booking_date)
    selected_slot = next(
        (slot for slot in slots if slot["id"] == slot_id),
        None,
    )

    if selected_slot is None:
        await callback.answer(
            "Это время уже занято. Выбери другое.",
            show_alert=True,
        )
        await callback.message.answer(
            "Свободное время на выбранную дату:",
            reply_markup=get_slots_keyboard(slots),
        )
        return

    await state.update_data(
        slot_id=selected_slot["id"],
        slot_start=selected_slot["starts_at"],
        slot_end=selected_slot["ends_at"],
    )
    await state.set_state(BookingStates.confirming_booking)

    await callback.answer()

    await callback.message.answer(
        "📝 Проверь данные перед подтверждением:\n\n"
        f"Услуга: {data['service_name']}\n"
        f"Цена: {data['service_price']} руб.\n"
        f"Имя: {data['client_name']}\n"
        f"Телефон: {data['client_phone']}\n"
        f"Дата: {selected_slot['starts_at'][:10]}\n"
        f"Время: {selected_slot['starts_at'][11:16]}–"
        f"{selected_slot['ends_at'][11:16]}\n\n"
        "Подтвердить запись?",
        reply_markup=get_confirmation_keyboard(),
    )


@dp.callback_query(
    BookingStates.confirming_booking,
    F.data == "booking:confirm",
)
async def confirm_booking(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    data = await state.get_data()

    required_fields = (
        "service_id",
        "slot_id",
        "client_name",
        "client_phone",
    )

    if any(data.get(field) is None for field in required_fields):
        await state.clear()
        await callback.answer(
            "Данные записи потеряны. Начни заново.",
            show_alert=True,
        )
        return

    user = callback.from_user

    booking_id = await create_booking(
        user_id=user.id,
        username=user.username,
        telegram_full_name=user.full_name,
        service_id=data["service_id"],
        slot_id=data["slot_id"],
        client_name=data["client_name"],
        phone=data["client_phone"],
    )

    await callback.answer()

    if booking_id is None:
        await state.clear()
        await callback.message.answer(
            "⚠️ Не удалось создать запись: выбранное время "
            "уже занято или услуга недоступна.\n\n"
            "Начни запись заново и выбери другое время.",
            reply_markup=get_main_menu(),
        )
        return

    await state.clear()

    await callback.message.answer(
        "✅ Запись успешно создана!\n\n"
        f"Номер записи: #{booking_id}\n"
        f"Услуга: {data['service_name']}\n"
        f"Дата: {data['slot_start'][:10]}\n"
        f"Время: {data['slot_start'][11:16]}–"
        f"{data['slot_end'][11:16]}\n"
        f"Имя: {data['client_name']}\n"
        f"Телефон: {data['client_phone']}\n\n"
        "Спасибо за запись! 😊",
        reply_markup=get_main_menu(),
    )


@dp.callback_query(
    BookingStates.confirming_booking,
    F.data == "booking:cancel",
)
async def cancel_confirmation(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.answer("Запись отменена.")

    if callback.message is not None:
        await callback.message.answer(
            "Запись не создана. Можешь начать заново.",
            reply_markup=get_main_menu(),
        )


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
        logging.info("База данных и расписание готовы.")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logging.info("BookingBot остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
