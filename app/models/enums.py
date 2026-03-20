import enum


class ConversationState(str, enum.Enum):
    ACTIVA = "ACTIVA"
    DESPEDIDA = "DESPEDIDA"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
