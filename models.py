from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# модель таблицы пользователей
class User(Base):
    __tablename__ = "users" # имя таблицы в базе
    
    id = Column(Integer, primary_key=True, index=True) # айди и автоинкремент
    username = Column(String, unique=True, index=True, nullable=False) # логин (уникальный)
    password_hash = Column(String, nullable=False) # хеш пароля
    
    # связи для обращения к связанным данным
    # например user.sent_messages вернет все сообщения где юзер отправитель
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    tokens = relationship("Token", back_populates="user") # связь с токенами

# модель таблицы токенов для авторизации
class Token(Base):
    __tablename__ = "tokens"
    # key_hash ето хеш токена
    key_hash = Column(String, primary_key=True, unique=True, index=True) 
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # ссылка на юзера
    created = Column(DateTime, default=datetime.utcnow) # когда создан
    
    user = relationship("User", back_populates="tokens") # обратная связь

# модель таблицы сообщений
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False) # текст сообщения
    created_at = Column(DateTime, default=datetime.utcnow, index=True) # время создания
    is_read = Column(Boolean, default=False) # прочитано или нет
    
    # внешние ключи, кто отправил и кому
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # связи чтобы писать message.sender.username
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")