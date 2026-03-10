#!/usr/bin/env python3
def _join(items, max_items=6):
    items = [str(x).strip() for x in items if str(x).strip()]
    if len(items) > max_items:
        return ", ".join(items[:max_items]) + f", +{len(items)-max_items} more"
    return ", ".join(items)

def format_brief(pair, tf, direction, score, tags=None, notes=None):
    tags  = tags  or []
    notes = notes or []
    tags_str  = _join(tags, 6)
    notes_str = _join(notes, 6)
    right = "Reason: " + (tags_str if tags_str else "—")
    if notes_str:
        right += " | " + notes_str
    return f"🔎 {right}"
