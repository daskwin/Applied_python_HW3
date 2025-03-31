import os
import random
import string
from datetime import datetime, timedelta, timezone

import redis as redis
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from core.database import get_db
from models.link import Link
from api.auth import get_current_user

router = APIRouter()

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
CACHE_TTL = 3600

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
    original_url: str
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
    original_url: str | None = None
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
    original_url: str
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
    original_url: str
    created_at: datetime
    access_count: int


def generate_short_code() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=6))


def update_link_stats(short_code: str):
    db = next(get_db())
    try:
        link = db.query(Link).filter(Link.short_code == short_code).first()
        if link:
            link.access_count += 1
            db.commit()
    finally:
        db.close()


@router.get("/search", response_model=LinkOut)
def search_link(
    original_url: str = Query(..., description="Оригинальный URL для поиска"),
    db: Session = Depends(get_db)
):
    """
    Ищет сокращённую ссылку по исходному URL для текущего пользователя.

    Args:
        original_url (AnyHttpUrl): Исходный URL, по которому производится поиск.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkOut: Объект сокращённой ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.
    """

    link = db.query(Link).filter(Link.original_url == original_url).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    return link


@router.get("/", response_model=list[LinkOut])
def list_links(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Получает список всех ссылок, принадлежащих текущему пользователю.

    Args:
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        list[LinkOut]: Список ссылок, созданных пользователем.
    """

    links = db.query(Link).filter(Link.owner_id == current_user.id).all()

    if not links:
        raise HTTPException(status_code=404, detail="Ссылки не найдены")
    return links


@router.post("/shorten", response_model=LinkOut)
def create_link(link_in: LinkCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
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

    redis_client.setex(f"url:{link.short_code}", CACHE_TTL, link.original_url)

    return link


@router.get("/{short_code}", response_model=LinkOut)
def get_link(short_code: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Получает данные конкретной сокращённой ссылки текущего пользователя.

    Args:
        short_code (str): Короткий код (alias) ссылки.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через зависимость get_current_user().

    Returns:
        LinkOut: Объект ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.
    """

    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    return link


@router.put("/{short_code}", response_model=LinkOut)
def update_link(short_code: str, link_in: LinkUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Обновляет данные сокращённой ссылки.

    Args:
        short_code (str): Короткий код (alias) ссылки, которую необходимо обновить.
        link_in (LinkUpdate): Данные для обновления, включающие новый оригинальный URL и/или количество дней до истечения срока действия.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через get_current_user().

    Returns:
        LinkOut: Объект ссылки, содержащий id, short_code, original_url, created_at, expires_at и access_count.
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

    new_url = link.original_url
    redis_client.setex(f"url:{short_code}", CACHE_TTL, new_url)
    # redis_client.delete(f"url:{short_code}")

    return link


@router.delete("/{short_code}", status_code=204)
def delete_link(short_code: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Удаляет сокращённую ссылку, принадлежащую текущему пользователю.

    Args:
        short_code (str): Короткий код (alias) ссылки, которую необходимо удалить.
        db (Session): Сессия базы данных, предоставляемая через зависимость get_db().
        current_user (User): Текущий пользователь, полученный через get_current_user().

    Returns:
        None: Пустой ответ с HTTP статусом 204 (No Content) при успешном удалении.
    """

    link = db.query(Link).filter(Link.short_code == short_code, Link.owner_id == current_user.id).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    db.delete(link)
    db.commit()
    redis_client.delete(f"url:{short_code}")

    return


@router.get("/{short_code}/stats", response_model=LinkStats)
def get_link_stats(short_code: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
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


@router.get("/public/{short_code}")
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
    cache_key = f"url:{short_code}"
    cached_url = redis_client.get(cache_key)

    if cached_url:
        background_tasks.add_task(update_link_stats, short_code)
        return RedirectResponse(url=cached_url, status_code=302)

    link = db.query(Link).filter(Link.short_code == short_code).first()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ссылка устарела")

    redis_client.setex(cache_key, CACHE_TTL, link.original_url)
    background_tasks.add_task(update_link_stats, short_code)

    return RedirectResponse(url=link.original_url, status_code=302)
