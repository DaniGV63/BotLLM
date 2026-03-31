import enum


class ConversationState(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"
    DERIVADA = "DERIVADA"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    THERAPIST = "therapist"


class TenantPlan(str, enum.Enum):
    SIN_PLAN = "SIN_PLAN"
    FREE_TRIAL = "FREE_TRIAL"
    PAID = "PAID"
