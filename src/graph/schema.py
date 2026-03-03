"""
Schema - Database Schema Provider

Loads and exposes the Neo4j knowledge graph schema for use by the
entity_normalizer agent when generating Cypher queries dynamically.

Provides:
- Node labels and their properties
- Relationship types and their properties
- Sample property values per node type
- A formatted string representation for LLM prompts

Core purpose: Give entity_normalizer's LLM accurate database context
so it generates valid Cypher rather than hallucinating node/property names.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SchemaProvider:
    """
    Loads and caches the knowledge graph schema from Neo4j.

    Used by entity_normalizer to ground LLM-generated Cypher
    in the actual database structure.
    """

    def __init__(self, graph_interface):
        """
        Initialize and immediately load schema from database.

        Args:
            graph_interface: GraphInterface instance (Neo4j connection)
        """
        self.graph = graph_interface
        self.schema: Dict[str, Any] = {}
        self.property_values: Dict[str, List[Any]] = {}
        self._load()

    def _load(self):
        """Load schema, sample property values, and relationship directions from Neo4j."""
        try:
            # Load node labels, relationship types, and properties
            self.schema = self.graph.get_schema_info()

            # Load relationship directionality — which node types each rel connects
            # Critical for LLMs to reason about valid paths without hallucinating
            self.relationship_directions: List[Dict[str, str]] = (
                self.graph.get_relationship_directions()
            )

            # Load sample values for each node property
            for label in self.schema.get("node_labels", []):
                props = self.schema.get("node_properties", {}).get(label, [])
                for prop in props:
                    key = f"{label}.{prop}"
                    if key not in self.property_values:
                        values = self.graph.get_property_values(label, prop, limit=5)
                        values = [v for v in values if v and str(v).strip()]
                        if values:
                            self.property_values[key] = values

            logger.info(
                f"✓ Schema loaded: "
                f"{len(self.schema.get('node_labels', []))} node types, "
                f"{len(self.schema.get('relationship_types', []))} relationship types, "
                f"{len(self.relationship_directions)} directed relationships"
            )

        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            raise

    def get_node_labels(self) -> List[str]:
        """Return all node labels in the graph."""
        return self.schema.get("node_labels", [])

    def get_relationship_types(self) -> List[str]:
        """Return all relationship types in the graph."""
        return self.schema.get("relationship_types", [])

    def get_node_properties(self, label: str) -> List[str]:
        """
        Return property names for a given node label.

        Args:
            label: Node label e.g. 'Drug', 'Supplement'

        Returns:
            List of property names e.g. ['drug_id', 'drug_name']
        """
        return self.schema.get("node_properties", {}).get(label, [])

    def get_sample_values(self, label: str, prop: str) -> List[Any]:
        """
        Return sample values for a node property.

        Args:
            label: Node label e.g. 'Drug'
            prop: Property name e.g. 'drug_name'

        Returns:
            List of sample values e.g. ['Warfarin', 'Metformin']
        """
        return self.property_values.get(f"{label}.{prop}", [])

    def to_prompt_string(self) -> str:
        """
        Format the schema as a string for injection into LLM prompts.

        Returns a compact, readable representation of:
        - All node types and their properties with sample values
        - All relationship types with source → target node types

        Example output:
            Node Types:
              Drug: drug_id, drug_name (e.g. Warfarin, Metformin)
              Supplement: supplement_id, supplement_name (e.g. Fish oil, Vitamin D)

            Relationships (source → target):
              SUPPLEMENT_INTERACTS_WITH : Supplement → Medication
              CONTAINS                  : Supplement → ActiveIngredient
              EQUIVALENT_TO             : ActiveIngredient → Drug
              INTERACTS_WITH            : Drug → Drug
        """
        lines = ["Node Types:"]

        for label in self.get_node_labels():
            props = self.get_node_properties(label)
            prop_parts = []

            for prop in props:
                samples = self.get_sample_values(label, prop)
                if samples:
                    sample_str = ", ".join(str(v) for v in samples[:5])
                    prop_parts.append(f"{prop} (e.g. {sample_str})")
                else:
                    prop_parts.append(prop)

            props_str = ", ".join(prop_parts) if prop_parts else "no properties"
            lines.append(f"  {label}: {props_str}")

        lines.append("")
        lines.append("Relationships (source → target):")

        # Find max rel_type length for alignment
        directions = getattr(self, 'relationship_directions', [])
        if directions:
            max_len = max(len(d['rel_type']) for d in directions)
            for d in directions:
                rel = d['rel_type'].ljust(max_len)
                lines.append(f"  {rel} : {d['from_label']} → {d['to_label']}")
        else:
            # Fallback — just list relationship names if directions failed to load
            for rel in self.get_relationship_types():
                lines.append(f"  {rel}")

        return "\n".join(lines)