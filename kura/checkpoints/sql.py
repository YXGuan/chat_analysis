"""
SQL-based checkpoint manager using SQLModel.

This module provides a checkpoint manager that stores data in SQL databases
(SQLite, PostgreSQL, MySQL, etc.) with run tracking and rich querying capabilities.
"""

import logging
from typing import Optional, List, TypeVar, Type

from sqlmodel import create_engine, Session, select, SQLModel
from pydantic import BaseModel

from kura.base_classes import BaseCheckpointManager
from kura.types import ConversationSummary, Cluster, ProjectedCluster
from .sql_schemas import (
    RunTable,
    ConversationTable,
    MessageTable,
    ConversationSummaryTable,
    ClusterTable,
    ClusterMembershipTable,
    ProjectedClusterTable,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class SQLCheckpointManager(BaseCheckpointManager):
    """SQL-based checkpoint manager with run tracking."""

    def __init__(self, database_url: str, *, enabled: bool = True):
        """
        Initialize SQL checkpoint manager.

        Args:
            database_url: SQLAlchemy database URL
                - SQLite: "sqlite:///path/to/database.db"
                - PostgreSQL: "postgresql://user:pass@localhost/dbname"
                - MySQL: "mysql://user:pass@localhost/dbname"
            enabled: Whether checkpointing is enabled
        """
        self.database_url = database_url
        self.enabled = enabled

        # For compatibility with MultiCheckpointManager
        self.checkpoint_dir = database_url

        if self.enabled:
            self.engine = create_engine(database_url)

            # Create all tables
            SQLModel.metadata.create_all(self.engine)

            logger.info(
                f"Initialized SQL checkpoint manager with database: {database_url}"
            )

        # Current run context (store ID to avoid session issues)
        self.current_run_id: Optional[str] = None

    def setup_checkpoint_dir(self) -> None:
        """Setup is handled in __init__ for SQL databases."""
        pass

    def get_checkpoint_path(self, filename: str):
        """Not applicable for SQL storage."""
        return filename

    # Run Management Methods

    def create_run(
        self, name: str, description: str = None, config: dict = None
    ) -> RunTable:
        """Create a new analysis run."""
        if not self.enabled:
            raise ValueError("SQL checkpoint manager is disabled")

        run = RunTable.create_new_run(name, config or {})
        if description:
            run.description = description

        with Session(self.engine) as session:
            session.add(run)
            session.commit()
            session.refresh(run)

        # Set as current run
        self.current_run_id = run.id
        logger.info(f"Created new run: {run.id}")
        return run

    def get_run(self, run_id: str) -> Optional[RunTable]:
        """Get a specific run by ID."""
        if not self.enabled:
            return None

        with Session(self.engine) as session:
            return session.get(RunTable, run_id)

    def list_runs(self, status: str = None, limit: int = 50) -> List[RunTable]:
        """List runs, optionally filtered by status."""
        if not self.enabled:
            return []

        with Session(self.engine) as session:
            query = select(RunTable).order_by(RunTable.created_at.desc())

            if status:
                query = query.where(RunTable.status == status)

            if limit:
                query = query.limit(limit)

            return list(session.exec(query))

    def set_current_run(self, run_id: str) -> RunTable:
        """Set the current run context."""
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        self.current_run_id = run.id
        logger.info(f"Set current run to: {run_id}")
        return run

    # Checkpoint Interface Implementation

    def save_checkpoint(self, filename: str, data: List[T], **kwargs) -> None:
        """Save data to SQL tables based on type."""
        if not self.enabled or not data:
            return

        if not self.current_run_id:
            logger.warning("No current run set, creating default run")
            default_run = self.create_run("default_run")
            self.current_run_id = default_run.id

        # Route to appropriate table based on data type
        if isinstance(data[0], ConversationSummary):
            self._save_summaries(data)
        elif isinstance(data[0], Cluster):
            self._save_clusters(data)
        elif isinstance(data[0], ProjectedCluster):
            self._save_projected_clusters(data)
        else:
            logger.warning(f"Unknown data type for SQL checkpoint: {type(data[0])}")

    def load_checkpoint(
        self, filename: str, model_class: Type[T], **kwargs
    ) -> Optional[List[T]]:
        """Load data from SQL tables based on model class."""
        if not self.enabled:
            return None

        if not self.current_run_id:
            logger.warning("No current run set for loading")
            return None

        # Route to appropriate table based on model class
        if model_class == ConversationSummary:
            return self._load_summaries()
        elif model_class == Cluster:
            return self._load_clusters()
        elif model_class == ProjectedCluster:
            return self._load_projected_clusters()

        return None

    def list_checkpoints(self) -> List[str]:
        """List available checkpoint types."""
        if not self.enabled:
            return []

        # For SQL, we return the types of data available
        available = []

        if self.current_run_id:
            # Check what data exists for this run
            with Session(self.engine) as session:
                run = session.get(RunTable, self.current_run_id)
                if run:
                    if run.generated_summaries > 0:
                        available.append("summaries")
                    if run.generated_clusters > 0:
                        available.append("clusters")

        return available

    def delete_checkpoint(self, filename: str) -> bool:
        """Delete checkpoint data (not implemented for safety)."""
        logger.warning("Delete checkpoint not implemented for SQL storage")
        return False

    # Individual Save Methods for Incremental Persistence

    def save_single_summary(self, summary: ConversationSummary) -> None:
        """Save individual summary immediately for incremental persistence."""
        if not self.enabled:
            return

        if not self.current_run_id:
            logger.warning("No current run set, creating default run")
            default_run = self.create_run("default_run")
            self.current_run_id = default_run.id

        with Session(self.engine) as session:
            # Convert to SQLModel and save
            summary_table = ConversationSummaryTable.from_pydantic(
                summary, self.current_run_id
            )
            session.add(summary_table)

            # Update run progress
            run = session.get(RunTable, self.current_run_id)
            if run:
                run.generated_summaries += 1
                session.add(run)

            session.commit()

        logger.debug(f"Saved summary for conversation {summary.chat_id}")

    # Private Methods for Batch Operations

    def _save_summaries(self, summaries: List[ConversationSummary]) -> None:
        """Save summaries to database."""
        with Session(self.engine) as session:
            saved_count = 0
            for summary in summaries:
                # Check if summary already exists
                existing = session.exec(
                    select(ConversationSummaryTable).where(
                        ConversationSummaryTable.chat_id == summary.chat_id
                    )
                ).first()

                if not existing:
                    summary_table = ConversationSummaryTable.from_pydantic(
                        summary, self.current_run_id
                    )
                    session.add(summary_table)
                    saved_count += 1

            # Update run progress
            run = session.get(RunTable, self.current_run_id)
            if run:
                run.generated_summaries = len(summaries)
                session.add(run)

            session.commit()

        logger.info(
            f"Saved {saved_count} new summaries to database (skipped {len(summaries) - saved_count} duplicates)"
        )

    def _save_clusters(self, clusters: List[Cluster]) -> None:
        """Save clusters to database."""
        with Session(self.engine) as session:
            for cluster in clusters:
                # Save cluster
                cluster_table = ClusterTable.from_pydantic(cluster, self.current_run_id)
                session.add(cluster_table)

                # Save cluster memberships
                for chat_id in cluster.chat_ids:
                    membership = ClusterMembershipTable(
                        cluster_id=cluster.id, chat_id=chat_id
                    )
                    session.add(membership)

            # Update run progress
            run = session.get(RunTable, self.current_run_id)
            if run:
                run.generated_clusters = len(clusters)
                session.add(run)

            session.commit()

        logger.info(f"Saved {len(clusters)} clusters to database")

    def _save_projected_clusters(
        self, projected_clusters: List[ProjectedCluster]
    ) -> None:
        """Save projected clusters to database."""
        with Session(self.engine) as session:
            for projected in projected_clusters:
                projected_table = ProjectedClusterTable.from_pydantic(projected)
                session.add(projected_table)

            session.commit()

        logger.info(f"Saved {len(projected_clusters)} projected clusters to database")

    def _load_summaries(self) -> List[ConversationSummary]:
        """Load summaries from database."""
        if not self.current_run_id:
            return []

        with Session(self.engine) as session:
            summaries = session.exec(
                select(ConversationSummaryTable).where(
                    ConversationSummaryTable.run_id == self.current_run_id
                )
            ).all()

            return [summary.to_pydantic() for summary in summaries]

    def _load_clusters(self) -> List[Cluster]:
        """Load clusters from database."""
        if not self.current_run_id:
            return []

        with Session(self.engine) as session:
            clusters = session.exec(
                select(ClusterTable).where(ClusterTable.run_id == self.current_run_id)
            ).all()

            return [cluster.to_pydantic() for cluster in clusters]

    def _load_projected_clusters(self) -> List[ProjectedCluster]:
        """Load projected clusters from database."""
        if not self.current_run_id:
            return []

        with Session(self.engine) as session:
            projected_query = session.exec(
                select(ProjectedClusterTable, ClusterTable)
                .join(ClusterTable, ProjectedClusterTable.cluster_id == ClusterTable.id)
                .where(ClusterTable.run_id == self.current_run_id)
            ).all()

            projected_clusters = []
            for projected_table, cluster_table in projected_query:
                cluster = cluster_table.to_pydantic()
                projected = projected_table.to_pydantic(cluster)
                projected_clusters.append(projected)

            return projected_clusters

    # Query Methods for Analysis

    def query_summaries(
        self, run_id: str = None, filters: dict = None, limit: int = None
    ) -> List[ConversationSummary]:
        """Query summaries with filters."""
        if not self.enabled:
            return []

        target_run_id = run_id or self.current_run_id
        if not target_run_id:
            return []

        with Session(self.engine) as session:
            query = select(ConversationSummaryTable).where(
                ConversationSummaryTable.run_id == target_run_id
            )

            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(ConversationSummaryTable, key):
                        if key.endswith("__gte"):
                            field_name = key[:-5]
                            field = getattr(ConversationSummaryTable, field_name)
                            query = query.where(field >= value)
                        elif key.endswith("__lte"):
                            field_name = key[:-5]
                            field = getattr(ConversationSummaryTable, field_name)
                            query = query.where(field <= value)
                        else:
                            field = getattr(ConversationSummaryTable, key)
                            query = query.where(field == value)

            if limit:
                query = query.limit(limit)

            summaries = session.exec(query).all()
            return [summary.to_pydantic() for summary in summaries]

    def get_run_stats(self, run_id: str = None) -> dict:
        """Get statistics for a run."""
        if not self.enabled:
            return {}

        target_run_id = run_id or self.current_run_id
        if not target_run_id:
            return {}

        run = self.get_run(target_run_id)
        if not run:
            return {}

        return {
            "run_id": run.id,
            "name": run.name,
            "status": run.status,
            "total_conversations": run.total_conversations,
            "generated_summaries": run.generated_summaries,
            "generated_clusters": run.generated_clusters,
            "created_at": run.created_at.isoformat(),
            "processing_time": (
                (run.completed_at - run.started_at).total_seconds()
                if run.completed_at and run.started_at
                else None
            ),
        }
