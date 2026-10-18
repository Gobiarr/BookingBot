
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import BOT_TOKEN, ADMIN_ID
from database.db import (
    init_db,
    get_active_services,
    get_all_services,
    add_service,
    update_service_price,
    set_service_active,
    get_available_dates,
    get_available_slots,
    create_booking,
    get_user_bookings,
    get_cancellable_bookings,
    cancel_user_booking,
    get_all_upcoming_bookings,
)
from keyboards.main_menu import get_main_menu
from keyboards.booking import (
    get_services_keyboard,
    get_dates_keyboard,
    get_slots_keyboard,
    get_confirmation_keyboard,
    get_bookings_keyboard,
)
from states.booking import BookingStates, AdminServiceStates


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить услугу",
                    callback_data="admin:add_service",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Управление услугами",
                    callback_data="admin:manage_services",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Все предстоящие записи",
                    callback_data="admin:bookings",
                )
            ],
        ]
    )


def get_admin_services_keyboard(
    services: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []

    for service in services:
        status = "🟢" if service["is_active"] else "🔴"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{status} {service['name']} "
                        f"— {service['price']} руб."
                    ),
                    callback_data=f"admin:service:{service['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 В админ-панель",
                callback_data="admin:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_service_edit_keyboard(
    service: dict,
) -> InlineKeyboardMarkup:
    if service["is_active"]:
        toggle_text = "🔴 Отключить услугу"
    else:
        toggle_text = "🟢 Включить услугу"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Изменить цену",
                    callback_data=f"admin:price:{service['id']}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin:toggle:{service['id']}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 К списку услуг",
                    callback_data="admin:manage_services",
                )
            ],
        ]
    )


def is_admin(user_id: int) -> bool:
    return ADMIN_ID > 0 and user_id == ADMIN_ID


async def show_admin_menu(message: Message) -> None:
    await message.answer(
        "🛠 Админ-панель\n\nВыбери действие:",
        reply_markup=get_admin_menu(),
    )


@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Привет! 👋\n\n"
        "Добро пожаловать в BookingBot.\n"
        "Здесь ты можешь посмотреть услуги и записаться "
        "на удобное время.",
        reply_markup=get_main_menu(),
    )


@dp.message(Command("cancel"))
async def cancel_handler(
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
        "❌ Текущее действие отменено.",
        reply_markup=get_main_menu(),
    )


@dp.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return

    await show_admin_menu(message)


@dp.callback_query(F.data == "admin:menu")
async def admin_menu_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "🛠 Админ-панель\n\nВыбери действие:",
        reply_markup=get_admin_menu(),
    )


@dp.callback_query(F.data == "admin:add_service")
async def admin_add_service_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminServiceStates.entering_service_name)

    await callback.answer()
    await callback.message.answer(
        "Напиши название новой услуги:"
    )


@dp.message(AdminServiceStates.entering_service_name)
async def admin_service_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text or not message.text.strip():
        await message.answer("Напиши название услуги текстом.")
        return

    await state.update_data(service_name=message.text.strip())
    await state.set_state(
        AdminServiceStates.entering_service_description
    )

    await message.answer(
        "Напиши описание услуги.\n\n"
        "Если описание не нужно, отправь дефис: -"
    )


@dp.message(AdminServiceStates.entering_service_description)
async def admin_service_description_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text:
        await message.answer("Отправь описание текстом или дефис.")
        return

    description = message.text.strip()

    if description == "-":
        description = ""

    await state.update_data(service_description=description)
    await state.set_state(AdminServiceStates.entering_service_price)

    await message.answer("Укажи цену услуги в рублях, целым числом.")


@dp.message(AdminServiceStates.entering_service_price)
async def admin_service_price_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "Цена должна быть целым неотрицательным числом."
        )
        return

    await state.update_data(service_price=int(message.text))
    await state.set_state(
        AdminServiceStates.entering_service_duration
    )

    await message.answer(
        "Укажи длительность услуги в минутах, целым положительным числом."
    )


@dp.message(AdminServiceStates.entering_service_duration)
async def admin_service_duration_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if (
        not message.text
        or not message.text.isdigit()
        or int(message.text) <= 0
    ):
        await message.answer(
            "Длительность должна быть положительным числом минут."
        )
        return

    data = await state.get_data()

    service_id = await add_service(
        name=data["service_name"],
        description=data["service_description"],
        price=data["service_price"],
        duration_minutes=int(message.text),
    )

    await state.clear()

    if service_id is None:
        await message.answer(
            "⚠️ Не удалось добавить услугу. "
            "Возможно, услуга с таким названием уже существует.",
            reply_markup=get_main_menu(),
        )
        return

    await message.answer(
        f"✅ Услуга «{data['service_name']}» добавлена!\n"
        f"Цена: {data['service_price']} руб.\n"
        f"Длительность: {int(message.text)} мин.",
        reply_markup=get_main_menu(),
    )

    await show_admin_menu(message)


@dp.callback_query(F.data == "admin:manage_services")
async def admin_manage_services_callback(
    callback: CallbackQuery,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    services = await get_all_services()

    await callback.answer()

    if not services:
        await callback.message.answer("Услуг пока нет.")
        return

    await callback.message.answer(
        "💰 Управление услугами\n\n"
        "🟢 — услуга активна\n"
        "🔴 — услуга отключена\n\n"
        "Выбери услугу:",
        reply_markup=get_admin_services_keyboard(services),
    )


@dp.callback_query(F.data.startswith("admin:service:"))
async def admin_select_service_callback(
    callback: CallbackQuery,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        service_id = int(callback.data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID услуги.", show_alert=True)
        return

    services = await get_all_services()
    service = next(
        (item for item in services if item["id"] == service_id),
        None,
    )

    if service is None:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return

    status = "активна" if service["is_active"] else "отключена"

    await callback.answer()
    await callback.message.answer(
        f"Услуга: {service['name']}\n"
        f"Описание: {service['description'] or 'не указано'}\n"
        f"Цена: {service['price']} руб.\n"
        f"Длительность: {service['duration_minutes']} мин.\n"
        f"Статус: {status}",
        reply_markup=get_service_edit_keyboard(service),
    )


@dp.callback_query(F.data.startswith("admin:price:"))
async def admin_change_price_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        service_id = int(callback.data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID услуги.", show_alert=True)
        return

    services = await get_all_services()
    service = next(
        (item for item in services if item["id"] == service_id),
        None,
    )

    if service is None:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return

    await state.clear()
    await state.update_data(editing_service_id=service_id)
    await state.set_state(AdminServiceStates.entering_new_price)

    await callback.answer()
    await callback.message.answer(
        f"Текущая цена услуги «{service['name']}»: "
        f"{service['price']} руб.\n\n"
        "Введи новую цену целым неотрицательным числом."
    )


@dp.message(AdminServiceStates.entering_new_price)
async def admin_new_price_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "Цена должна быть целым неотрицательным числом. "
            "Попробуй ещё раз."
        )
        return

    data = await state.get_data()
    service_id = data.get("editing_service_id")

    if service_id is None:
        await state.clear()
        await message.answer(
            "Не удалось определить услугу. Начни заново через /admin."
        )
        return

    changed = await update_service_price(
        service_id=service_id,
        new_price=int(message.text),
    )

    await state.clear()

    if not changed:
        await message.answer("Не удалось изменить цену услуги.")
        return

    await message.answer(
        f"✅ Цена успешно изменена на {int(message.text)} руб."
    )

    services = await get_all_services()
    service = next(
        (item for item in services if item["id"] == service_id),
        None,
    )

    if service is not None:
        await message.answer(
            f"Услуга: {service['name']}\n"
            f"Цена: {service['price']} руб.\n"
            f"Статус: {'активна' if service['is_active'] else 'отключена'}",
            reply_markup=get_service_edit_keyboard(service),
        )


@dp.callback_query(F.data.startswith("admin:toggle:"))
async def admin_toggle_service_callback(
    callback: CallbackQuery,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        service_id = int(callback.data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный ID услуги.", show_alert=True)
        return

    services = await get_all_services()
    service = next(
        (item for item in services if item["id"] == service_id),
        None,
    )

    if service is None:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return

    new_status = not bool(service["is_active"])

    changed = await set_service_active(
        service_id=service_id,
        is_active=new_status,
    )

    if not changed:
        await callback.answer("Не удалось изменить статус.", show_alert=True)
        return

    await callback.answer(
        "Услуга включена." if new_status else "Услуга отключена."
    )

    service["is_active"] = int(new_status)

    await callback.message.answer(
        f"Услуга «{service['name']}» теперь "
        f"{'активна' if new_status else 'отключена'}.",
        reply_markup=get_service_edit_keyboard(service),
    )


@dp.callback_query(F.data == "admin:bookings")
async def admin_bookings_callback(
    callback: CallbackQuery,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    bookings = await get_all_upcoming_bookings()
    await callback.answer()

    if not bookings:
        await callback.message.answer("Предстоящих записей пока нет.")
        return

    lines = ["📅 Предстоящие записи:\n"]

    for booking in bookings:
        lines.append(
            f"Запись #{booking['booking_id']}\n"
            f"Клиент: {booking['client_name']}\n"
            f"Телефон: {booking['phone']}\n"
            f"Услуга: {booking['service_name']}\n"
            f"Дата и время: {booking['starts_at']}\n"
            f"Цена: {booking['price']} руб.\n"
        )

    text = "\n".join(lines)

    for start in range(0, len(text), 4000):
        await callback.message.answer(text[start:start + 4000])


@dp.message(Command("all_bookings"))
async def all_bookings_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа.")
        return

    bookings = await get_all_upcoming_bookings()

    if not bookings:
        await message.answer("Предстоящих записей пока нет.")
        return

    lines = ["📅 Предстоящие записи:\n"]

    for booking in bookings:
        lines.append(
            f"Запись #{booking['booking_id']}\n"
            f"Клиент: {booking['client_name']}\n"
            f"Телефон: {booking['phone']}\n"
            f"Услуга: {booking['service_name']}\n"
            f"Дата и время: {booking['starts_at']}\n"
            f"Цена: {booking['price']} руб.\n"
        )

    text = "\n".join(lines)

    for start in range(0, len(text), 4000):
        await message.answer(text[start:start + 4000])


@dp.message(F.text == "📋 Услуги")
async def services_handler(message: Message) -> None:
    services = await get_active_services()

    if not services:
        await message.answer("Сейчас активных услуг нет.")
        return

    lines = ["📋 Наши услуги:\n"]

    for service in services:
        lines.append(
            f"✂️ {service['name']}\n"
            f"Описание: {service['description'] or 'не указано'}\n"
            f"Цена: {service['price']} руб.\n"
            f"Длительность: {service['duration_minutes']} мин.\n"
        )

    await message.answer("\n".join(lines))


@dp.message(F.text == "📅 Записаться")
async def booking_start_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    services = await get_active_services()

    if not services:
        await message.answer("Сейчас нет доступных услуг.")
        return

    await state.set_state(BookingStates.choosing_service)

    await message.answer(
        "Выбери услугу для записи:",
        reply_markup=get_services_keyboard(services),
    )


@dp.callback_query(
    BookingStates.choosing_service,
    F.data.startswith("service:"),
)
async def service_selected_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    try:
        service_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректная услуга.", show_alert=True)
        return

    services = await get_active_services()
    service = next(
        (item for item in services if item["id"] == service_id),
        None,
    )

    if service is None:
        await callback.answer(
            "Эта услуга больше недоступна.",
            show_alert=True,
        )
        await state.clear()
        return

    await state.update_data(service_id=service_id)
    await state.set_state(BookingStates.entering_name)

    await callback.answer()
    await callback.message.answer(
        f"Ты выбрал услугу «{service['name']}».\n\n"
        "Напиши своё имя:"
    )


@dp.message(BookingStates.entering_name)
async def booking_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введи имя текстом.")
        return

    await state.update_data(client_name=message.text.strip())
    await state.set_state(BookingStates.entering_phone)

    await message.answer("Теперь введи номер телефона для связи:")


@dp.message(BookingStates.entering_phone)
async def booking_phone_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введи номер телефона текстом.")
        return

    phone = message.text.strip()

    if len(phone) < 5:
        await message.answer("Номер выглядит слишком коротким. Попробуй ещё раз.")
        return

    await state.update_data(phone=phone)

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
        "Выбери дату записи:",
        reply_markup=get_dates_keyboard(dates),
    )


@dp.callback_query(
    BookingStates.choosing_date,
    F.data.startswith("date:"),
)
async def booking_date_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    booking_date = callback.data.split(":", 1)[1]

    available_dates = await get_available_dates()

    if booking_date not in available_dates:
        await callback.answer(
            "На эту дату больше нет свободного времени.",
            show_alert=True,
        )
        return

    slots = await get_available_slots(booking_date)

    if not slots:
        await callback.answer(
            "Свободного времени на эту дату нет.",
            show_alert=True,
        )
        return

    await state.update_data(booking_date=booking_date)
    await state.set_state(BookingStates.choosing_slot)

    await callback.answer()
    await callback.message.answer(
        "Выбери свободное время:",
        reply_markup=get_slots_keyboard(slots),
    )


@dp.callback_query(
    BookingStates.choosing_slot,
    F.data.startswith("slot:"),
)
async def booking_slot_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    try:
        slot_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректное время.", show_alert=True)
        return

    data = await state.get_data()
    booking_date = data.get("booking_date")

    slots = await get_available_slots(booking_date or "")
    slot = next(
        (item for item in slots if item["id"] == slot_id),
        None,
    )

    if slot is None:
        await callback.answer(
            "Это время уже занято. Выбери другое.",
            show_alert=True,
        )
        return

    await state.update_data(slot_id=slot_id)
    await state.set_state(BookingStates.confirming_booking)

    services = await get_active_services()
    service = next(
        (
            item for item in services
            if item["id"] == data.get("service_id")
        ),
        None,
    )

    if service is None:
        await state.clear()
        await callback.answer(
            "Услуга больше недоступна.",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.answer(
        "Проверь данные перед подтверждением:\n\n"
        f"Услуга: {service['name']}\n"
        f"Цена: {service['price']} руб.\n"
        f"Имя: {data.get('client_name', '')}\n"
        f"Телефон: {data.get('phone', '')}\n"
        f"Дата: {slot['starts_at'][:10]}\n"
        f"Время: {slot['starts_at'][11:16]}–"
        f"{slot['ends_at'][11:16]}\n\n"
        "Подтвердить запись?",
        reply_markup=get_confirmation_keyboard(),
    )


@dp.callback_query(
    BookingStates.confirming_booking,
    F.data == "booking:confirm",
)
async def booking_confirm_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if not all(
        key in data
        for key in (
            "service_id",
            "slot_id",
            "client_name",
            "phone",
        )
    ):
        await state.clear()
        await callback.answer(
            "Данные записи потеряны. Начни заново.",
            show_alert=True,
        )
        return

    booking_id = await create_booking(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        telegram_full_name=callback.from_user.full_name,
        service_id=data["service_id"],
        slot_id=data["slot_id"],
        client_name=data["client_name"],
        phone=data["phone"],
    )

    await state.clear()
    await callback.answer()

    if booking_id is None:
        await callback.message.answer(
            "⚠️ Не удалось создать запись: возможно, время уже занято "
            "или услуга больше недоступна.\n"
            "Попробуй записаться ещё раз.",
            reply_markup=get_main_menu(),
        )
        return

    await callback.message.answer(
        f"✅ Запись #{booking_id} подтверждена!\n\n"
        f"Имя: {data['client_name']}\n"
        f"Телефон: {data['phone']}\n\n"
        "Спасибо за запись!",
        reply_markup=get_main_menu(),
    )

    if ADMIN_ID > 0:
        try:
            bookings = await get_all_upcoming_bookings()
            booking = next(
                (
                    item for item in bookings
                    if item["booking_id"] == booking_id
                ),
                None,
            )

            if booking:
                await bot.send_message(
                    ADMIN_ID,
                    "🔔 Новая запись!\n\n"
                    f"Номер: #{booking['booking_id']}\n"
                    f"Клиент: {booking['client_name']}\n"
                    f"Телефон: {booking['phone']}\n"
                    f"Услуга: {booking['service_name']}\n"
                    f"Дата и время: {booking['starts_at']}\n"
                    f"Цена: {booking['price']} руб.",
                )
        except Exception:
            pass


@dp.callback_query(
    BookingStates.confirming_booking,
    F.data == "booking:cancel",
)
async def booking_cancel_confirmation_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "❌ Запись не создана.",
        reply_markup=get_main_menu(),
    )


@dp.message(F.text == "🗓 Мои записи")
async def my_bookings_handler(message: Message) -> None:
    bookings = await get_user_bookings(message.from_user.id)

    if not bookings:
        await message.answer("У тебя пока нет предстоящих записей.")
        return

    lines = ["🗓 Твои предстоящие записи:\n"]

    for booking in bookings:
        lines.append(
            f"Запись #{booking['booking_id']}\n"
            f"Услуга: {booking['service_name']}\n"
            f"Дата и время: {booking['starts_at']}\n"
            f"Цена: {booking['price']} руб.\n"
        )

    await message.answer("\n".join(lines))


@dp.message(F.text == "❌ Отменить запись")
async def cancel_booking_start_handler(message: Message) -> None:
    bookings = await get_cancellable_bookings(message.from_user.id)

    if not bookings:
        await message.answer("У тебя нет записей, доступных для отмены.")
        return

    await message.answer(
        "Выбери запись, которую хочешь отменить:",
        reply_markup=get_bookings_keyboard(bookings),
    )


@dp.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking_callback(
    callback: CallbackQuery,
) -> None:
    try:
        booking_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный номер записи.", show_alert=True)
        return

    cancelled = await cancel_user_booking(
        booking_id=booking_id,
        user_id=callback.from_user.id,
    )

    await callback.answer()

    if cancelled:
        await callback.message.answer(
            f"✅ Запись #{booking_id} отменена. "
            "Это время снова доступно для записи."
        )
    else:
        await callback.message.answer(
            "Не удалось отменить запись. Возможно, она уже отменена "
            "или больше недоступна для отмены."
        )


@dp.message(StateFilter(None))
async def unknown_message_handler(message: Message) -> None:
    await message.answer(
        "Выбери действие с помощью кнопок меню "
        "или используй команду /start.",
        reply_markup=get_main_menu(),
    )


async def main() -> None:
    await init_db()

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
