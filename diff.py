from typing import Dict, Any, Optional

def compute_diff(old_rec: Dict[str, Any], new_rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compare two citation records of the form:
      {'type': str, 'citation_key': str, 'fields': { key: value, ... }}
    Returns None if no changes, otherwise a dict with keys:
      - 'type_changed': {'from': str, 'to': str} | None
      - 'added': { field: value, ... }
      - 'removed': { field: value, ... }
      - 'modified': { field: {'from': v1, 'to': v2}, ... }
    """
    changes = {'type_changed': None, 'added': {}, 'removed': {}, 'modified': {}}

    old_fields = (old_rec.get('fields') or {}).copy()
    new_fields = (new_rec.get('fields') or {}).copy()

    # Type changes
    old_type = (old_rec.get('type') or '')
    new_type = (new_rec.get('type') or '')
    if old_type != new_type:
        changes['type_changed'] = {'from': old_type, 'to': new_type}

    # Added / modified
    for k, v_new in new_fields.items():
        if k not in old_fields:
            changes['added'][k] = v_new
        else:
            v_old = old_fields[k]
            if v_old != v_new:
                changes['modified'][k] = {'from': v_old, 'to': v_new}

    # Removed
    for k, v_old in old_fields.items():
        if k not in new_fields:
            changes['removed'][k] = v_old

    if not changes['type_changed'] and not changes['added'] and not changes['removed'] and not changes['modified']:
        return None
    return changes

def format_changes_for_log(citation_key: str, changes: Dict[str, Any]) -> str:
    lines = [f"Changes for {citation_key}:"]
    if changes.get('type_changed'):
        tc = changes['type_changed']
        lines.append(f"  type: {tc['from']}  ->  {tc['to']}")
    if changes.get('added'):
        lines.append("  added fields:")
        for k, v in changes['added'].items():
            lines.append(f"    + {k}: {v}")
    if changes.get('removed'):
        lines.append("  removed fields:")
        for k, v in changes['removed'].items():
            lines.append(f"    - {k}: {v}")
    if changes.get('modified'):
        lines.append("  modified fields:")
        for k, pair in changes['modified'].items():
            lines.append(f"    * {k}: {pair['from']}  ->  {pair['to']}")
    return "\n".join(lines)

def format_changes_markdown(citation_key: str, old_rec: Dict[str, Any], new_rec: Dict[str, Any], changes: Dict[str, Any]) -> str:
    title = (old_rec.get('fields') or {}).get('title') or (new_rec.get('fields') or {}).get('title') or "(no title)"
    md = [f"### `{citation_key}` — {title}"]
    if changes.get('type_changed'):
        tc = changes['type_changed']
        md.append(f"- **Type:** `{tc['from']}` → `{tc['to']}`")
    if changes.get('added'):
        md.append("- **Added fields:**")
        for k, v in changes['added'].items():
            md.append(f"  - `{k}`: `{v}`")
    if changes.get('removed'):
        md.append("- **Removed fields:**")
        for k, v in changes['removed'].items():
            md.append(f"  - `{k}`: `{v}`")
    if changes.get('modified'):
        md.append("- **Modified fields:**")
        for k, pair in changes['modified'].items():
            md.append(f"  - `{k}`: `{pair['from']}` → `{pair['to']}`")
    md.append("")  # trailing newline
    return "\n".join(md)
