from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from core.database import Base


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
