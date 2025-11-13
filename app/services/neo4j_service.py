"""
NeuroscribeAI - Neo4j Knowledge Graph Service
Builds and queries clinical knowledge graphs from extracted facts
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.config import settings
from app.schemas import AtomicClinicalFact, EntityType

logger = logging.getLogger(__name__)


# =============================================================================
# Neo4j Connection Manager
# =============================================================================

class Neo4jConnection:
    """Manages Neo4j database connection with health checks"""

    def __init__(self):
        self.driver: Optional[Driver] = None
        self.uri = settings.neo4j_uri
        self.user = settings.neo4j_user
        self.password = settings.neo4j_password
        self.database = settings.neo4j_database
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info(f"✓ Neo4j connected successfully: {self.uri}")

        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            raise
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def get_session(self) -> Session:
        """Get a new Neo4j session"""
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        return self.driver.session(database=self.database)

    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def health_check(self) -> bool:
        """Check if Neo4j is accessible"""
        try:
            with self.get_session() as session:
                result = session.run("RETURN 1 as health")
                return result.single()["health"] == 1
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False


# Global connection instance
neo4j_connection = Neo4jConnection()


# =============================================================================
# Knowledge Graph Service
# =============================================================================

class Neo4jGraphService:
    """Service for building and querying clinical knowledge graphs"""

    def __init__(self):
        self.connection = neo4j_connection

    # =========================================================================
    # Graph Initialization & Indexing
    # =========================================================================

    def initialize_graph_schema(self):
        """Create indexes and constraints for optimal query performance"""
        with self.connection.get_session() as session:
            # Constraints for uniqueness
            constraints = [
                "CREATE CONSTRAINT patient_id_unique IF NOT EXISTS FOR (p:Patient) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT diagnosis_id_unique IF NOT EXISTS FOR (d:Diagnosis) REQUIRE d.id IS UNIQUE",
                "CREATE CONSTRAINT procedure_id_unique IF NOT EXISTS FOR (pr:Procedure) REQUIRE pr.id IS UNIQUE",
                "CREATE CONSTRAINT medication_id_unique IF NOT EXISTS FOR (m:Medication) REQUIRE m.id IS UNIQUE",
            ]

            # Indexes for query performance
            indexes = [
                "CREATE INDEX patient_mrn_idx IF NOT EXISTS FOR (p:Patient) ON (p.mrn)",
                "CREATE INDEX diagnosis_name_idx IF NOT EXISTS FOR (d:Diagnosis) ON (d.name)",
                "CREATE INDEX procedure_name_idx IF NOT EXISTS FOR (pr:Procedure) ON (pr.name)",
                "CREATE INDEX medication_name_idx IF NOT EXISTS FOR (m:Medication) ON (m.generic_name)",
                "CREATE INDEX lab_test_idx IF NOT EXISTS FOR (l:LabValue) ON (l.test_name)",
            ]

            # Full-text search indexes
            fulltext_indexes = [
                """CREATE FULLTEXT INDEX entity_fulltext_idx IF NOT EXISTS
                   FOR (n:Diagnosis|Procedure|Medication|Symptom)
                   ON EACH [n.name, n.extracted_text]""",
            ]

            try:
                for constraint in constraints:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint[:50]}...")

                for index in indexes:
                    session.run(index)
                    logger.info(f"Created index: {index[:50]}...")

                for ft_index in fulltext_indexes:
                    session.run(ft_index)
                    logger.info("Created fulltext index for entity search")

                logger.info("✓ Neo4j graph schema initialized successfully")

            except Exception as e:
                logger.error(f"Error initializing graph schema: {e}")
                raise

    # =========================================================================
    # Node Creation Methods
    # =========================================================================

    def create_patient_node(self, patient_data: Dict[str, Any]) -> str:
        """Create or update Patient node in graph"""
        with self.connection.get_session() as session:
            cypher = """
            MERGE (p:Patient {id: $id})
            SET p.mrn = $mrn,
                p.age = $age,
                p.sex = $sex,
                p.primary_diagnosis = $primary_diagnosis,
                p.updated_at = datetime($updated_at)
            RETURN elementId(p) as node_id
            """

            result = session.run(
                cypher,
                id=patient_data.get("id"),
                mrn=patient_data.get("mrn"),
                age=patient_data.get("age"),
                sex=patient_data.get("sex"),
                primary_diagnosis=patient_data.get("primary_diagnosis"),
                updated_at=patient_data.get("updated_at", datetime.now()).isoformat()
            )

            node_id = result.single()["node_id"]
            logger.info(f"Created/updated Patient node: {patient_data.get('mrn')}")
            return node_id

    def create_fact_node(self, fact: AtomicClinicalFact) -> Tuple[str, str]:
        """Create entity node from clinical fact"""
        with self.connection.get_session() as session:
            # Determine node label based on entity type
            label_map = {
                EntityType.DIAGNOSIS: "Diagnosis",
                EntityType.PROCEDURE: "Procedure",
                EntityType.MEDICATION: "Medication",
                EntityType.LAB_VALUE: "LabValue",
                EntityType.PHYSICAL_EXAM: "PhysicalExam",
                EntityType.IMAGING: "ImagingFinding",
                EntityType.IMAGING_FINDING: "ImagingFinding",
                EntityType.SYMPTOM: "Symptom",
                EntityType.VITAL_SIGN: "VitalSign"
            }

            label = label_map.get(fact.entity_type, "ClinicalFact")

            # Build properties dict
            properties = {
                "id": fact.id if hasattr(fact, 'id') else None,
                "name": fact.entity_name,
                "extracted_text": fact.extracted_text,
                "confidence": fact.confidence_score,
                "extraction_method": fact.extraction_method,
                "is_negated": fact.is_negated,
                "is_historical": fact.is_historical,
            }

            # Add type-specific properties
            if fact.anatomical_context:
                properties["laterality"] = fact.anatomical_context.get("laterality")
                properties["brain_region"] = fact.anatomical_context.get("brain_region")
                properties["size_mm"] = fact.anatomical_context.get("size_mm")

            if fact.medication_detail:
                properties["dose_value"] = fact.medication_detail.get("dose_value")
                properties["dose_unit"] = fact.medication_detail.get("dose_unit")
                properties["frequency"] = fact.medication_detail.get("frequency")

            if fact.temporal_context:
                properties["pod"] = fact.temporal_context.get("pod")
                properties["hospital_day"] = fact.temporal_context.get("hospital_day")

            # Create node
            cypher = f"""
            MERGE (e:{label} {{id: $id}})
            SET e += $properties
            RETURN elementId(e) as node_id, $id as fact_id
            """

            result = session.run(cypher, id=properties["id"], properties=properties)
            record = result.single()

            logger.info(f"Created {label} node: {fact.entity_name}")
            return record["node_id"], record["fact_id"]

    # =========================================================================
    # Relationship Creation
    # =========================================================================

    def create_patient_fact_relationship(
        self,
        patient_id: int,
        fact: AtomicClinicalFact,
        neo4j_node_id: str
    ):
        """Create relationship from Patient to entity node"""
        with self.connection.get_session() as session:
            # Relationship type based on entity type
            rel_type_map = {
                EntityType.DIAGNOSIS: "HAS_DIAGNOSIS",
                EntityType.PROCEDURE: "UNDERWENT_PROCEDURE",
                EntityType.MEDICATION: "TAKES_MEDICATION",
                EntityType.LAB_VALUE: "HAS_LAB",
                EntityType.PHYSICAL_EXAM: "HAS_EXAM",
                EntityType.IMAGING: "HAS_IMAGING",
                EntityType.SYMPTOM: "EXHIBITS_SYMPTOM"
            }

            rel_type = rel_type_map.get(fact.entity_type, "HAS_FACT")

            # Relationship properties
            rel_props = {
                "confidence": fact.confidence_score,
                "source_method": fact.extraction_method,
                "created_at": datetime.now().isoformat()
            }

            if fact.temporal_context:
                rel_props["pod"] = fact.temporal_context.get("pod")
                if fact.temporal_context.get("timestamp"):
                    rel_props["event_date"] = fact.temporal_context["timestamp"]

            # Create relationship
            cypher = f"""
            MATCH (p:Patient {{id: $patient_id}})
            MATCH (e) WHERE elementId(e) = $node_id
            MERGE (p)-[r:{rel_type}]->(e)
            SET r += $properties
            """

            session.run(
                cypher,
                patient_id=patient_id,
                node_id=neo4j_node_id,
                properties=rel_props
            )

            logger.info(f"Created relationship: Patient-[{rel_type}]->{{fact.entity_name}}")

    def infer_clinical_relationships(self, patient_id: int):
        """Infer logical relationships between clinical entities"""
        with self.connection.get_session() as session:
            # Infer Medication → Diagnosis (treatment) relationships
            cypher_med_diag = """
            MATCH (p:Patient {id: $patient_id})-[:TAKES_MEDICATION]->(m:Medication)
            MATCH (p)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            WHERE (
                (m.generic_name = 'dexamethasone' AND
                 (d.name CONTAINS 'glioblastoma' OR d.name CONTAINS 'edema'))
                OR
                (m.generic_name = 'levetiracetam' AND
                 (d.name CONTAINS 'glioblastoma' OR d.name CONTAINS 'seizure'))
                OR
                (m.generic_name = 'enoxaparin' AND
                 d.name CONTAINS 'craniotomy')
            )
            MERGE (m)-[r:PRESCRIBED_FOR]->(d)
            SET r.confidence = 0.9,
                r.indication = CASE m.generic_name
                    WHEN 'dexamethasone' THEN 'edema control'
                    WHEN 'levetiracetam' THEN 'seizure prophylaxis'
                    WHEN 'enoxaparin' THEN 'DVT prophylaxis'
                END,
                r.prophylaxis = (m.generic_name IN ['levetiracetam', 'enoxaparin'])
            """
            session.run(cypher_med_diag, patient_id=patient_id)

            # Infer Diagnosis → Procedure relationships
            cypher_diag_proc = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            MATCH (p)-[:UNDERWENT_PROCEDURE]->(proc:Procedure)
            WHERE d.brain_region IS NOT NULL
              AND proc.brain_region IS NOT NULL
              AND d.brain_region = proc.brain_region
            MERGE (d)-[r:INDICATED_PROCEDURE]->(proc)
            SET r.confidence = 0.85,
                r.anatomical_match = true
            """
            session.run(cypher_diag_proc, patient_id=patient_id)

            logger.info(f"Inferred clinical relationships for patient {patient_id}")

    def build_temporal_relationships(self, patient_id: int):
        """Create temporal BEFORE/AFTER relationships between facts"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (p:Patient {id: $patient_id})-[]->(e1)
            MATCH (p)-[]->(e2)
            WHERE e1 <> e2
              AND e1.pod IS NOT NULL
              AND e2.pod IS NOT NULL
              AND e1.pod < e2.pod
            MERGE (e1)-[r:TEMPORAL_BEFORE]->(e2)
            SET r.days_difference = e2.pod - e1.pod,
                r.same_patient = true
            """
            session.run(cypher, patient_id=patient_id)
            logger.info(f"Built temporal relationships for patient {patient_id}")

    # =========================================================================
    # Main Sync Method
    # =========================================================================

    def sync_patient_to_graph(
        self,
        patient_id: int,
        patient_data: Dict[str, Any],
        facts: List[AtomicClinicalFact]
    ) -> Dict[str, int]:
        """
        Complete sync of patient and all their facts to Neo4j graph

        Args:
            patient_id: PostgreSQL patient ID
            patient_data: Patient demographics
            facts: List of all patient's clinical facts

        Returns:
            Dict with sync statistics
        """
        logger.info(f"Starting graph sync for patient {patient_id} with {len(facts)} facts")

        stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": 0
        }

        try:
            # Step 1: Create Patient node
            patient_node_id = self.create_patient_node(patient_data)
            stats["nodes_created"] += 1

            # Step 2: Create entity nodes and relationships
            for fact in facts:
                try:
                    # Create entity node
                    neo4j_node_id, fact_id = self.create_fact_node(fact)
                    stats["nodes_created"] += 1

                    # Create Patient->Entity relationship
                    self.create_patient_fact_relationship(patient_id, fact, neo4j_node_id)
                    stats["relationships_created"] += 1

                except Exception as e:
                    logger.error(f"Error syncing fact {fact.entity_name}: {e}")
                    stats["errors"] += 1

            # Step 3: Infer clinical logic relationships
            self.infer_clinical_relationships(patient_id)
            stats["relationships_created"] += 10  # Approximate

            # Step 4: Build temporal relationships
            self.build_temporal_relationships(patient_id)
            stats["relationships_created"] += 5  # Approximate

            logger.info(f"✓ Graph sync complete: {stats['nodes_created']} nodes, "
                       f"{stats['relationships_created']} relationships, {stats['errors']} errors")

            return stats

        except Exception as e:
            logger.error(f"Graph sync failed for patient {patient_id}: {e}", exc_info=True)
            stats["errors"] += 1
            return stats

    # =========================================================================
    # Query Methods
    # =========================================================================

    def find_similar_patients(
        self,
        patient_mrn: str,
        min_shared_diagnoses: int = 2,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find patients with similar diagnoses and procedures"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (target:Patient {mrn: $target_mrn})-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            MATCH (similar:Patient)-[:HAS_DIAGNOSIS]->(d)
            WHERE similar <> target
            WITH similar, count(DISTINCT d) as shared_diagnoses
            WHERE shared_diagnoses >= $min_shared
            OPTIONAL MATCH (similar)-[:UNDERWENT_PROCEDURE]->(p:Procedure)
            OPTIONAL MATCH (target:Patient {mrn: $target_mrn})-[:UNDERWENT_PROCEDURE]->(p)
            WITH similar, shared_diagnoses, count(DISTINCT p) as shared_procedures
            RETURN similar.mrn as mrn,
                   similar.age as age,
                   similar.sex as sex,
                   similar.primary_diagnosis as diagnosis,
                   shared_diagnoses,
                   shared_procedures,
                   (shared_diagnoses * 2 + shared_procedures) as similarity_score
            ORDER BY similarity_score DESC
            LIMIT $limit
            """

            result = session.run(
                cypher,
                target_mrn=patient_mrn,
                min_shared=min_shared_diagnoses,
                limit=limit
            )

            return [dict(record) for record in result]

    def get_treatment_pathway(self, patient_mrn: str) -> List[Dict[str, Any]]:
        """Get chronological treatment pathway for patient"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (p:Patient {mrn: $mrn})
            OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            OPTIONAL MATCH (p)-[:UNDERWENT_PROCEDURE]->(proc:Procedure)
            OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(med:Medication)
            RETURN d.name as diagnosis, d.pod as diag_pod, d.brain_region as location,
                   proc.name as procedure, proc.pod as proc_pod,
                   med.generic_name as medication, med.frequency as dose_frequency
            ORDER BY coalesce(d.pod, proc.pod, 999)
            """

            result = session.run(cypher, mrn=patient_mrn)
            return [dict(record) for record in result]

    def get_medication_protocol(self, diagnosis_name: str) -> List[Dict[str, Any]]:
        """Get common medication protocols for a diagnosis"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (p:Patient)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
            WHERE d.name CONTAINS $diagnosis
            MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
            WITH m.generic_name as medication, m.frequency as frequency,
                 count(DISTINCT p) as patient_count
            WHERE patient_count >= 2
            RETURN medication, frequency, patient_count,
                   patient_count * 100.0 / $total_patients as usage_percentage
            ORDER BY patient_count DESC
            LIMIT 10
            """

            result = session.run(cypher, diagnosis=diagnosis_name, total_patients=100)
            return [dict(record) for record in result]

    def find_complications(
        self,
        procedure_name: str,
        days_window: int = 30
    ) -> List[Dict[str, Any]]:
        """Find complications occurring after a procedure"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (p:Patient)-[:UNDERWENT_PROCEDURE]->(proc:Procedure)
            WHERE proc.name CONTAINS $procedure
            MATCH (p)-[:HAS_DIAGNOSIS]->(comp:Diagnosis)
            WHERE comp.pod IS NOT NULL
              AND proc.pod IS NOT NULL
              AND comp.pod > proc.pod
              AND (comp.pod - proc.pod) <= $days_window
            WITH comp.name as complication,
                 count(DISTINCT p) as occurrences,
                 avg(comp.pod - proc.pod) as avg_days_after
            WHERE occurrences >= 2
            RETURN complication, occurrences, round(avg_days_after, 1) as avg_days_post_op
            ORDER BY occurrences DESC
            """

            result = session.run(
                cypher,
                procedure=procedure_name,
                days_window=days_window
            )
            return [dict(record) for record in result]

    def query_graph(self, cypher_query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Execute custom Cypher query"""
        with self.connection.get_session() as session:
            result = session.run(cypher_query, parameters or {})
            return [dict(record) for record in result]

    # =========================================================================
    # Statistics & Analytics
    # =========================================================================

    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get overall graph statistics"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (n)
            WITH labels(n) as label, count(n) as node_count
            RETURN label[0] as node_type, node_count
            """

            node_stats = session.run(cypher)

            cypher_rels = """
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(r) as count
            """

            rel_stats = session.run(cypher_rels)

            return {
                "nodes": [dict(record) for record in node_stats],
                "relationships": [dict(record) for record in rel_stats],
                "total_nodes": sum(r["node_count"] for r in session.run("MATCH (n) RETURN count(n) as node_count")),
                "total_relationships": sum(r["count"] for r in session.run("MATCH ()-[r]->() RETURN count(r) as count"))
            }

    # =========================================================================
    # Cleanup & Maintenance
    # =========================================================================

    def delete_patient_graph(self, patient_id: int):
        """Delete all graph data for a patient"""
        with self.connection.get_session() as session:
            cypher = """
            MATCH (p:Patient {id: $patient_id})
            OPTIONAL MATCH (p)-[r]->(e)
            DETACH DELETE p, e
            """
            session.run(cypher, patient_id=patient_id)
            logger.info(f"Deleted graph data for patient {patient_id}")

    def clear_entire_graph(self):
        """Clear all nodes and relationships (use with caution!)"""
        with self.connection.get_session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.warning("Entire graph cleared!")


# =============================================================================
# Public API
# =============================================================================

# Global service instance
neo4j_service = Neo4jGraphService()


def sync_patient_facts_to_graph(
    patient_id: int,
    patient_data: Dict[str, Any],
    facts: List[AtomicClinicalFact]
) -> Dict[str, int]:
    """
    Public API for syncing patient data to knowledge graph

    Args:
        patient_id: PostgreSQL patient ID
        patient_data: Patient demographics
        facts: List of clinical facts

    Returns:
        Sync statistics
    """
    return neo4j_service.sync_patient_to_graph(patient_id, patient_data, facts)


def query_knowledge_graph(cypher: str, params: Dict = None) -> List[Dict]:
    """
    Public API for querying the knowledge graph

    Args:
        cypher: Cypher query string
        params: Query parameters

    Returns:
        Query results as list of dicts
    """
    return neo4j_service.query_graph(cypher, params)
