import logging
from typing import Dict, Any

try:
    from agent_core.config_loader import DecisionConfig
    from agent_core.domain.pipeline_status import PipelineStatus
except Exception:
    from config_loader import DecisionConfig
    from domain.pipeline_status import PipelineStatus

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, config: DecisionConfig):
        self.config = config

    def make_decision(self, agent_runs: Dict[str, Any]) -> PipelineStatus:
        """
        Determine final pipeline status based on failed/halted agent runs.
        """
        failed_runs = {name: run for name, run in agent_runs.items() if run.status in ("failed", "halted")}
        critical_failures = [
            agent_name for agent_name in failed_runs
            if agent_name in self.config.critical_agents or not self.config.get_agent_config(agent_name).graceful_degradation
        ]
        if critical_failures:
            logger.error(f"Pipeline halted due to critical failures: {', '.join(critical_failures)}")
            return PipelineStatus.HALTED_CRITICAL

        degraded_runs = {
            name: run for name, run in agent_runs.items()
            if run.status == "unavailable"
            or any(str(w).lower() in {"data_unavailable", "provider_credentials_unavailable", "llm_unavailable"} for w in getattr(run, "warnings", []))
        }
        if failed_runs or degraded_runs:
            affected = ", ".join(sorted(set(failed_runs) | set(degraded_runs)))
            logger.warning(f"Pipeline partially completed. Unavailable/failed agents: {affected}")
            return PipelineStatus.PARTIALLY_COMPLETED
        return PipelineStatus.COMPLETED
