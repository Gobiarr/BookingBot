
from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    entering_name = State()
    entering_phone = State()
    choosing_date = State()
    choosing_slot = State()
    confirming_booking = State()


class AdminServiceStates(StatesGroup):
    entering_service_name = State()
    entering_service_description = State()
    entering_service_price = State()
    entering_service_duration = State()

    choosing_service_to_edit = State()
    entering_new_price = State()
