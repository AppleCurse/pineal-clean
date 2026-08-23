from enum import Enum

class PipelineStatus(str, Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    HALTED_INSUFFICIENT_EVIDENCE = "halted_evidence"
    HALTED_CRITICAL = "halted_critical"
    HALTED_FREQUENCY = "halted_frequency"
    FAILED = "failed"

    def is_success(self) -> bool:
        return self in (PipelineStatus.COMPLETED, PipelineStatus.PARTIALLY_COMPLETED)
    
    def is_halted(self) -> bool:
        return self in (
            PipelineStatus.HALTED_INSUFFICIENT_EVIDENCE, 
            PipelineStatus.HALTED_CRITICAL, 
            PipelineStatus.HALTED_FREQUENCY
        )
