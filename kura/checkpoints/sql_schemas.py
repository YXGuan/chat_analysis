"""
SQLModel schemas for Kura data types.

This module provides SQLModel table definitions that mirror the Pydantic models
in kura.types, enabling SQL-based checkpointing with support for SQLite, PostgreSQL,
MySQL, and other SQLAlchemy-supported databases.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from kura.types import (
    Conversation,
    ConversationSummary,
    Cluster,
    ProjectedCluster,
    Message,
)


class RunTable(SQLModel, table=True):
    """Table for tracking analysis runs."""

    __tablename__ = "runs"

    id: str = Field(primary_key=True)  # e.g., "wildchat_50k_2024_01_15"
    name: str  # Human readable name
    description: Optional[str] = None
    status: str = Field(default="running")  # "running", "completed", "failed"

    # Configuration metadata
    config_json: str  # JSON string of run configuration

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Progress tracking
    total_conversations: Optional[int] = None
    processed_conversations: int = Field(default=0)
    total_summaries: Optional[int] = None
    generated_summaries: int = Field(default=0)
    total_clusters: Optional[int] = None
    generated_clusters: int = Field(default=0)

    # Error tracking
    error_message: Optional[str] = None
    error_count: int = Field(default=0)

    # Relationships
    conversations: list["ConversationTable"] = Relationship(back_populates="run")
    summaries: list["ConversationSummaryTable"] = Relationship(back_populates="run")
    clusters: list["ClusterTable"] = Relationship(back_populates="run")

    @classmethod
    def create_new_run(
        cls, name: str, config: dict, total_conversations: int = None
    ) -> "RunTable":
        """Create a new analysis run."""
        run_id = f"{name}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}_{uuid.uuid4().hex[:8]}"

        return cls(
            id=run_id,
            name=name,
            config_json=json.dumps(config),
            status="running",
            started_at=datetime.now(),
            total_conversations=total_conversations,
        )

    def update_progress(self, **kwargs) -> None:
        """Update progress counters."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def mark_completed(self) -> None:
        """Mark run as completed."""
        self.status = "completed"
        self.completed_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """Mark run as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.now()


class ConversationTable(SQLModel, table=True):
    """Table for storing conversations."""

    __tablename__ = "conversations"

    chat_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="runs.id")
    created_at: datetime
    metadata_json: str  # JSON string of metadata dict

    # Relationships
    run: RunTable = Relationship(back_populates="conversations")
    messages: list["MessageTable"] = Relationship(back_populates="conversation")
    summary: Optional["ConversationSummaryTable"] = Relationship(
        back_populates="conversation"
    )

    @classmethod
    def from_pydantic(
        cls, conversation: Conversation, run_id: str
    ) -> "ConversationTable":
        """Convert from kura.types.Conversation."""
        return cls(
            chat_id=conversation.chat_id,
            run_id=run_id,
            created_at=conversation.created_at,
            metadata_json=json.dumps(conversation.metadata),
        )

    def to_pydantic(self) -> Conversation:
        """Convert to kura.types.Conversation."""
        # Load messages
        message_objects = [msg.to_pydantic() for msg in self.messages]

        return Conversation(
            chat_id=self.chat_id,
            created_at=self.created_at,
            messages=message_objects,
            metadata=json.loads(self.metadata_json),
        )


class MessageTable(SQLModel, table=True):
    """Table for storing individual messages."""

    __tablename__ = "messages"

    id: int = Field(primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.chat_id")
    created_at: datetime
    role: str  # "user" or "assistant"
    content: str

    # Relationships
    conversation: ConversationTable = Relationship(back_populates="messages")

    @classmethod
    def from_pydantic(cls, message: Message, conversation_id: str) -> "MessageTable":
        """Convert from kura.types.Message."""
        return cls(
            conversation_id=conversation_id,
            created_at=message.created_at,
            role=message.role,
            content=message.content,
        )

    def to_pydantic(self) -> Message:
        """Convert to kura.types.Message."""
        return Message(created_at=self.created_at, role=self.role, content=self.content)


class ConversationSummaryTable(SQLModel, table=True):
    """Table for storing conversation summaries."""

    __tablename__ = "conversation_summaries"

    id: int = Field(primary_key=True)
    chat_id: str = Field(foreign_key="conversations.chat_id", unique=True)
    run_id: str = Field(foreign_key="runs.id")

    # Summary fields
    summary: str
    request: Optional[str] = None
    topic: Optional[str] = None
    languages_json: Optional[str] = None  # JSON array
    task: Optional[str] = None
    concerning_score: Optional[int] = None
    user_frustration: Optional[int] = None
    assistant_errors_json: Optional[str] = None  # JSON array
    metadata_json: str  # JSON string of metadata dict
    embedding_json: Optional[str] = None  # JSON array of floats

    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    conversation: ConversationTable = Relationship(back_populates="summary")
    run: RunTable = Relationship(back_populates="summaries")

    @classmethod
    def from_pydantic(
        cls, summary: ConversationSummary, run_id: str
    ) -> "ConversationSummaryTable":
        """Convert from kura.types.ConversationSummary."""
        return cls(
            chat_id=summary.chat_id,
            run_id=run_id,
            summary=summary.summary,
            request=summary.request,
            topic=summary.topic,
            languages_json=json.dumps(summary.languages) if summary.languages else None,
            task=summary.task,
            concerning_score=summary.concerning_score,
            user_frustration=summary.user_frustration,
            assistant_errors_json=(
                json.dumps(summary.assistant_errors)
                if summary.assistant_errors
                else None
            ),
            metadata_json=json.dumps(summary.metadata),
            embedding_json=json.dumps(summary.embedding) if summary.embedding else None,
        )

    def to_pydantic(self) -> ConversationSummary:
        """Convert to kura.types.ConversationSummary."""
        return ConversationSummary(
            chat_id=self.chat_id,
            summary=self.summary,
            request=self.request,
            topic=self.topic,
            languages=json.loads(self.languages_json) if self.languages_json else None,
            task=self.task,
            concerning_score=self.concerning_score,
            user_frustration=self.user_frustration,
            assistant_errors=(
                json.loads(self.assistant_errors_json)
                if self.assistant_errors_json
                else None
            ),
            metadata=json.loads(self.metadata_json),
            embedding=json.loads(self.embedding_json) if self.embedding_json else None,
        )


class ClusterTable(SQLModel, table=True):
    """Table for storing clusters."""

    __tablename__ = "clusters"

    id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="runs.id")
    name: str
    description: str
    slug: str
    parent_id: Optional[str] = Field(foreign_key="clusters.id")
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    run: RunTable = Relationship(back_populates="clusters")
    # Note: Self-referential relationships disabled for now - parent_id field still available
    memberships: list["ClusterMembershipTable"] = Relationship(back_populates="cluster")

    @classmethod
    def from_pydantic(cls, cluster: Cluster, run_id: str) -> "ClusterTable":
        """Convert from kura.types.Cluster."""
        return cls(
            id=cluster.id,
            run_id=run_id,
            name=cluster.name,
            description=cluster.description,
            slug=cluster.slug,
            parent_id=cluster.parent_id,
        )

    def to_pydantic(self) -> Cluster:
        """Convert to kura.types.Cluster."""
        # Get chat_ids from memberships
        chat_ids = [membership.chat_id for membership in self.memberships]

        return Cluster(
            id=self.id,
            name=self.name,
            description=self.description,
            slug=self.slug,
            chat_ids=chat_ids,
            parent_id=self.parent_id,
        )


class ClusterMembershipTable(SQLModel, table=True):
    """Many-to-many table for cluster membership."""

    __tablename__ = "cluster_memberships"

    cluster_id: str = Field(foreign_key="clusters.id", primary_key=True)
    chat_id: str = Field(foreign_key="conversations.chat_id", primary_key=True)

    # Relationships
    cluster: ClusterTable = Relationship(back_populates="memberships")
    conversation: ConversationTable = Relationship()


class ProjectedClusterTable(SQLModel, table=True):
    """Table for storing projected clusters with coordinates."""

    __tablename__ = "projected_clusters"

    cluster_id: str = Field(foreign_key="clusters.id", primary_key=True)
    x_coord: float
    y_coord: float
    level: int

    # Relationships
    cluster: ClusterTable = Relationship()

    @classmethod
    def from_pydantic(cls, projected: ProjectedCluster) -> "ProjectedClusterTable":
        """Convert from kura.types.ProjectedCluster."""
        return cls(
            cluster_id=projected.id,
            x_coord=projected.x_coord,
            y_coord=projected.y_coord,
            level=projected.level,
        )

    def to_pydantic(self, cluster_data: Cluster) -> ProjectedCluster:
        """Convert to kura.types.ProjectedCluster."""
        return ProjectedCluster(
            id=cluster_data.id,
            name=cluster_data.name,
            description=cluster_data.description,
            slug=cluster_data.slug,
            chat_ids=cluster_data.chat_ids,
            parent_id=cluster_data.parent_id,
            x_coord=self.x_coord,
            y_coord=self.y_coord,
            level=self.level,
        )
