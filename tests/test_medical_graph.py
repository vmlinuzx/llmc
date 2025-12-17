"""
Unit tests for Clinical Knowledge Graph and Relations.
"""

from pathlib import Path
import tempfile

import pytest

from llmc.rag.graph.edge_types import EdgeType as GraphEdgeType
from llmc.rag.graph.medical_graph import MedicalGraph, MedicalNode
from llmc.rag.relation.clinical_re import (
    ClinicalRelation,
    ClinicalRelationExtractor,
    EdgeType,
)


def test_edge_type_enum():
    """Test that clinical edge types are present in the enum."""
    assert hasattr(GraphEdgeType, "TREATED_BY")
    assert hasattr(GraphEdgeType, "MONITORED_BY")
    assert hasattr(GraphEdgeType, "CONTRAINDICATES")
    assert hasattr(GraphEdgeType, "ADVERSE_EVENT")

    assert GraphEdgeType.TREATED_BY.value == "TREATED_BY"
    assert GraphEdgeType.MONITORED_BY.value == "MONITORED_BY"
    assert GraphEdgeType.CONTRAINDICATES.value == "CONTRAINDICATES"
    assert GraphEdgeType.ADVERSE_EVENT.value == "ADVERSE_EVENT"


def test_clinical_relation_extractor():
    """Test clinical relation extraction from text."""
    extractor = ClinicalRelationExtractor(confidence_threshold=0.5)

    text = "Hypertension is treated with Lisinopril. Diabetes is monitored with HbA1c test."
    relations = extractor.extract_from_text(text)

    assert len(relations) >= 2

    # Check for TREATED_BY relation
    treated_relations = [r for r in relations if r.edge_type == EdgeType.TREATED_BY]
    assert len(treated_relations) > 0

    # Check for MONITORED_BY relation
    monitored_relations = [r for r in relations if r.edge_type == EdgeType.MONITORED_BY]
    assert len(monitored_relations) > 0


def test_medical_graph_creation():
    """Test medical graph creation and basic operations."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        # Test adding nodes
        node1 = MedicalNode("condition:hypertension", "Hypertension", "condition")
        node2 = MedicalNode("drug:lisinopril", "Lisinopril", "drug")

        assert graph.add_node(node1) == True
        assert graph.add_node(node2) == True

        # Test adding edge
        assert (
            graph.add_edge(
                source_id="condition:hypertension",
                target_id="drug:lisinopril",
                edge_type=EdgeType.TREATED_BY,
                confidence=0.9,
            )
            == True
        )

        # Test query functions
        treatments = graph.get_treatments("Hypertension")
        assert len(treatments) == 1
        assert treatments[0]["name"] == "Lisinopril"

        # Test counts
        assert graph.get_node_count() == 2
        assert graph.get_edge_count() == 1

    finally:
        db_path.unlink(missing_ok=True)


def test_get_treatments():
    """Test get_treatments function."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        # Add test data
        graph.add_node(MedicalNode("condition:diabetes", "Diabetes", "condition"))
        graph.add_node(MedicalNode("drug:metformin", "Metformin", "drug"))
        graph.add_node(MedicalNode("drug:insulin", "Insulin", "drug"))

        graph.add_edge("condition:diabetes", "drug:metformin", EdgeType.TREATED_BY, 0.9)
        graph.add_edge("condition:diabetes", "drug:insulin", EdgeType.TREATED_BY, 0.8)

        treatments = graph.get_treatments("Diabetes")
        assert len(treatments) == 2

        # Should be ordered by confidence
        assert treatments[0]["name"] == "Metformin"
        assert treatments[0]["confidence"] == 0.9
        assert treatments[1]["name"] == "Insulin"
        assert treatments[1]["confidence"] == 0.8

    finally:
        db_path.unlink(missing_ok=True)


def test_get_contraindications():
    """Test get_contraindications function."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        # Add test data
        graph.add_node(MedicalNode("drug:warfarin", "Warfarin", "drug"))
        graph.add_node(MedicalNode("condition:pregnancy", "Pregnancy", "condition"))

        graph.add_edge(
            "drug:warfarin", "condition:pregnancy", EdgeType.CONTRAINDICATES, 0.95
        )

        contraindications = graph.get_contraindications("Warfarin")
        assert len(contraindications) == 1
        assert contraindications[0]["name"] == "Pregnancy"

    finally:
        db_path.unlink(missing_ok=True)


def test_get_adverse_events_with_threshold():
    """Test get_adverse_events function with confidence threshold."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        # Add test data
        graph.add_node(MedicalNode("drug:aspirin", "Aspirin", "drug"))
        graph.add_node(MedicalNode("symptom:bleeding", "Bleeding", "symptom"))
        graph.add_node(MedicalNode("symptom:nausea", "Nausea", "symptom"))

        graph.add_edge("drug:aspirin", "symptom:bleeding", EdgeType.ADVERSE_EVENT, 0.8)
        graph.add_edge("drug:aspirin", "symptom:nausea", EdgeType.ADVERSE_EVENT, 0.6)

        # Test with threshold 0.7
        adverse_events = graph.get_adverse_events("Aspirin", confidence_threshold=0.7)
        assert len(adverse_events) == 1
        assert adverse_events[0]["name"] == "Bleeding"

        # Test with threshold 0.5
        adverse_events = graph.get_adverse_events("Aspirin", confidence_threshold=0.5)
        assert len(adverse_events) == 2

    finally:
        db_path.unlink(missing_ok=True)


def test_build_from_relations():
    """Test building graph from clinical relations."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        # Create test relations
        relations = [
            ClinicalRelation(
                source_entity="Hypertension",
                target_entity="Lisinopril",
                edge_type=EdgeType.TREATED_BY,
                confidence=0.9,
                context="Hypertension is treated with Lisinopril",
                matched_pattern="test pattern",
            ),
            ClinicalRelation(
                source_entity="Diabetes",
                target_entity="HbA1c",
                edge_type=EdgeType.MONITORED_BY,
                confidence=0.8,
                context="Diabetes is monitored with HbA1c",
                matched_pattern="test pattern",
            ),
        ]

        count = graph.build_from_relations(relations)
        assert count == 2

        # Verify nodes were created
        assert graph.get_node_count() == 4  # 2 conditions + 1 drug + 1 test
        assert graph.get_edge_count() == 2

    finally:
        db_path.unlink(missing_ok=True)


def test_build_from_texts():
    """Test building graph directly from texts."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        graph = MedicalGraph(db_path)

        texts = [
            "Hypertension is treated with Lisinopril.",
            "Diabetes is monitored with HbA1c test.",
            "Warfarin is contraindicated in pregnancy.",
            "Aspirin may cause bleeding.",
        ]

        count = graph.build_from_texts(texts, confidence_threshold=0.5)
        assert count > 0

        # Verify we can query the built graph
        treatments = graph.get_treatments("Hypertension")
        assert len(treatments) > 0

    finally:
        db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
