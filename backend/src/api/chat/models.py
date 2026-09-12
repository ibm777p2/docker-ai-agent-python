from sqlmodel import SQLModel, Field

class ChatMessagePayload(SQLModel):
    # pydantic model for validation
    # validation
    # serializer
    message: str
    
class ChatMessage(SQLModel, table=True):
    # database table
    # saving, updating, getting, deleting
    # serializer
    id: int | None = Field(default=None, primary_key=True)
    message: str