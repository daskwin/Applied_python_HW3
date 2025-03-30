from datetime import datetime, timedelta, timezone
import os
import random
import string
import asyncio

from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, AnyHttpUrl, EmailStr, Field, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.ext.declarative import declarative_base
import redis
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

# Переменные окружения
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecret")
SESSION_TTL = int(os.getenv("SESSION_TTL", 86400))
INACTIVITY_DAYS = int(os.getenv("INACTIVITY_DAYS", 90))

# Инициализация SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Инициализация Redis и bcrypt
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """
    Класс пользователя.

    Атрибуты:
        id (int): Уникальный идентификатор пользователя.
        username (str): Уникальное имя пользователя.
        email (str | None): Адрес электронной почты пользователя (необязательный).
        password_hash (str): Хэш пароля пользователя.
        created_at (datetime): Дата и время создания записи пользователя.
        links (List[Link]): Список ссылок, созданных пользователем.
    """

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    links = relationship("Link", back_populates="owner", cascade="all, delete-orphan", passive_deletes=True)


class Link(Base):
    """
    Класс ссылки.

    Атрибуты:
        id (int): Уникальный идентификатор ссылки.
        original_url (str): Исходный длинный URL.
        short_code (str): 'alias' для ссылки.
        created_at (datetime): Дата и время создания ссылки.
        expires_at (datetime | None): Дата и время истечения срока действия ссылки (если задан).
        access_count (int): Количество переходов по ссылке.
        owner_id (int): Идентификатор пользователя, создавшего ссылку.
        owner (User): Объект пользователя, владеющий ссылкой.
    """

    __tablename__ = "links"
    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String(20), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    owner = relationship("User", back_populates="links")


class UserCreate(BaseModel):
    """
    Класс для создания нового пользователя.

    Атрибуты:
        username (str): Имя пользователя (обязательное поле, должно быть уникальным).
        password (str): Пароль пользователя (обязательное поле, минимум 6 символов).
        email (EmailStr | None): Адрес электронной почты пользователя (необязательное поле).

    model_config:
        Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    username: str
    password: str = Field(..., min_length=6)
    email: EmailStr | None = None


class UserOut(BaseModel):
    """
    Класс для вывода информации о пользователе.

    Атрибуты:
        id (int): Уникальный идентификатор пользователя.
        username (str): Имя пользователя.
        email (EmailStr | None): Электронная почта пользователя, если указана.
        created_at (datetime): Дата и время создания пользователя.

    model_config:
       Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr | None = None
    created_at: datetime


class UserLogin(BaseModel):
    """
    Класс для авторизации пользователя.

    Атрибуты:
        username (str): Имя пользователя.
        password (str): Пароль пользователя.

    model_config:
         Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    username: str
    password: str


class LinkCreate(BaseModel):
    """
    Схема для создания новой сокращённой ссылки.

    Атрибуты:
        original_url (AnyHttpUrl): Исходный URL, который требуется сократить.
        custom_alias (str | None): 'alias' для ссылки. Если не задан, сгенерируется автоматически.
        expires_in_days (int | None): Количество дней до истечения срока действия ссылки. Если не указано, ссылка может быть бессрочной.

    model_config:
        Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    original_url: AnyHttpUrl
    custom_alias: str | None = None
    expires_in_days: int | None = None


class LinkUpdate(BaseModel):
    """
    Класс для обновления данных сокращённой ссылки.

    Атрибуты:
        original_url (AnyHttpUrl | None): Новый исходный URL. Если не указан, предыдущий URL сохраняется.
        expires_in_days (int | None): Новое количество дней до истечения срока действия ссылки. Если не указано, срок не обновляется.

    model_config:
        Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    original_url: AnyHttpUrl | None = None
    expires_in_days: int | None = None


class LinkOut(BaseModel):
    """
    Класс для вывода информации о сокращённой ссылке.

    Атрибуты:
        id (int): Уникальный идентификатор ссылки.
        short_code (str): Уникальный код (alias) для ссылки.
        original_url (AnyHttpUrl): Исходный URL, который был сокращен.
        created_at (datetime): Дата и время создания ссылки.
        expires_at (datetime | None): Дата и время истечения срока действия ссылки (если задан).
        access_count (int): Количество переходов по ссылке.

    model_config:
        Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """

    model_config = ConfigDict(from_attributes=True)
    id: int
    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None = None
    access_count: int


class LinkStats(BaseModel):
    """
    Класс для вывода статистики сокращённой ссылки.

    Атрибуты:
        original_url (AnyHttpUrl): Исходный URL, связанный со ссылкой.
        created_at (datetime): Дата и время создания ссылки.
        access_count (int): Количество переходов по ссылке.

    model_config:
        Используется ConfigDict с поддержкой создания экземпляров модели из ORM-объектов.
    """
    model_config = ConfigDict(from_attributes=True)
    original_url: AnyHttpUrl
    created_at: datetime
    access_count: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_session_token(user_id: int) -> str:
    token = f"session:{user_id}:{datetime.utcnow().timestamp()}"
    redis_client.setex(token, SESSION_TTL, user_id)
    return token


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_id")
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    user_id = redis_client.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def generate_short_code() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=6))


def update_link_stats(short_code: str):
    db = SessionLocal()
    try:
        link = db.query(Link).filter(Link.short_code == short_code).first()
        if link:
            link.access_count += 1
            db.commit()
    finally:
        db.close()


# Основное приложение
app = FastAPI(title="Simpler Linker API")
Base.metadata.create_all(bind=engine)


# Регистрация пользователя
@app.post("/auth/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Регистрация нового пользователя.

    Args:
        user_in (UserCreate): Данные для регистрации нового пользователя, включающие username, password и опционально email.
        db (Session): Сессия базы данных, предоставляемая зависимостью get_db().

    Returns:
        UserOut: Объект, содержащий id, username, email и дату создания зарегистрированного пользователя.

    - Если в базе данных уже существует пользователь с указанным username, генерируется исключение HTTP 400.
    - Если username свободен, создаётся новый пользователь с хэшированным паролем.
    - Новый пользователь сохраняется в базе данных, затем обновляется и возвращается.
    """

    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# Логин пользователя
@app.post("/auth/login", response_model=dict)
def login(user_in: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    Логин пользователя.

    Args:
        user_in (UserLogin): Данные для входа, включающие имя пользователя и пароль.
        request (Request): HTTP-запрос, используемый для получения дополнительной информации (например, cookies).
        db (Session): Сессия базы данных, предоставляемая зависимостью get_db().

    Returns:
        dict: Словарь с сообщением об успешном входе и данными пользователя (id и username). Также устанавливает cookie "session_id" с временем жизни SESSION_TTL.

    - Если пользователь не найден или пароль неверный, генерируется исключение HTTP 401.
    - При успешной аутентификации генерируется токен сессии, устанавливается cookie "session_id" и возвращается JSON с данными пользователя.
    """

    user = db.query(User).filter(User.username == user_in.username).first()

    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверные учетные данные")

    token = create_session_token(user.id)
    resp = JSONResponse({"message": "Успешный вход", "user": {"id": user.id, "username": user.username}})
    resp.set_cookie(key="session_id", value=token, httponly=True, max_age=SESSION_TTL)
    return resp


# Получение профиля
@app.get("/auth/profile", response_model=UserOut)
def profile(current_user: User = Depends(get_current_user)):
    """
    Получение профиля текущего пользователя.

    Args:
        current_user (User): Пользователь, полученный через зависимость get_current_user().

    Returns:
        UserOut: Данные профиля пользователя, включая id, username, email и дату создания.
    """

    return current_user


# Удаление пользователя
@app.delete("/auth/user", response_model=dict)
def delete_user(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Удаляет текущего пользователя.

    Args:
        request (Request): HTTP-запрос для получения контекста.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через get_current_user().

    Returns:
        dict: Словарь с сообщением о том, что пользователь удален.
    """

    db.delete(current_user)
    db.commit()
    return {"message": "Пользователь удален"}


# Список ссылок
@app.get("/links", response_model=list[LinkOut])
def list_links(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Получает список всех ссылок, принадлежащих текущему пользователю.

    Args:
        db (Session): Сессия базы данных, предоставляемая зависимостью get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        list[LinkOut]: Список ссылок, созданных пользователем.
    """

    links = db.query(Link).filter(Link.owner_id == current_user.id).all()

    if not links:
        raise HTTPException(status_code=404, detail="Ссылки не найдены")

    return links


# Создание ссылки
@app.post("/links/shorten", response_model=LinkOut)
def create_link(link_in: LinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Создает новую сокращённую ссылку для текущего пользователя.

    Args:
        link_in (LinkCreate): Данные для создания ссылки, включающие:
            - original_url (AnyHttpUrl): Исходный URL, который нужно сократить.
            - custom_alias (str | None): Опциональное пользовательское имя (alias) для ссылки.
            - expires_in_days (int | None): Количество дней, через которое ссылка станет недействительной.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkOut: Объект созданной ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.

    - Если задан custom_alias, проверяется его уникальность в базе данных.
    - Если custom_alias не предоставлен, генерируется случайный короткий код.
    - Если expires_in_days указан, вычисляется expires_at как текущее время в UTC плюс указанное количество дней.
    - Поле original_url приводится к строке для корректного сохранения в базе данных.
    """

    if link_in.custom_alias:
        if db.query(Link).filter(Link.short_code == link_in.custom_alias).first():
            raise HTTPException(status_code=400, detail="Alias уже используется")
        code = link_in.custom_alias
    else:
        code = generate_short_code()
        while db.query(Link).filter(Link.short_code == code).first():
            code = generate_short_code()
    expires_at = None

    if link_in.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=link_in.expires_in_days)

    link = Link(
        original_url=str(link_in.original_url),
        short_code=code,
        expires_at=expires_at,
        owner_id=current_user.id
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return link


# Получение данных ссылки (для владельца)
@app.get("/links/{short_code}", response_model=LinkOut)
def get_link(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Получает данные конкретной сокращённой ссылки текущего пользователя.

    Args:
        short_code (str): Короткий код (alias) ссылки.
        db (Session): Сессия базы данных, предоставляемая зависимостью get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkOut: Объект ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.
    """
    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    return link


# Обновление ссылки
@app.put("/links/{short_code}", response_model=LinkOut)
def update_link(short_code: str, link_in: LinkUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Обновляет данные сокращённой ссылки.

    Args:
        short_code (str): Короткий код (alias) ссылки, которую необходимо обновить.
        link_in (LinkUpdate): Данные для обновления, включающие новый оригинальный URL и/или количество дней до истечения срока действия.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через get_current_user().

    Returns:
        LinkOut: Обновлённый объект ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.

    - Если передан новый original_url, он приводится к строке и обновляется.
    - Если указан expires_in_days, вычисляется новое значение expires_at как текущее время UTC плюс указанное количество дней.
    - Обновленные данные сохраняются в базе данных, после чего объект обновляется и возвращается.
    """

    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if link_in.original_url:
        link.original_url = str(link_in.original_url)
    if link_in.expires_in_days is not None:
        link.expires_at = datetime.now(timezone.utc) + timedelta(days=link_in.expires_in_days)
    db.commit()
    db.refresh(link)
    return link


# Удаление ссылки
@app.delete("/links/{short_code}", status_code=204)
def delete_link(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Удаляет сокращённую ссылку, принадлежащую текущему пользователю.

    Args:
        short_code (str): Короткий код (alias) ссылки, которую необходимо удалить.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        None: Пустой ответ с HTTP статусом 204 (No Content) при успешном удалении.
    """

    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    db.delete(link)
    db.commit()
    return


# Получение статистики ссылки
@app.get("/links/{short_code}/stats", response_model=LinkStats)
def get_link_stats(short_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Получает статистику по сокращённой ссылке для текущего пользователя.

    Args:
        short_code (str): Короткий код (alias) ссылки, для которой требуется статистика.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkStats: Объект, содержащий оригинальный URL (original_url), дату создания (created_at) и количество переходов (access_count)
                   для указанной ссылки.
    """

    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    return LinkStats(original_url=link.original_url, created_at=link.created_at, access_count=link.access_count)


# Поиск ссылки по оригинальному URL
@app.get("/links/search", response_model=LinkOut)
def search_link(original_url: AnyHttpUrl, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Ищет сокращённую ссылку по исходному URL для текущего пользователя.

    Args:
        original_url (AnyHttpUrl): Исходный URL, по которому производится поиск.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkOut: Объект сокращённой ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.
    """

    link = db.query(Link).filter(Link.original_url == str(original_url), Link.owner_id == current_user.id).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    return link


# Публичный редирект
@app.get("/{short_code}")
async def public_redirect(short_code: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Публичный редирект по короткому коду.

    Args:
        short_code (str): Короткий код (alias) ссылки.
        background_tasks (BackgroundTasks): Объект для добавления фоновых задач.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().

    Returns:
        RedirectResponse: Перенаправляет пользователя на оригинальный URL, связанный с данным коротким кодом, с HTTP статусом 302.
    """

    link = db.query(Link).filter(Link.short_code == short_code).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ссылка устарела")

    background_tasks.add_task(update_link_stats, short_code)
    return RedirectResponse(url=link.original_url, status_code=302)
