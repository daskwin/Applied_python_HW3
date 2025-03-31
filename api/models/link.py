from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from core.database import Base


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
