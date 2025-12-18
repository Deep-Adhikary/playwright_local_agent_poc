from typing import TypedDict

from snapshot_parser import *


class Action(TypedDict, total=False):
    action_id: str
    role: str
    name: str
    ref: str
    url: str
    disabled: bool


class Item(TypedDict, total=False):
    item_id: str
    item_key: str
    container_role: str
    actions: List[Action]


class Section(TypedDict, total=False):
    section_id: str
    landmark: str
    heading_path: List[str]
    items: List[Item]


def heading_path_for(ancs: List[Node]) -> List[str]:
    # collect headings from ancestors; keep last few
    hp = [a.name for a in ancs if a.role == HEADING_ROLE and a.name]
    # de-noise: keep last 3 headings
    return hp[-3:]


def nearest_landmark(ancs: List[Node]) -> Optional[Node]:
    for a in reversed(ancs):
        if a.role in LANDMARK_ROLES:
            return a
    return None


def nearest_item_container(ancs: List[Node]) -> Optional[Node]:
    # nearest row/listitem/group ancestor
    for a in reversed(ancs):
        if a.role in REPEATER_ITEM_ROLES:
            return a
    return None


def build_context_model(snapshot_text: str) -> Dict[str, Any]:
    root = parse_snapshot(snapshot_text)
    chains = ancestors_with_context(root)

    # key: (section_id, item_node_id) -> item
    sections: Dict[str, Section] = {}
    item_map: Dict[Tuple[str, int], Item] = {}

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
    model: Dict[str, Any],
    task: str,
    max_sections: int = 3,
    max_items: int = 8,
    max_actions: int = 8,
) -> Dict[str, Any]:
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

    trimmed_sections: List[Section] = []
    for sec in scored_sections:
        items = sec.get("items", [])
        # score items by item_key
        scored_items = sorted(
            items, key=lambda it: score_text(it.get("item_key", "")), reverse=True
        )[:max_items]

        new_items: List[Item] = []
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
    with open("output.format.md") as f:
        snapshot_text = f.read()
        model = build_context_model(snapshot_text)
        prompt_payload = trim_for_llm(
            model, task="Click Playwright Python link", max_sections=2, max_items=5, max_actions=6
        )

        print(prompt_payload)
