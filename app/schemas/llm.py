from pydantic import BaseModel


class SlotPreference(BaseModel):
    """Preferencia horaria extraída por el LLM del mensaje del paciente."""
    date: str | None = None        # "YYYY-MM-DD" o null
    period: str | None = None      # "mañana" | "mediodia" | "tarde" | null


class ActionCreate(BaseModel):
    type: str = "create"
    datetime: str
    duration: int = 60
    client_name: str
    client_phone: str
    service: str
    is_group_class: bool = False
    session_id: str | None = None


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
    slot_preference: SlotPreference | None = None
