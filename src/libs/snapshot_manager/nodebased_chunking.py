from src.libs.snapshot_manager.snapshot_parser import Node, iter_nodes, parse_snapshot

CHUNK_ROOT_ROLES = {"main", "navigation", "contentinfo", "rowgroup", "list"}


def estimate_tokens(text: str) -> int:
    # rough estimate: ~4 chars/token, but words is fine as a heuristic
    return max(1, len(text) // 4)


def serialize_subtree(node: Node, max_lines: int = 5000) -> str:
    """
    Serialize subtree back to a compact text form (still hierarchical).
    You can tune this to include only certain roles if needed.
    """
    lines: list[str] = []
    stack: list[tuple[Node, int]] = [(node, 0)]
    while stack and len(lines) < max_lines:
        n, depth = stack.pop()
        name_part = f' "{n.name}"' if n.name else ""
        ref_part = f" [ref={n.ref}]" if n.ref else ""
        dis_part = " [disabled]" if n.disabled else ""
        url_part = f" /url={n.attrs.get('url')}" if "url" in n.attrs else ""
        lines.append(f"{'  ' * depth}- {n.role}{name_part}{ref_part}{dis_part}{url_part}")
        for c in reversed(n.children):
            stack.append((c, depth + 1))
    return "\n".join(lines)


def find_chunk_roots(root: Node) -> list[Node]:
    roots: list[Node] = []
    for n in iter_nodes(root):
        if n.role in CHUNK_ROOT_ROLES and n is not root:
            roots.append(n)

    # Prefer top-level landmarks first (main/nav/footer), then inner repeaters
    def rank(n: Node) -> int:
        if n.role in ("main", "navigation", "contentinfo"):
            return 0
        return 1

    return sorted(roots, key=rank)


def make_chunks(snapshot_text: str, max_tokens_per_chunk: int = 2000) -> list[dict[str, any]]:
    root = parse_snapshot(snapshot_text)
    chunk_roots = find_chunk_roots(root)

    chunks: list[dict[str, any]] = []
    for idx, cr in enumerate(chunk_roots):
        text = serialize_subtree(cr)
        if estimate_tokens(text) <= max_tokens_per_chunk:
            chunks.append({"chunk_id": f"ch{idx}", "root_role": cr.role, "text": text})
        else:
            # If a subtree is too big, split by its children (generic fallback)
            for j, child in enumerate(cr.children):
                child_text = serialize_subtree(child)
                if estimate_tokens(child_text) <= max_tokens_per_chunk:
                    chunks.append(
                        {
                            "chunk_id": f"ch{idx}_{j}",
                            "root_role": f"{cr.role}:{child.role}",
                            "text": child_text,
                        }
                    )
                else:
                    # last resort: hard-slice text (still better than failing)
                    chunks.append(
                        {
                            "chunk_id": f"ch{idx}_{j}_slice",
                            "root_role": f"{cr.role}:{child.role}",
                            "text": child_text[: max_tokens_per_chunk * 4],
                        }
                    )
    return chunks


def stage_a_prompt(task: str, chunk: dict[str, any]) -> dict[str, any]:
    return {
        "task": task,
        "chunk_id": chunk["chunk_id"],
        "chunk_root": chunk["root_role"],
        "chunk_text": chunk["text"],
        "instructions": (
            "Return up to 5 candidate actions that best match the task.\n"
            "Each candidate must include: ref, role, name(if any), url(if any), confidence 0..1, why.\n"
            "If none found, return empty candidates."
        ),
    }


def stage_b_prompt(task: str, all_candidates: list[dict[str, any]]) -> dict[str, any]:
    return {
        "task": task,
        "candidates": all_candidates,
        "instructions": (
            "Pick the single best candidate for the task.\n"
            "Return: {pick_ref, why}.\n"
            "If ambiguous, return top 2 refs and ask to expand a specific chunk."
        ),
    }
