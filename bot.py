import asyncio
import os
import re
import logging

from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from pytube import YouTube
from pytube.exceptions import VideoUnavailable
import yadisk
from yadisk.exceptions import BadRequestError
import gspread

from config import TELEGRAM_TOKEN, YANDEX_DISK_TOKEN
from utils import send_video_from_archive
import kb

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
# Объект бота
bot = Bot(token=TELEGRAM_TOKEN)
# Диспетчер
dp = Dispatcher()
# инициализация объектов для работы с Яндекс Диск и Google Sheets
yd = yadisk.AsyncClient(token=YANDEX_DISK_TOKEN)
gc = gspread.service_account(filename='credentials.json')
wks = gc.open("video_storage").sheet1

# добавляем данные из таблицы в локальное хранилище
archive = wks.get_all_values()[1:]


# Хэндлер на команду /start
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer('Привет! Пришли мне ссылку на видео с YouTube',
                         reply_markup=kb.archive_kb)


# Хэндлер на команду /help
@dp.message(Command('help'))
async def cmd_help(message: types.Message):
    await message.answer('Привет! Этот бот принимает ссылки на видео с YouTube'
                         ' и возвращает файл для скачивания видео')


# Обработчик текстовых сообщений
@dp.message(F.text)
async def text_massage_handler(message: types.Message):
    if re.match(r'https?://(?:www.youtube.com|youtu.be)/.*', message.text):
        try:
            # скачивание видео и отправка пользователю
            if message.text in wks.col_values(3):
                # отправка повторяющегося видео из гугл таблиц
                await message.answer_document(send_video_from_archive(wks, message.text))
                await message.answer(f'Видео уже есть в архиве')
            else:
                # инициализация объекта видео
                yt = YouTube(message.text)
                # скачивание видео и отправка пользователю
                download_video_path = (yt.streams.get_highest_resolution()
                                       .download())

                video_file = types.FSInputFile(download_video_path)
                video_name = os.path.basename(download_video_path)
                await message.answer_document(video_file)
                await message.answer(f'Видео {video_name} успешно загружено')

                # загрузка видео на Яндекс Диск
                await yd.upload(
                    download_video_path,
                    f'/video_storage/{video_name}',
                    overwrite=True,
                    timeout=60,
                )

                # удаление скачанного файла
                os.remove(download_video_path)

                # сохранение данных в гугл таблицу
                link_yd = await yd.get_download_link(f'/video_storage/{video_name}')
                new_row = [yt.title, yt.author, message.text, link_yd]
                wks.append_row(new_row)
                archive.append(new_row)
                await message.answer(f'Видео {video_name} добавлено в архив')
        except (VideoUnavailable, BadRequestError) as e:
            logging.error(f'Ошибка при обработке ссылки: {e}')
            await message.answer('Произошла ошибка при обработке ссылки. '
                                 'Пожалуйста, попробуйте еще раз.')
    elif message.text == 'Архив':
        # проходимся по архиву и строим инлайн-клавиатуру
        buttons_video = []
        for i, el in enumerate(archive):
            button_video = types.InlineKeyboardButton(
                text=f'{el[0]} - {el[1]}',
                callback_data=f'button_video_{i}',
            )
            buttons_video.append([button_video])

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=buttons_video
        )
        await message.answer(text='Доступные видео из архива:',
                             reply_markup=keyboard)
    else:
        await message.answer('Некорректная ссылка!!!')


# обработчик нажатия инлайн-кнопки видео из архива
@dp.callback_query(lambda c: c.data and c.data.startswith('button_video_'))
async def process_button_video(callback: types.CallbackQuery):
    # строим клавиатуру для просмотра и скачивания видео
    index_video = callback.data.split('_')[-1]

    button_view = types.InlineKeyboardButton(
        text='Смотреть YouTube',
        callback_data=f'button_view_{index_video}',
    )
    button_download = types.InlineKeyboardButton(
        text='Скачать',
        callback_data=f'button_download_{index_video}',
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[button_view], [button_download]]
    )

    await callback.message.answer("Выберите действие:", reply_markup=keyboard)
    await callback.answer()


# обработчик нажатия инлайн-кнопки 'смотреть видео'
@dp.callback_query(lambda c: c.data and c.data.startswith('button_view_'))
async def process_button_view(callback: types.CallbackQuery):
    index_video = int(callback.data.split('_')[-1])

    await callback.message.answer(archive[index_video][2])
    await callback.answer()


# обработчик нажатия инлайн-кнопки 'скачать'
@dp.callback_query(lambda c: c.data and c.data.startswith('button_download_'))
async def process_button_download(callback: types.CallbackQuery):
    index_video = int(callback.data.split('_')[-1])

    await callback.message.answer_document(archive[index_video][3])
    await callback.answer()


# Обработчик сообщений, отличных от текстовых
@dp.message()
async def error(message: types.Message):
    await message.answer('Введите ссылку на видео!!!')


# Запуск процесса пуллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
