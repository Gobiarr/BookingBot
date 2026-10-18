
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def get_services_keyboard(
    services: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []

    for service in services:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{service['name']} — "
                        f"{service['price']} руб."
                    ),
                    callback_data=f"service:{service['id']}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
