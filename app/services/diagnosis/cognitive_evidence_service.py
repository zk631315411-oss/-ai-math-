"""Disabled Diagnosis V1 compatibility entrypoint.

V2 persists evidence only through ``diagnostic_evidence`` and its projectors.
The archived V1 helper directly changed confidence and is intentionally blocked.
"""

from app.services.diagnosis.contracts import CognitiveEvidence


def persist_evidence_items(evidence_items: list[CognitiveEvidence], max_items_per_concept: int = 20) -> None:
    raise RuntimeError(
        "Diagnosis V1 evidence persistence is archived; use the V2 evidence ledger and projectors."
    )
