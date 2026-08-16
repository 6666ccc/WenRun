from enum import Enum


class KnowledgeBase(str, Enum):
    HOSPITAL = "hospital-custom"
    MEDICAL = "medical-general"
    MEMORY = "conversation-memory"


COLLECTIONS = {
    KnowledgeBase.HOSPITAL: "wenrun_hospital_custom",
    KnowledgeBase.MEDICAL: "wenrun_medical_general",
    KnowledgeBase.MEMORY: "wenrun_conversation_memory",
}
