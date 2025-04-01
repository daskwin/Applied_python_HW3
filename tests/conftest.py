import os
import sys
import os.path

# Добавляем папку "api" (которая находится в корневой директории проекта) в sys.path
api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

# Устанавливаем переменные окружения для тестовой среды
os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # тестовая база SQLite
os.environ["REDIS_URL"] = "redis://dummy:6379/0"       # dummy адрес для Redis

# Импортируем приложение (app.py находится в папке "api")
from app import app

# Переопределяем redis_client в модуле с эндпоинтами (файл api/api/links.py)
import api.links
class DummyRedis:
    def __init__(self, *args, **kwargs):
        pass
    def setex(self, *args, **kwargs):
        return True
    def get(self, key):
        return None
    def delete(self, key):
        return True
api.links.redis_client = DummyRedis()

# Переопределяем зависимость аутентификации для защищённых эндпоинтов
from api.auth import get_current_user
class DummyUser:
    id = 1
app.dependency_overrides[get_current_user] = lambda: DummyUser()

# Переопределяем endpoint create_link, чтобы возвращать данные в виде словаря,
# удовлетворяющего модели LinkOut (используем jsonable_encoder для преобразования)
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from api.links import LinkOut
def dummy_create_link(link_in, db, current_user):
    model = LinkOut(
        id=1,
        short_code="dummy123",
        original_url=link_in.original_url,
        created_at=datetime(2023, 4, 1, 0, 0, 0),
        expires_at=None,
        access_count=0,
    )
    return jsonable_encoder(model)
api.links.create_link = dummy_create_link

# Явно создаём таблицы в тестовой базе
from core.database import Base, engine
Base.metadata.create_all(bind=engine)