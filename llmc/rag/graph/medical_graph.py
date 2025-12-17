"""
Clinical Knowledge Graph Builder and Querier

Builds and queries a medical knowledge graph with clinical relationships.
Supports edge types: TREATED_BY, MONITORED_BY, CONTRAINDICATES, ADVERSE_EVENT
Persists graph in SQLite database.
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
import json
from datetime import datetime

from .edge import GraphEdge
from .edge_types import EdgeType
from ..relation.clinical_re import ClinicalRelation, ClinicalRelationExtractor


@dataclass
class MedicalNode:
    """Represents a node in the medical knowledge graph."""
    node_id: str
    name: str
    node_type: str  # "condition", "drug", "test", "symptom", "procedure"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MedicalGraph:
    """Clinical knowledge graph with SQLite persistence."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with required tables."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Create nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                node_type TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create edges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes (node_id),
                FOREIGN KEY (target_id) REFERENCES nodes (node_id)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type)")
        
        self.conn.commit()
    
    def add_node(self, node: MedicalNode) -> bool:
        """Add a node to the graph."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO nodes (node_id, name, node_type, metadata) VALUES (?, ?, ?, ?)",
                (node.node_id, node.name, node.node_type, json.dumps(node.metadata))
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
    
    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType, 
                 confidence: float = 1.0, metadata: Dict[str, Any] = None) -> bool:
        """Add an edge to the graph."""
        if metadata is None:
            metadata = {}
        
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO edges (source_id, target_id, edge_type, confidence, metadata) 
                   VALUES (?, ?, ?, ?, ?)""",
                (source_id, target_id, edge_type.value, confidence, json.dumps(metadata))
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
    
    def add_relation(self, relation: ClinicalRelation) -> bool:
        """Add a clinical relation to the graph."""
        # Ensure source and target nodes exist
        source_node = MedicalNode(
            node_id=f"condition:{relation.source_entity.lower().replace(' ', '_')}",
            name=relation.source_entity,
            node_type="condition"
        )
        target_node = MedicalNode(
            node_id=f"drug:{relation.target_entity.lower().replace(' ', '_')}",
            name=relation.target_entity,
            node_type="drug"
        )
        
        # Adjust node types based on edge type
        if relation.edge_type == EdgeType.MONITORED_BY:
            target_node.node_type = "test"
        elif relation.edge_type == EdgeType.ADVERSE_EVENT:
            source_node.node_type = "drug"
            target_node.node_type = "symptom"
        
        self.add_node(source_node)
        self.add_node(target_node)
        
        # Add edge
        return self.add_edge(
            source_id=source_node.node_id,
            target_id=target_node.node_id,
            edge_type=relation.edge_type,
            confidence=relation.confidence,
            metadata={
                "context": relation.context,
                "matched_pattern": relation.matched_pattern
            }
        )
    
    def get_treatments(self, condition: str) -> List[Dict[str, Any]]:
        """Get medications that treat a condition."""
        condition_id = f"condition:{condition.lower().replace(' ', '_')}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.name, n.node_type, e.confidence, e.metadata
            FROM edges e
            JOIN nodes n ON e.target_id = n.node_id
            WHERE e.source_id = ? AND e.edge_type = ?
            ORDER BY e.confidence DESC
        """, (condition_id, EdgeType.TREATED_BY.value))
        
        results = []
        for row in cursor.fetchall():
            name, node_type, confidence, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            results.append({
                "name": name,
                "type": node_type,
                "confidence": confidence,
                "metadata": metadata
            })
        return results
    
    def get_contraindications(self, drug: str) -> List[Dict[str, Any]]:
        """Get conditions that are contraindicated for a drug."""
        drug_id = f"drug:{drug.lower().replace(' ', '_')}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.name, n.node_type, e.confidence, e.metadata
            FROM edges e
            JOIN nodes n ON e.target_id = n.node_id
            WHERE e.source_id = ? AND e.edge_type = ?
            ORDER BY e.confidence DESC
        """, (drug_id, EdgeType.CONTRAINDICATES.value))
        
        results = []
        for row in cursor.fetchall():
            name, node_type, confidence, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            results.append({
                "name": name,
                "type": node_type,
                "confidence": confidence,
                "metadata": metadata
            })
        return results
    
    def get_adverse_events(self, drug: str, confidence_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Get adverse events for a drug with confidence threshold."""
        drug_id = f"drug:{drug.lower().replace(' ', '_')}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.name, n.node_type, e.confidence, e.metadata
            FROM edges e
            JOIN nodes n ON e.target_id = n.node_id
            WHERE e.source_id = ? AND e.edge_type = ? AND e.confidence >= ?
            ORDER BY e.confidence DESC
        """, (drug_id, EdgeType.ADVERSE_EVENT.value, confidence_threshold))
        
        results = []
        for row in cursor.fetchall():
            name, node_type, confidence, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            results.append({
                "name": name,
                "type": node_type,
                "confidence": confidence,
                "metadata": metadata
            })
        return results
    
    def get_monitoring_tests(self, condition: str) -> List[Dict[str, Any]]:
        """Get tests used to monitor a condition."""
        condition_id = f"condition:{condition.lower().replace(' ', '_')}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.name, n.node_type, e.confidence, e.metadata
            FROM edges e
            JOIN nodes n ON e.target_id = n.node_id
            WHERE e.source_id = ? AND e.edge_type = ?
            ORDER BY e.confidence DESC
        """, (condition_id, EdgeType.MONITORED_BY.value))
        
        results = []
        for row in cursor.fetchall():
            name, node_type, confidence, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            results.append({
                "name": name,
                "type": node_type,
                "confidence": confidence,
                "metadata": metadata
            })
        return results
    
    def build_from_relations(self, relations: List[ClinicalRelation]) -> int:
        """Build graph from a list of clinical relations."""
        count = 0
        for relation in relations:
            if self.add_relation(relation):
                count += 1
        return count
    
    def build_from_texts(self, texts: List[str], confidence_threshold: float = 0.7) -> int:
        """Build graph by extracting relations from texts."""
        extractor = ClinicalRelationExtractor(confidence_threshold=confidence_threshold)
        relations = extractor.extract_from_documents(texts)
        return self.build_from_relations(relations)
    
    def get_node_count(self) -> int:
        """Get total number of nodes in the graph."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes")
        return cursor.fetchone()[0]
    
    def get_edge_count(self) -> int:
        """Get total number of edges in the graph."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM edges")
        return cursor.fetchone()[0]
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_medical_graph(db_path: Path) -> MedicalGraph:
    """Factory function to create a medical graph."""
    return MedicalGraph(db_path)
