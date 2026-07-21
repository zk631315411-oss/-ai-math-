# Diagnosis V1 Archive

## Status

Diagnosis V1 is archived and must not be restored to the runtime path. Its source is retained under `app/legacy/diagnosis_v1/` for historical audit, migration analysis, and comparison with V2.

## Archived Design

```text
chat history
  -> one mixed diagnostic LLM prompt
  -> concept stages + 15-dimension deltas + weak-node suggestion
  -> direct updates to knowledge_stages and math_profiles
```

This design mixed immediate QA interpretation with long-term state estimation. It could infer ability from AI answers, use one event to update a 15-dimension profile, and bypass a durable evidence ledger.

## V2 Replacement

```text
qa_turn_records / exercise_attempts
  -> source-specific scorers
  -> StageObservation / DimensionObservation
  -> diagnostic_evidence
  -> deterministic Stage or five-event dimension projection
```

Compatibility imports may remain temporarily, but V1 direct profile writes are disabled. Historical profile values are retained as `legacy_v1` baselines; no historical V1 event is replayed through V2 automatically.
