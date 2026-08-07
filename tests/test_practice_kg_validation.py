from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.practice.kg_validation import verify_item_kg_mapping


def _item() -> dict:
    return {
        "textbook_id": "gaodai_shang",
        "sequence_id": "V1-C03-S05",
        "primary_concept_id": "rank",
        "secondary_concept_ids": ["minor"],
        "prerequisite_concept_ids": ["row-reduction"],
    }


class PracticeKGValidationTests(unittest.TestCase):
    @patch("app.db.kg_v44.one_hop_relations_in_book")
    @patch("app.db.kg_v44.nodes_by_ids_in_scope")
    def test_verified_scoped_nodes_and_one_hop_prerequisite_pass(
        self, nodes_by_ids, one_hop
    ) -> None:
        nodes_by_ids.return_value = [
            {"node_id": "rank"},
            {"node_id": "minor"},
            {"node_id": "row-reduction"},
        ]
        one_hop.return_value = [
            {"source_node_id": "row-reduction", "target_node_id": "rank"}
        ]
        self.assertEqual(verify_item_kg_mapping(_item()), [])
        nodes_by_ids.assert_called_once_with(
            "gaodai_shang", "gaodai_shang:C03", ["rank", "minor", "row-reduction"]
        )

    @patch("app.db.kg_v44.one_hop_relations_in_book", return_value=[])
    @patch("app.db.kg_v44.nodes_by_ids_in_scope")
    def test_cross_scope_and_unlinked_prerequisite_are_quarantined(
        self, nodes_by_ids, _one_hop
    ) -> None:
        nodes_by_ids.return_value = [{"node_id": "rank"}, {"node_id": "row-reduction"}]
        errors = verify_item_kg_mapping(_item())
        self.assertIn("kg_nodes_outside_textbook_chapter:minor", errors)
        self.assertIn("prerequisites_not_one_hop:row-reduction", errors)

    def test_legacy_textbook_id_is_rejected_before_neo4j(self) -> None:
        item = _item()
        item["textbook_id"] = "高代上-丘维声"
        self.assertEqual(verify_item_kg_mapping(item), ["invalid_textbook_id"])


if __name__ == "__main__":
    unittest.main()
