def send_video_from_archive(wks, link):
    """Функция отправки видео из Google Sheets"""
    row_index = wks.col_values(3).index(link) + 1
    return wks.row_values(row_index)[3]

