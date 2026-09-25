# Как выложить на Render

1. Сайт https://render.com — вход через GitHub.
2. New → Web Service.
3. Репозиторий vk-song-contest.
4. Language Python, branch main.
5. Build command: pip install -r requirements.txt
6. Start command: uvicorn backend.app:app --host 0.0.0.0 --port $PORT
7. Plan Free → Create Web Service.
8. Подожди, пока статус станет Live. Ссылку кидай друзьям.

Первый заход может длиться до минуты — бесплатный сервер просыпается.
После перезапуска треки на бесплатном плане могут пропасть.
