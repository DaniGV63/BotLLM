from pydantic import BaseModel


class ActionCreate(BaseModel):
    type: str = "create"
    datetime: str
    duration: int = 60
    client_name: str
    client_phone: str
    service: str


class ActionModify(BaseModel):
    type: str = "modify"
    event_id: str
    new_datetime: str


class ActionCancel(BaseModel):
    type: str = "cancel"
    event_id: str


class ActionDerivar(BaseModel):
    type: str = "derivar"
    motivo: str


class LLMResponseSchema(BaseModel):
    message: str
    action: ActionCreate | ActionModify | ActionCancel | ActionDerivar | None = None
    nombre_detectado: str | None = None
