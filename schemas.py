from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# базовая схема юзера
class UserBase(BaseModel):
    username: str

# схема для создания юзера
# наследуется логин
class UserCreate(UserBase):
    password: str

# схема ответа 
class User(UserBase):
    id: int
    class Config:
        # позволяет pydantic читать данные напрямую из объектов
        from_attributes = True

# схема ответа при логине/регистрации
class TokenResponse(BaseModel):
    token: str

# базовая схема сообщения
class MessageBase(BaseModel):
    receiver: str # имя получателя
    content: str # текст

# схема для отправки сообщения
class MessageCreate(MessageBase):
    pass # все то же самое но пустой класс наследник

# схема ответа при получении сообщения
class MessageOut(BaseModel):
    id: int
    sender: str # имя отправителя
    receiver: str # имя получателя
    content: str
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True