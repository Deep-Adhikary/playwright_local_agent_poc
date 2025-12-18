import re

from pydantic import BaseModel, Field

from src.libs.snapshot_manager.snapshot_parser import (
    HEADING_ROLE,
    INTERACTIVE_ROLES,
    LANDMARK_ROLES,
    REPEATER_ITEM_ROLES,
    Node,
    ancestors_with_context,
    first_salient_text,
    iter_nodes,
    parse_snapshot,
)


class Action(BaseModel):
    action_id: str
    role: str
    ref: str
    name: str | None = None
    url: str | None = None
    disabled: bool = False

    model_config = {"extra": "forbid", "frozen": True}


class Item(BaseModel):
    item_id: str
    actions: list[Action] = Field(default_factory=list)

    item_key: str | None = None
    container_role: str | None = None

    model_config = {"extra": "forbid", "frozen": True}


class Section(BaseModel):
    section_id: str
    items: list[Item] = Field(default_factory=list)

    landmark: str | None = None
    heading_path: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid", "frozen": True}


def heading_path_for(ancs: list[Node]) -> list[str]:
    # collect headings from ancestors; keep last few
    hp = [a.name for a in ancs if a.role == HEADING_ROLE and a.name]
    # de-noise: keep last 3 headings
    return hp[-3:]


def nearest_landmark(ancs: list[Node]) -> Node | None:
    for a in reversed(ancs):
        if a.role in LANDMARK_ROLES:
            return a
    return None


def nearest_item_container(ancs: list[Node]) -> Node | None:
    # nearest row/listitem/group ancestor
    for a in reversed(ancs):
        if a.role in REPEATER_ITEM_ROLES:
            return a
    return None


def build_context_model(snapshot_text: str) -> dict[str, any]:
    root = parse_snapshot(snapshot_text)
    chains = ancestors_with_context(root)

    # key: (section_id, item_node_id) -> item
    sections: dict[str, Section] = {}
    item_map: dict[tuple[str, int], Item] = {}

    for n in iter_nodes(root):
        if n.role not in INTERACTIVE_ROLES:
            continue
        if not n.ref:
            continue

        ancs = chains[id(n)]
        lm = nearest_landmark(ancs)
        section_landmark = lm.role if lm else "unknown"
        hp = heading_path_for(ancs)

        section_id = f"s_{section_landmark}_{'_'.join(hp) if hp else 'noheading'}"
        if section_id not in sections:
            sections[section_id] = {
                "section_id": section_id,
                "landmark": section_landmark,
                "heading_path": hp,
                "items": [],
            }

        item_container = nearest_item_container(ancs) or (lm if lm else ancs[-1] if ancs else root)
        item_key = first_salient_text(item_container)

        item_key_id = (section_id, id(item_container))
        if item_key_id not in item_map:
            item = {
                "item_id": f"{section_id}/i{len(item_map)}",
                "item_key": item_key,
                "container_role": item_container.role,
                "actions": [],
            }
            item_map[item_key_id] = item
            sections[section_id]["items"].append(item)

        action: Action = {
            "action_id": f"{item_map[item_key_id]['item_id']}/a{len(item_map[item_key_id]['actions'])}",
            "role": n.role,
            "name": n.name or "",
            "ref": n.ref,
            "disabled": n.disabled,
        }
        if "url" in n.attrs:
            action["url"] = n.attrs["url"]

        item_map[item_key_id]["actions"].append(action)

    return {
        "page": {},  # you can add title/url externally
        "sections": list(sections.values()),
    }


def trim_for_llm(
    model: dict[str, any],
    task: str,
    max_sections: int = 3,
    max_items: int = 8,
    max_actions: int = 8,
) -> dict[str, any]:
    """
    A simple relevance trim:
    - keep sections whose heading_path matches task keywords
    - keep top items/actions by basic keyword scoring
    """
    kw = {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", task) if len(w) > 2}

    def score_text(s: str) -> int:
        s2 = s.lower()
        return sum(1 for k in kw if k in s2)

    # score sections by heading
    sections = model["sections"]
    scored_sections = sorted(
        sections, key=lambda sec: score_text(" ".join(sec.get("heading_path", []))), reverse=True
    )[:max_sections]

    trimmed_sections: list[Section] = []
    for sec in scored_sections:
        items = sec.get("items", [])
        # score items by item_key
        scored_items = sorted(
            items, key=lambda it: score_text(it.get("item_key", "")), reverse=True
        )[:max_items]

        new_items: list[Item] = []
        for it in scored_items:
            acts = it.get("actions", [])
            # score actions by name + url
            scored_acts = sorted(
                acts,
                key=lambda a: score_text(a.get("name", "") + " " + a.get("url", "")),
                reverse=True,
            )[:max_actions]
            new_items.append({**it, "actions": scored_acts})

        trimmed_sections.append({**sec, "items": new_items})

    return {"task": task, "sections": trimmed_sections}


if __name__ == "__main__":
    with open("scratchpad/output.format.md") as f:
        snapshot_text = f.read()
        model = build_context_model(snapshot_text)
        prompt_payload = trim_for_llm(
            model, task="Click Playwright Python link", max_sections=2, max_items=5, max_actions=6
        )

        print(prompt_payload)
