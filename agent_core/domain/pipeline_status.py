from enum import Enum

class PipelineStatus(str, Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    HALTED_INSUFFICIENT_EVIDENCE = "halted_evidence"
    HALTED_CRITICAL = "halted_critical"
    HALTED_FREQUENCY = "halted_frequency"
    FAILED = "failed"
