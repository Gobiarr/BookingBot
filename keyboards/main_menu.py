
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Услуги"),
                KeyboardButton(text="📅 Записаться"),
            ],
            [
                KeyboardButton(text="🗓 Мои записи"),
                KeyboardButton(text="❌ Отменить запись"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )

    return keyboard
