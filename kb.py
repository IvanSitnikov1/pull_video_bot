from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

archive_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Архив')]],
    resize_keyboard=True,
)
