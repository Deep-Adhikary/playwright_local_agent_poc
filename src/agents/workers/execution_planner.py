from __future__ import annotations

from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from typing import Any

from src.libs.utils.configs import ModelConfig

MODELCONFIG=ModelConfig(
    model_name="qwen2.5:14b-instruct",
    temperature=0.5,
    max_tokens=1024
)

PLANNER_PROMPT = PromptTemplate(
    input_variables=["goal", "context"],
    template="""
ROLE
You are a PLANNER agent. You ONLY convert the user's goal into an ordered list of small executable tasks.
You do NOT decide tools or implementation.

HARD RULES
- Do NOT mention tools, selectors, refs, APIs, code, or implementation details.
- Output MUST be valid JSON and MUST match EXACTLY this schema:
  {{
    "goal": "string",
    "tasks": [
      {{
        "id": "T1",
        "task": "imperative short sentence",
        "done_when": ["observable completion checks (state/outcome-based)"],
        "needs": {{ "input_name": "value_or_placeholder" }},
        "notes": ["edge cases, constraints, or clarifications"]
      }}
    ],
    "completion_definition": [
      "high-level stop conditions for the overall goal (NOT per-task checks)"
    ]
  }}

TASK QUALITY CONSTRAINTS
- Each task must be small enough to be completed by an executor in 1–3 actions.
- Tasks must be ordered and avoid duplication.
- Include an early task that forces capturing or refreshing the current state.
- done_when MUST describe observable outcomes, not actions (e.g. avoid words like click, type, submit).
- needs is ONLY for required inputs or prerequisites. Use placeholders like "<from user>" if unknown.
- completion_definition should usually contain 1–3 items and must remain high-level.

SELF-CHECK (SILENT)
Before responding, verify:
- Output is valid JSON
- No implementation or tool-related terms are present
- Every task includes at least one done_when condition
- completion_definition reflects overall completion, not step mechanics

INPUT
Goal:
{goal}

Context (optional, may be empty):
{context}
""".strip(),
)

class Task(BaseModel):
    id: str
    task: str
    done_when: list[str] = Field(default_factory=list)
    needs: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

class TaskPlan(BaseModel):
    goal: str
    tasks: list[Task]
    completion_definition: list[str] = Field(default_factory=list)

def create_execution_plan(
    goal: str, context: str| None = None,
) -> TaskPlan:
    prompt=PLANNER_PROMPT.format(goal=goal, context=context or "(None)")
    llm=ChatOllama(
        model=MODELCONFIG.model_name,
        temperature=MODELCONFIG.temperature,
        max_tokens=MODELCONFIG.max_tokens
        )
    response=llm.invoke(prompt).content
    print("Planner LLM Response:", response)
    return TaskPlan.model_validate_json(response)
if __name__ == "__main__":
    sample_goal="""
    Navigate to PanlelApp Website.
    Go to the panel tab
    search a panel named 'Test Panel'
    Verify that panel is exists
    Open the panel by clicking on it
"""
    plan=create_execution_plan(sample_goal)