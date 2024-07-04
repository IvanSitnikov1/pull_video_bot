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


# Хэндлер на команду /start
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer('Привет! Пришли мне ссылку на видео с YouTube')


# Хэндлер на команду /help
@dp.message(Command('help'))
async def cmd_help(message: types.Message):
    await message.answer('Привет! Этот бот принимает ссылки на видео с YouTube'
                         ' и возвращает файл для скачивания видео')


# Обработчик текстовых сообщений
@dp.message(F.text)
async def link_processing(message: types.Message):
    if re.match(r'https?://(?:www.youtube.com|youtu.be)/.*', message.text):
        try:
            # скачивание видео и отправка пользователю
            if message.text in wks.col_values(3):
                # отправка повторяющегося видео из гугл таблиц
                row_index = wks.col_values(3).index(message.text) + 1
                download_video_link = wks.row_values(row_index)[3]
                await message.answer_document(download_video_link)
                await message.answer(f'Видео уже есть в архиве')
            else:
                # инициализация объекта видео
                yt = YouTube(message.text)
                # скачивание видео и отправка пользователю
                download_video_path = (yt.streams.get_highest_resolution()
                                       .download())
                video_name = os.path.basename(download_video_path)
                video_file = types.FSInputFile(download_video_path)

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
                wks.append_row([yt.title, yt.author, message.text, link_yd])
                await message.answer(f'Видео {video_name} добавлено в архив')
        except (VideoUnavailable, BadRequestError) as e:
            logging.error(f'Ошибка при обработке ссылки: {e}')
            await message.answer('Произошла ошибка при обработке ссылки. '
                                 'Пожалуйста, попробуйте еще раз.')
    else:
        await message.answer('Некорректная ссылка!!!')


# Обработчик сообщений, отличных от текстовых
@dp.message()
async def error(message: types.Message):
    await message.answer('Введите ссылку на видео!!!')


# Запуск процесса пуллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())