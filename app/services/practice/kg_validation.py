"""Hard KG boundary checks for reviewed textbook practice assets."""

from __future__ import annotations

from app.textbooks import canonical_textbook_id, section_node_id


def verify_item_kg_mapping(item: dict) -> list[str]:
    errors: list[str] = []
    try:
        textbook_id = canonical_textbook_id(item.get("textbook_id", ""))
        section_id = section_node_id(textbook_id, item.get("sequence_id", ""))
    except ValueError:
        return ["invalid_textbook_id"]

    chapter_prefix = ":".join(section_id.split(":")[:2])
    primary = str(item.get("primary_concept_id") or "")
    secondary = [str(value) for value in item.get("secondary_concept_ids") or [] if value]
    prerequisites = [str(value) for value in item.get("prerequisite_concept_ids") or [] if value]
    expected = list(dict.fromkeys([primary, *secondary, *prerequisites]))
    if not primary:
        return ["missing_kg_mapping"]

    from app.db.kg_v44 import nodes_by_ids_in_scope, one_hop_relations_in_book

    resolved = nodes_by_ids_in_scope(textbook_id, chapter_prefix, expected)
    resolved_ids = [str(row.get("node_id") or "") for row in resolved]
    if len(resolved_ids) != len(set(resolved_ids)):
        errors.append("ambiguous_kg_mapping")
    missing = sorted(set(expected) - set(resolved_ids))
    if missing:
        errors.append("kg_nodes_outside_textbook_chapter:" + ",".join(missing))
    if prerequisites and primary in resolved_ids:
        relations = one_hop_relations_in_book(textbook_id, prerequisites, [primary])
        linked = {str(row.get("source_node_id") or "") for row in relations}
        unlinked = sorted(set(prerequisites) - linked)
        if unlinked:
            errors.append("prerequisites_not_one_hop:" + ",".join(unlinked))
    return errors
