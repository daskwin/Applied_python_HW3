import os
from datetime import datetime
import random
import string

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import redis
from core.database import get_db
from models.user import User
from passlib.context import CryptContext

load_dotenv()

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
SESSION_TTL = int(os.getenv("SESSION_TTL", 86400))


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


@router.post("/register", response_model=UserOut)
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


@router.post("/login", response_model=dict)
def login(user_in: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    Логин пользователя.

    Args:
        user_in (UserLogin): Данные для входа, включающие имя пользователя и пароль.
        request (Request): HTTP-запрос, используемый для получения дополнительной информации (например, cookies).
        db (Session): Сессия базы данных, предоставляемая зависимостью get_db().

    Returns:
        dict: Словарь с сообщением об успешном входе и данными пользователя (id и username). Также устанавливается cookie "session_id" с временем жизни SESSION_TTL.

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


@router.get("/profile", response_model=UserOut)
def profile(current_user: User = Depends(get_current_user)):
    """
    Получение профиля текущего пользователя.

    Args:
        current_user (User): Пользователь, полученный через зависимость get_current_user().

    Returns:
        UserOut: Данные профиля пользователя, включая id, username, email и дату создания.
    """

    return current_user


@router.delete("/user", response_model=dict)
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
