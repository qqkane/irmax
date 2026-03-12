from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# адрес базы данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./messenger.db"

# создаем движок базы данных
# эта настройка отключает эту проверку
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# создание сессии локальной
local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# класс для моделей
Base = declarative_base()

def get_db():
    # создаем сессию
    db = local_session()
    try:
        # yield работает как return но не убивает функцию окончательно
        yield db
    finally:
        # в любом случаезакрываем соединение
        db.close()