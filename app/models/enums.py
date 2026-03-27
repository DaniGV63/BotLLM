import enum


class ConversationState(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
