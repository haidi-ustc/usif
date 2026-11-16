"""The USIF data agent: natural-language access to a local dataset, with human approval.

* :mod:`usif.agent.config` - the OpenAI-compatible endpoint (DeepSeek by default);
* :mod:`usif.agent.llm` - the HTTP chat client (standard library only);
* :mod:`usif.agent.discover` - finding calculations and structure files in directories;
* :mod:`usif.agent.plan` - change plans and :func:`apply_plan`, the only write path;
* :mod:`usif.agent.tools` - the read-only tools and ``propose_*`` tools the model uses;
* :mod:`usif.agent.session` - the conversation loop.

The model can read and propose; a person approves a plan before anything is
written.
"""

from usif.agent.config import LLMConfig, load_config
from usif.agent.discover import Candidate, ScanResult, scan
from usif.agent.llm import ChatClient, ChatModel
from usif.agent.plan import ApplyReport, Operation, Plan, apply_plan, plan_from_scan
from usif.agent.session import Session
from usif.agent.tools import Toolbox

__all__ = [
    "ApplyReport",
    "Candidate",
    "ChatClient",
    "ChatModel",
    "LLMConfig",
    "Operation",
    "Plan",
    "ScanResult",
    "Session",
    "Toolbox",
    "apply_plan",
    "load_config",
    "plan_from_scan",
    "scan",
]
