"""Repository classes for async CRUD operations."""

from typing import List, Optional, Any
from uuid import uuid4

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, and_, or_
except ImportError:
    AsyncSession = None
    select = None
    and_ = None
    or_ = None

from agentend.persistence.models import (
    Session as SessionModel,
    Run,
    MemoryBlock,
    Checkpoint,
)


class BaseRepository:
    """Base repository with common CRUD operations."""

    def __init__(self, session):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session.
        """
        if AsyncSession is None or select is None:
            raise ImportError("Install agentend[persistence] for SQLAlchemy support")
        self.session = session
        self.model = None

    async def create(self, **kwargs) -> Any:
        """Create and save model instance."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_by_id(self, id: str) -> Optional[Any]:
        """Get model by ID."""
        if select is None:
            raise ImportError("Install agentend[persistence] for SQLAlchemy support")
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        """Get all models with pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, id: str, **kwargs) -> Optional[Any]:
        """Update model by ID."""
        instance = await self.get_by_id(id)
        if not instance:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.flush()
        return instance

    async def delete(self, id: str) -> bool:
        """Delete model by ID."""
        instance = await self.get_by_id(id)
        if not instance:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def save(self) -> None:
        """Commit all pending changes."""
        await self.session.commit()


class SessionRepository(BaseRepository):
    """Repository for Session model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.model = SessionModel

    async def get_by_tenant_user(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 100,
    ) -> List[SessionModel]:
        """Get sessions for tenant and user."""
        stmt = select(SessionModel).where(
            and_(
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == user_id,
            )
        ).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_status(
        self,
        tenant_id: str,
        status: str,
        limit: int = 100,
    ) -> List[SessionModel]:
        """Get sessions by status."""
        stmt = select(SessionModel).where(
            and_(
                SessionModel.tenant_id == tenant_id,
                SessionModel.status == status,
            )
        ).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_sessions(self, tenant_id: str) -> List[SessionModel]:
        """Get all active sessions for tenant."""
        return await self.get_by_status(
            tenant_id,
            "active",
            limit=1000,
        )


class RunRepository(BaseRepository):
    """Repository for Run model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.model = Run

    async def get_by_tenant_user(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 100,
    ) -> List[Run]:
        """Get runs for tenant and user."""
        stmt = select(Run).where(
            and_(
                Run.tenant_id == tenant_id,
                Run.user_id == user_id,
            )
        ).order_by(Run.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_status(
        self,
        tenant_id: str,
        status: str,
        limit: int = 100,
    ) -> List[Run]:
        """Get runs by status."""
        stmt = select(Run).where(
            and_(
                Run.tenant_id == tenant_id,
                Run.status == status,
            )
        ).order_by(Run.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_runs(self, tenant_id: Optional[str] = None) -> List[Run]:
        """Get all pending runs."""
        conditions = [Run.status.in_(["submitted", "processing"])]

        if tenant_id:
            conditions.append(Run.tenant_id == tenant_id)

        stmt = select(Run).where(and_(*conditions)).order_by(Run.priority.desc(), Run.created_at.asc())

        result = await self.session.execute(stmt)
        return result.scalars().all()


class MemoryRepository(BaseRepository):
    """Repository for MemoryBlock model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.model = MemoryBlock

    async def get_by_session(
        self,
        tenant_id: str,
        session_id: str,
        block_type: Optional[str] = None,
    ) -> List[MemoryBlock]:
        """Get memory blocks for session."""
        conditions = [
            MemoryBlock.tenant_id == tenant_id,
            MemoryBlock.session_id == session_id,
        ]

        if block_type:
            conditions.append(MemoryBlock.block_type == block_type)

        stmt = select(MemoryBlock).where(and_(*conditions)).order_by(
            MemoryBlock.accessed_at.desc()
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_type(
        self,
        tenant_id: str,
        block_type: str,
        limit: int = 100,
    ) -> List[MemoryBlock]:
        """Get memory blocks by type."""
        stmt = select(MemoryBlock).where(
            and_(
                MemoryBlock.tenant_id == tenant_id,
                MemoryBlock.block_type == block_type,
            )
        ).order_by(MemoryBlock.accessed_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_similar(
        self,
        tenant_id: str,
        embedding: List[float],
        block_type: Optional[str] = None,
        similarity_threshold: float = 0.8,
        limit: int = 10,
    ) -> List[MemoryBlock]:
        """Find similar memory blocks by embedding similarity."""
        # Placeholder: Would use pgvector <-> operator
        # For now, just return recent blocks of type
        if block_type:
            return await self.get_by_type(tenant_id, block_type, limit)
        return []


class CheckpointRepository(BaseRepository):
    """Repository for Checkpoint model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.model = Checkpoint

    async def get_by_run(
        self,
        tenant_id: str,
        run_id: str,
    ) -> List[Checkpoint]:
        """Get all checkpoints for a run."""
        stmt = select(Checkpoint).where(
            and_(
                Checkpoint.tenant_id == tenant_id,
                Checkpoint.run_id == run_id,
            )
        ).order_by(Checkpoint.checkpoint_number.desc())

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_checkpoint(
        self,
        tenant_id: str,
        run_id: str,
    ) -> Optional[Checkpoint]:
        """Get latest checkpoint for a run."""
        checkpoints = await self.get_by_run(tenant_id, run_id)
        return checkpoints[0] if checkpoints else None

    async def create_checkpoint(
        self,
        tenant_id: str,
        run_id: str,
        checkpoint_number: int,
        state: dict,
        memory_state: dict,
    ) -> Checkpoint:
        """Create a new checkpoint."""
        return await self.create(
            tenant_id=tenant_id,
            run_id=run_id,
            checkpoint_number=checkpoint_number,
            state=state,
            memory_state=memory_state,
        )

    async def resume_from_checkpoint(
        self,
        tenant_id: str,
        run_id: str,
        checkpoint_number: int,
    ) -> Optional[dict]:
        """Get checkpoint state for resumption."""
        checkpoints = await self.get_by_run(tenant_id, run_id)
        for cp in checkpoints:
            if cp.checkpoint_number == checkpoint_number:
                return {
                    "state": cp.state,
                    "memory_state": cp.memory_state,
                }
        return None
