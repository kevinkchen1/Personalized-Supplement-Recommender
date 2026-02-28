"""
Connections - Module-level Singletons

Initializes GraphInterface and SchemaProvider once at import time.
All nodes that need database access import directly from here
rather than reading from state.

This avoids passing these objects through state entirely — they are
effectively singletons (one instance for the lifetime of the app).

Usage:
    from graph.connections import graph_interface, schema_provider
"""

import os
from dotenv import load_dotenv

from src.graph.graph_interface import GraphInterface
from src.graph.schema import SchemaProvider

load_dotenv()

# ── Initialize once at import time ──
graph_interface = GraphInterface(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", ""),
)

# SchemaProvider loads DB schema on init — runs once, cached for all nodes
schema_provider = SchemaProvider(graph_interface)