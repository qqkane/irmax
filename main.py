from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
import secrets
import hashlib
import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="OwerMessage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')


# функция хеширования пароля
def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

# проверка пароля
def verify_password(plain_password, hashed_password):
    return get_password_hash(plain_password) == hashed_password

# генерация токена доступа
def create_db_token(user_id: int, db: Session):
    # генерируем случайную строку
    raw_token = secrets.token_hex(16)
    
    # хешируем её чтобы в базе не лежали токены
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    # сохраняем хеш в базу
    db_token = models.Token(key_hash=token_hash, user_id=user_id)
    db.add(db_token)
    db.commit()
    
    # возвращаем именно сырую строку
    return raw_token

def get_current_user(authorization: str = Query(None), db: Session = Depends(get_db)):
    # если токена нет то доступ запрещен
    if not authorization:
         raise HTTPException(status_code=401, detail="Not authenticated")
    
    # убираем префикс "Token "
    token_key = authorization.replace("Token ", "").strip()
    
    # хешируем токен из запроса
    token_hash = hashlib.sha256(token_key.encode()).hexdigest()
    
    # ищем в базе
    db_token = db.query(models.Token).filter(models.Token.key_hash == token_hash).first()
    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    # возвращаем объект юзера
    return db_token.user

class ConnectionManager:
    def __init__(self):
        # словарь активных соединений
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        # принимаем соединение
        await websocket.accept()
        # запоминаем кто онлайн
        self.active_connections[user_id] = websocket
        print(f"User {user_id} connected")

    def disconnect(self, user_id: int):
        # удаляем юзера из списка онлайн при отключении
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"User {user_id} disconnected")

    async def send_message(self, message: dict, receiver_id: int):
        # отправляем сообщение конкретному юзеру если он онлайн
        if receiver_id in self.active_connections:
            await self.active_connections[receiver_id].send_json(message)

# создаем экземпляр менеджера
manager = ConnectionManager()

# логика регистрации
@app.post("/api/register/", response_model=schemas.TokenResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # проверяем, не занят ли логин
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # создаем юзера с захешированным паролем
    hashed_pwd = get_password_hash(user.password)
    new_user = models.User(username=user.username, password_hash=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # сразу выдаем токен чтобы логиниться отдельно не надо было
    token = create_db_token(new_user.id, db)
    return {"token": token}

@app.post("/api/login/", response_model=schemas.TokenResponse)
def login(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # ищем юзера
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    # проверяем пароль
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # выдаем новый токен
    token = create_db_token(db_user.id, db)
    return {"token": token}

@app.get("/api/users/")
def get_users(auth_token: str = Query(..., alias="token"), db: Session = Depends(get_db)):
    # проверяем авторизацию через нашу функцию
    user = get_current_user(auth_token, db)
    
    # получаем всех юзеров кроме самого себя
    users = db.query(models.User).filter(models.User.id != user.id).all()
    
    # возвращаем красивый список словарей
    return {"users": [{"id": u.id, "username": u.username} for u in users]}

@app.get("/api/messages/")
def get_messages(
    partner: str, 
    date_from: Optional[str] = None, 
    auth_token: str = Query(..., alias="token"), 
    db: Session = Depends(get_db)
):
    # авторизация
    current_user = get_current_user(auth_token, db)
    
    # ищем собеседника в базе
    partner_user = db.query(models.User).filter(models.User.username == partner).first()
    if not partner_user:
        return {"messages": []}

    query = db.query(models.Message).filter(
        ((models.Message.sender_id == current_user.id) & (models.Message.receiver_id == partner_user.id)) |
        ((models.Message.sender_id == partner_user.id) & (models.Message.receiver_id == current_user.id))
    )
    
    # если передали дату фильтруем еще и по дате
    if date_from:
        try:
            dt_obj = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(models.Message.created_at >= dt_obj)
        except:
            pass # если дата не та  то пасс
            
    # сортируем по времени
    messages = query.order_by(models.Message.created_at).all()
    
    # собираем результат
    result = []
    for m in messages:
        result.append({
            "id": m.id,
            "sender": m.sender.username,
            "receiver": m.receiver.username,
            "content": m.content,
            "created_at": str(m.created_at),
            "is_read": m.is_read
        })
        
    return {"messages": result}

@app.post("/api/messages/send/")
async def send_message(
    msg: schemas.MessageCreate, 
    auth_token: str = Query(..., alias="token"), 
    db: Session = Depends(get_db)
):
    # авторизация
    current_user = get_current_user(auth_token, db)
    
    # ищем получателя
    receiver = db.query(models.User).filter(models.User.username == msg.receiver).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # создаем запись в базе
    db_message = models.Message(
        content=msg.content,
        sender_id=current_user.id,
        receiver_id=receiver.id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # готовим пакет данных для отправки через вебсокет
    message_data = {
        "type": "new_message",
        "data": {
            "id": db_message.id,
            "sender": current_user.username,
            "receiver": receiver.username,
            "content": db_message.content,
            "created_at": str(db_message.created_at),
            "is_read": False
        }
    }
    
    # пытаемся отправить получателю в реальном времени
    await manager.send_message(message_data, receiver.id)
    
    return {"id": db_message.id, "status": "ok"}


 

@app.websocket("/ws/chat/")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # получаем сессию базы данных
    db = next(get_db())
    
    # верифицируем токен
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db_token = db.query(models.Token).filter(models.Token.key_hash == token_hash).first()
    
    # если токена нет закрываем соединение
    if not db_token:
        await websocket.close(code=1008) 
        return

    user = db_token.user
    # регистрируем подключение в менеджере
    await manager.connect(websocket, user.id)
    
    try:
        while True:
            # держим соединение живым
            # если клиент пришлет текст мы его прочитаем
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        # если клиент закрыл вкладку делаем исключение и удаляем его из списка
        manager.disconnect(user.id)