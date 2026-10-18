
from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    entering_name = State()
    entering_phone = State()
    choosing_date = State()
    choosing_slot = State()
    confirming_booking = State()
