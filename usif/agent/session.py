"""The conversation loop: model <-> read-only tools, collecting a change plan."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from usif.agent.llm import ChatModel, Message
from usif.agent.tools import Toolbox
from usif.errors import AgentError

__all__ = ["Session", "system_prompt"]

MAX_STEPS = 16


def system_prompt(toolbox: Toolbox) -> str:
    roots = ", ".join(map(str, toolbox.roots)) or "none (scanning is disabled)"
    existence = (
        "The dataset exists."
        if toolbox.dataset.exists()
        else "The dataset does not exist yet: the first approved plan creates it."
    )
    return f"""You are the data agent of USIF, a local, searchable dataset of computational \
materials results (structures with energies, forces, stresses and provenance) kept by a \
research group.

Dataset: {toolbox.dataset}
Directories you may read and scan: {roots}

Rules:
- Use the tools to answer; never invent entries, values or paths. Say when nothing matches.
- You cannot modify the dataset. The propose_* tools add operations to a change plan that the \
user reviews and approves after your answer. Report the exact operations the propose_* tools \
return; never claim that data was imported, changed or removed.
- Before proposing an import, scan the directory and check the candidates (status new, \
registered, conflict). Follow the group layout already in the dataset; otherwise use groups \
such as /projects/<project>/<system>.
- Projects are the groups /projects/<name>, described by their attributes (list_projects). \
To create or describe one, use propose_project. To save files into a project, scan them with \
group /projects/<name>/... and propose_import; to save entries that are already in the dataset \
(for example what a search found), use propose_link: it links them without copying.
- {existence} Only call propose_storage_options when the user asks how data is stored.
- Units: energy and free_energy eV, force eV/Å, stress GPa (positive = tensile), band_gap eV.
- Entry attributes: source (file), source_sha256, code, incar (VASP parameters), notes \
(README text), plan (the approved plan that added the entry), linked_from (the entry a \
linked entry was saved from).
- Be concise. Use tables or short lists for several entries. Answer in the user's language."""


class Session:
    """A conversation with ``model`` over ``toolbox``; :attr:`plan` holds proposals."""

    def __init__(
        self,
        model: ChatModel,
        toolbox: Toolbox,
        *,
        on_tool: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        max_steps: int = MAX_STEPS,
    ) -> None:
        self.model = model
        self.toolbox = toolbox
        self.on_tool = on_tool
        self.max_steps = max_steps
        self.messages: List[Message] = [{"role": "system", "content": system_prompt(toolbox)}]

    @property
    def plan(self) -> Any:
        return self.toolbox.plan

    def ask(self, text: str) -> str:
        """Send one user message; run tool calls until the model answers."""
        if not self.toolbox.plan.request:
            self.toolbox.plan.request = text
        self.messages.append({"role": "user", "content": text})
        specs = self.toolbox.specs()
        for _ in range(self.max_steps):
            reply = self.model.complete(self.messages, specs)
            message: Message = {"role": "assistant", "content": reply.get("content") or ""}
            calls = reply.get("tool_calls") or []
            if reply.get("reasoning_content"):
                message["reasoning_content"] = reply["reasoning_content"]
            if calls:
                message["tool_calls"] = calls
            self.messages.append(message)
            if not calls:
                return str(message["content"])
            for call in calls:
                function = call.get("function", {})
                name = str(function.get("name", ""))
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("arguments must be an object")
                except ValueError as exc:
                    result = json.dumps({"error": f"arguments are not a JSON object: {exc}"})
                else:
                    if self.on_tool is not None:
                        self.on_tool(name, arguments)
                    result = self.toolbox.call(name, arguments)
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.get("id", ""), "content": result}
                )
        raise AgentError(f"no answer after {self.max_steps} tool rounds; ask a narrower question")
