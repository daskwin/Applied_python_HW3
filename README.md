# Simpler Linker API

Сервис для сокращения URL, позволяющий пользователям регистрироваться, создавать короткие ссылки с возможностью задания кастомного alias и срока действия, а также получать статистику по ссылкам.

## Функциональные возможности сервиса

### Обязательные функции ДЗ:
- **Создание / удаление / изменение / получение информации по короткой ссылке:**
  - POST `/links/shorten` – создание новой сокращённой ссылки для текущего пользователя.
  - GET `/links/{short_code}` - получаение данных для конкретной сокращённой ссылки текущего пользователя.
  - DELETE `/links/{short_code}` - удаление указанной сокращённой ссылки, принадлежащей текущему пользователю.
  - PUT `/links/{short_code}` - обновление данных ссылки – оригинальный URL и/или срок действия.
- **Статистика по ссылке:**
  - GET `/links/{short_code}/stats` – получение статистики по сокращённой ссылке для текущего пользователя.
- **Создание кастомных ссылок (уникальный alias):**
  - POST `/links/shorten` (с передачей custom_alias) - через один endpoint реализуются разные функционалы (в этом пункте при указании custom_alias проверяется уникальность).
- **Поиск ссылки по оригинальному URL:**
  - GET `/links/search?original_url={url}` – поиск сокращенной ссылки по исходному URL для текущего пользователя.
- **Указание времени жизни ссылки:**
  - POST `/links/shorten` (с параметром expires_at) - через один endpoint реализуются разные функционалы (в этом пункте при указании expires_at указывается время жизни ссылки).
- **Регистрация и управление аккаунтом:**
  - POST `/auth/register` – регистрация нового пользователя.
  - POST `/auth/login` – вход в систему (с установкой cookie-сессии).
  - GET `/auth/profile` – получение профиля текущего пользователя.
  - DELETE `/auth/user` – удаление аккаунта (с каскадным удалением всех связанных ссылок).

## Структура проекта

```
Simpler Linker API/
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   ├── app.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── links.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── database.py
│   └── models/
│       ├── __init__.py
│       ├── user.py
│       └── link.py
├── docker-compose.yml
└── README.md
```

## Локальный запуск

1. **Настройка переменных окружения для локального запуска:**  
   В файле `api/.env` укажите следующие значения по шаблону:
   ```env
   DATABASE_URL=postgresql://urlshort:urlshortpass@localhost:5432/urlshort_db
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=YourProdSecretKeyHere
   SESSION_TTL=86400
   INACTIVITY_DAYS=90
   ```

2.	**Запуск backend:**
Перейдите в папку api и выполните:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступно по ссылке http://localhost:8000 в случае локального тестирования.

4.	**Тестирование API:**
 
Я использовала Postman.

5. **Docker Compose**

Для сборки сервиса был написан Docker Compose файл для локального тестирования.

Шаблон docker-compose.yml:

```yaml
services:
  db:
    image: postgres:15-alpine
    container_name: simplerlink_db
    environment:
      POSTGRES_USER: linker_user
      POSTGRES_PASSWORD: linker_pass
      POSTGRES_DB: linker_db
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - internal

  redis:
    image: redis:7-alpine
    container_name: simplerlink_redis
    ports:
      - "6379:6379"
    networks:
      - internal

  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: simplerlink_api
    env_file:
      - ./api/.env
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    networks:
      - internal

networks:
  internal:
    driver: bridge

volumes:
  db_data:
```

Запустить можно командой:

```bash
docker-compose up --build
```

## Примеры работы API

### 1. Register User - регистрация
 - **Endpoint**: `{{API_URL}}/api/auth/register`
 - **Method**: `POST`
 - **Headers**: Content-Type: `application/json`
 - **Body**:
```json
{
  "username": "daskwin",
  "password": "mypassword",
  "email": "daskwin@example.com"
}
```

> **Response:**
>```json
>{
>  "id": 2,
>  "username": "daskwin",
>  "email": "daswin@example.com",
>  "created_at": "2025-03-31T08:35:53.288861Z"
>}
>```

### 2. Login User - логин пользователя
 - **Endpoint**: `{{API_URL}}/api/auth/login`
 - **Method:** `POST`
 - **Headers:** Content-Type: `application/json`
 - **Body:**
```json
{
  "username": "daskwin",
  "password": "mypassword"
}
```

> **Response:**
>```json
>{
>    "message": "Успешный вход",
>    "user": {
>        "id": 2,
>        "username": "daskwin"
>    }
>}
>```

> Cookie с именем session_id сохраняется для дальнейших запросов.

### 3. Get Profile
 - **Endpoint:** `{{API_URL}}/api/auth/profile`
 - **Method:** `GET`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -

> **Response:**
>```json
>{
>    "id": 2,
>    "username": "daskwin",
>    "email": "daskwin@example.com",
>    "created_at": "2025-03-31T08:35:53.288861Z"
>}
>```

### 4. Create Link
 - **Endpoint:** `{{API_URL}}/api/links/shorten`
 - **Method:** `POST`
 - **Headers:**
   - Content-Type: `application/json`
   - Cookie: `session_id={{session_id}}`
 - **Body:**

```json
{
  "original_url": "https://example.com/very-long-and-difficult-for-me",
  "custom_alias": "simple",
  "expires_in_days": 3
}
```

> **Response:**
> ```json
> {
>    "id": 2,
>    "short_code": "simple",
>    "original_url": "https://example.com/very-long-and-difficult-for-me",
>    "created_at": "2025-03-31T09:10:08.226766Z",
>    "expires_at": "2025-04-03T09:10:08.224911Z",
>    "access_count": 0
>}
> ```

### 5. List Links
 - **Endpoint:** `{{API_URL}}/api/links`
 - **Method:** `GET`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -

> **Response:**
> ```json
>[
>    {
>        "id": 2,
>        "short_code": "simple",
>        "original_url": "https://example.com/very-long-and-difficult-for-me",
>        "created_at": "2025-03-31T09:10:08.226766Z",
>        "expires_at": "2025-04-03T09:10:08.224911Z",
>        "access_count": 0
>    }
>]
> ```

### 6. Get Link by short_code
 - **Endpoint:** `{{API_URL}}/api/links/{{short_code}}`
 - **Method:** `GET`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -

> **Response for short_code = simple:**
> ```json
> {
>    "id": 2,
>    "short_code": "simple",
>    "original_url": "https://example.com/very-long-and-difficult-for-me",
>    "created_at": "2025-03-31T09:10:08.226766Z",
>    "expires_at": "2025-04-03T09:10:08.224911Z",
>    "access_count": 0
>}
> ```

### 7. Update Link
 - **Endpoint:** `{{API_URL}}/api/links/{{short_code}}`
 - **Method:** `PUT`
 - **Headers:**
   - Content-Type: `application/json`
   - Cookie: `session_id={{session_id}}`
 - **Body:**

```json
{
  "original_url": "https://example.com/updated-url-but-difficult",
  "expires_in_days": 5
}
```

> **Response:**
> ```json
>{
>    "id": 2,
>    "short_code": "simple",
>    "original_url": "https://example.com/updated-url-but-difficult",
>    "created_at": "2025-03-31T09:10:08.226766Z",
>    "expires_at": "2025-04-05T09:25:54.641557Z",
>    "access_count": 0
>}
> ```

### 8. Get Link Stats
 - **Endpoint:** `{{API_URL}}/api/links/{{short_code}}/stats`
 - **Method:** `GET`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -
  
> **Response:**
>```json
>{
>    "original_url": "https://example.com/updated-url-but-difficult",
>    "created_at": "2025-03-31T09:10:08.226766Z",
>    "access_count": 1
>}
>``` 

### 9. Search Link by Original URL
 - **Endpoint:** `{{API_URL}}/api/links/search?original_url=https://example.com/updated-url-but-difficult`
 - **Method:** `GET`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -

> **Response:**
>```json
>{
>    "id": 2,
>    "short_code": "simple",
>    "original_url": "https://example.com/updated-url-but-difficult",
>    "created_at": "2025-03-31T09:10:08.226766Z",
>    "expires_at": "2025-04-05T09:25:54.641557Z",
>    "access_count": 1
>}
>``` 

### 10. Public Redirect
 - **Endpoint:** `{{API_URL}}/api/links/public/{{short_code}}`
 - **Method:** GET
 - **Headers:** -
 - **Body:** -
 -

> **Response:** получили код страницы изначальной ссылки.

### 11. Delete Link
 - **Endpoint:** `{{API_URL}}/api/links/{{short_code}}`
 - **Method:** `DELETE`
 - **Headers:** Cookie: `session_id={{session_id}}`
 - **Body:** -

>**Response:** произошло удаление привязки ссылок.

### 12. Delete User (Account)
- **Endpoint:** `{{API_URL}}/api/auth/user`
- **Method:** `DELETE`
- **Headers:**
- **Cookie:** `session_id={{session_id}}`
- **Body:** (нет)

> **Response:**
>```json
>{
>  "message": "Пользователь удалён"
>}
>```

## Deploy на Render

Проект был задеплойен с помощью платформы [Render](https://dashboard.render.com/). 
На основе кода этого репозитория, в этой платформе было развернуто 3 компонента сервиса:

1. FastAPI сервис:  [https://pylinkshort.onrender.com](https://applied-python-hw3.onrender.com);
3. PostgreSQL DB;
4. Redis (key-value store).

## Описание БД

В качестве основного хранилища используется PostgreSQL (указанная в переменной окружения DATABASE_URL).

Структура БД:
- Таблица users: хранит информацию о пользователях.
- Поля:
  - id – уникальный идентификатор пользователя.
	- username – уникальное имя пользователя.
  - email – адрес электронной почты (необязательное).
	- password_hash – хэш пароля.
  - created_at – дата и время регистрации.
- Таблица links: хранит данные о сокращённых ссылках.
- Поля:
  - id – уникальный идентификатор ссылки.
  - original_url – исходный длинный URL.
  - short_code – сокращённый код (alias) ссылки.
	- created_at – дата и время создания ссылки.
  - expires_at – дата и время истечения срока действия ссылки (если задан).
	- access_count – количество переходов по ссылке.
  - owner_id – идентификатор пользователя, создавшего ссылку (связь с таблицей users).

Redis используется для хранения сессионных токенов (управление сессиями) и для кэширования (в моем случае при создании ссылки кэшированием запоминаем юрл, используем при публичном редиректе).

## Дополнительные ссылки:
- https://applied-python-hw3.onrender.com - ссылка на сервис
- https://applied-python-hw3.onrender.com/docs - документация

