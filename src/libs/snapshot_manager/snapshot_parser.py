from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------- Regex helpers ----------
LINE_RE = re.compile(r"^(?P<indent>\s*)-\s+(?P<body>.*)$")
ROLE_RE = re.compile(r"^(?P<role>[a-zA-Z_]+)\b")
NAME_RE = re.compile(r"\"(?P<name>.*?)\"")
REF_RE = re.compile(r"\[ref=(?P<ref>e\d+)\]")
DISABLED_RE = re.compile(r"\[disabled\]")
URL_RE = re.compile(r"^/url:\s*(?P<url>\S+)\s*$")

# text nodes show like: - text: foo
TEXT_KV_RE = re.compile(r"^text:\s*(?P<text>.*)$")

# ---------- Utilities ----------
INTERACTIVE_ROLES = {
    "button",
    "link",
    "combobox",
    "textbox",
    "searchbox",
    "checkbox",
    "radio",
    "option",
    "menuitem",
    "tab",
}

LANDMARK_ROLES = {"main", "navigation", "contentinfo"}

REPEATER_ITEM_ROLES = {"row", "listitem", "group"}  # generic, but works surprisingly often
HEADING_ROLE = "heading"


# ---------- Model ----------
@dataclass
class Node:
    raw: str
    indent: int
    role: str = "unknown"
    name: str | None = None
    ref: str | None = None
    disabled: bool = False
    attrs: dict[str, any] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)

    def add_child(self, n: Node) -> None:
        self.children.append(n)


def parse_snapshot(snapshot_text: str) -> Node:
    """
    Parse the indentation-based YAML-ish snapshot into a tree of Nodes.
    Treat "- /url: ..." and "- text: ..." as attribute children to the nearest parent.
    """
    root = Node(raw="ROOT", indent=-1, role="root")
    stack: list[Node] = [root]

    for line in snapshot_text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue

        indent = len(m.group("indent"))
        body = m.group("body").strip()

        # Attribute lines (url/text) are represented as their own nodes in the snapshot.
        # We'll store them as attrs on the nearest parent node.
        urlm = URL_RE.match(body)
        if urlm:
            # attach to current top
            stack[-1].attrs["url"] = urlm.group("url")
            continue

        textm = TEXT_KV_RE.match(body)
        if textm:
            # store "text" as child-like context on parent
            stack[-1].attrs.setdefault("texts", []).append(textm.group("text"))
            continue

        # Create a normal node
        role = ROLE_RE.match(body).group("role") if ROLE_RE.match(body) else "unknown"
        name = NAME_RE.search(body).group("name") if NAME_RE.search(body) else None
        ref = REF_RE.search(body).group("ref") if REF_RE.search(body) else None
        disabled = bool(DISABLED_RE.search(body))

        node = Node(raw=body, indent=indent, role=role, name=name, ref=ref, disabled=disabled)

        # Adjust stack by indentation
        while stack and indent <= stack[-1].indent:
            stack.pop()

        # Attach
        stack[-1].add_child(node)
        stack.append(node)

    return root


def iter_nodes(root: Node) -> list[Node]:
    out: list[Node] = []
    stack = [root]
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(reversed(n.children))
    return out


def ancestors_with_context(root: Node) -> dict[int, list[Node]]:
    """
    Build parent pointers & ancestor chains by walking.
    Return mapping of id(node) -> list of ancestors (root..parent).
    """
    parent: dict[int, Node] = {}
    chains: dict[int, list[Node]] = {id(root): []}
    stack: list[Node] = [root]

    while stack:
        n = stack.pop()
        for c in n.children:
            parent[id(c)] = n
            chains[id(c)] = chains[id(n)] + [n]
            stack.append(c)
    return chains


def first_salient_text(container: Node, max_len: int = 80) -> str:
    """
    Generic item_key: first heading/link name, else first text chunk, else role+ref.
    """
    for n in iter_nodes(container):
        if n.role in ("heading", "link") and n.name:
            return n.name[:max_len]
        # some snapshots store text in attrs
        texts = n.attrs.get("texts")
        if texts:
            t = " ".join(texts).strip()
            if t:
                return t[:max_len]
        if n.role == "emphasis" and n.attrs.get("texts"):
            t = " ".join(n.attrs["texts"]).strip()
            if t:
                return t[:max_len]
    # fallback
    return f"{container.role}:{container.ref or 'no-ref'}"
