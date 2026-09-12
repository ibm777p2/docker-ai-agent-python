from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from .models import ChatMessagePayload, ChatMessage
from api.db import get_session
router = APIRouter()

# /api/chats/
@router.get("/")
def chat_health():
    return{"status": "ok"}

# /api/chats/recent/
# curl http://localhost:8080/api/chats/recent/
@router.get("/recent/")
def chat_list_messages(session: Session= Depends(get_session)):
    query = select(ChatMessage)# sql -> query
    results = session.exec(query).fetchall()[:10]
    return results

# HTTP POST -> {"message": "Nice site"} -> {"message": "Nice site", "id": 1}
# curl -X POST -d '{"message": "Nice site"}' -H "Content-type: application/json" http://localhost:8080/api/chats/
@router.post("/", response_model=ChatMessage)
def chat_create_message(
    payload:ChatMessagePayload,
    session: Session = Depends(get_session)
):
    
    data = payload.model_dump() # pydantic -> dict
    print(data)
    obj = ChatMessage.model_validate(data)
    session.add(obj)
    session.commit()
    session.refresh(obj)# ensure id/primary key added to the obj instace
    # ready to store in the database
    return obj