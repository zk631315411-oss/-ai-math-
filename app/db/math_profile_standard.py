"""Deprecated import bridge for archived Diagnosis V1 profile definitions.

Diagnosis V2 uses source-specific observations and deterministic projectors.
The archived mixed Prompt must not be used by runtime code.
"""

from app.legacy.diagnosis_v1.math_profile_standard import *  # noqa: F403
