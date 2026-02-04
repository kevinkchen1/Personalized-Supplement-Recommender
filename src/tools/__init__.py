"""
Components package for entity extraction and normalization.

This package contains modular components for processing patient health data:
- entity_extractor: Extract entities from natural language (Phase 1)
- entity_normalizer: Normalize entities to database IDs (Phase 2)
"""

from .entity_extractor import (
    extract_entities_from_text,
    process_patient_profile
)

from .entity_normalizer import (
    normalize_medication_to_database,
    normalize_supplement_to_database,
    correct_patient_profile_data
)

__all__ = [
    'extract_entities_from_text',
    'process_patient_profile',
    'normalize_medication_to_database',
    'normalize_supplement_to_database',
    'correct_patient_profile_data'
]
