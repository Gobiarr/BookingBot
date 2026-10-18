
from datetime import date

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_services_keyboard(
    services: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []

    for service in services:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{service['name']} — {service['price']} руб.",
                    callback_data=f"service:{service['id']}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_dates_keyboard(
    dates: list[str],
) -> InlineKeyboardMarkup:
    buttons = []

    for date_string in dates:
        selected_date = date.fromisoformat(date_string)
        weekday = WEEKDAYS[selected_date.weekday()]

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{weekday}, "
                        f"{selected_date.strftime('%d.%m.%Y')}"
                    ),
                    callback_data=f"date:{date_string}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_slots_keyboard(
    slots: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []

    for slot in slots:
        start_time = slot["starts_at"][11:16]
        end_time = slot["ends_at"][11:16]

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🕒 {start_time}–{end_time}",
                    callback_data=f"slot:{slot['id']}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить запись",
                    callback_data="booking:confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="booking:cancel",
                )
            ],
        ]
    )


def get_bookings_keyboard(
    bookings: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []

    for booking in bookings:
        starts_at = booking["starts_at"]
        date_text = starts_at[:10]
        time_text = starts_at[11:16]

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"❌ #{booking['booking_id']} — "
                        f"{date_text} {time_text}"
                    ),
                    callback_data=f"cancel_booking:{booking['booking_id']}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
