# PHASE 2: Multi-Board Job Distribution - Complete Implementation

**Read First:** SPEC.md, ARCHITECTURE.md, CLAUDE.MD, PROMPT33, PROMPT34, PROMPT44, and completed Phase 1

## Purpose

Build the "post once, distribute everywhere" feature that is Winnow's core value proposition for recruiters. This phase implements automated job distribution to multiple job boards (Indeed, LinkedIn, Google Jobs, etc.) with real-time sync and per-board analytics.

**What already exists (DO NOT recreate):**
- ✅ Employer jobs table with status workflow
- ✅ Frontend job creation and management UI (Phase 1)
- ✅ Backend API for job CRUD operations

**What we're building:**
- Board adapter interface for connecting to external job boards
- Distribution engine to push jobs to multiple boards
- Real-time sync when jobs are edited or closed
- Per-board metrics tracking (impressions, clicks, applications, cost)
- Distribution status monitoring UI

---

## Step 1: Create Distribution Database Tables

### 1.1 - Create Alembic Migration

**What to do:**
1. Open **PowerShell**
2. Navigate to the API directory:
   ```powershell
   cd services/api
   ```
3. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
4. Create a new migration file:
   ```powershell
   alembic revision -m "add_job_distribution_tables"
   ```

This will create a new file in `services/api/alembic/versions/` with a name like `xxxx_add_job_distribution_tables.py`

### 1.2 - Edit the Migration File

**File location:** `services/api/alembic/versions/xxxx_add_job_distribution_tables.py`  
(The `xxxx` will be a unique timestamp - find the newest file in that folder)

**Replace the entire contents** with this code:

```python
"""add job distribution tables

Revision ID: xxxx
Revises: (previous_revision)
Create Date: (timestamp)

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx'  # Keep the auto-generated revision ID
down_revision = 'yyyy'  # Keep the auto-generated down_revision ID
branch_labels = None
depends_on = None


def upgrade():
    # job_boards table
    op.create_table(
        'job_boards',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('api_endpoint', sa.String(500)),
        sa.Column('requires_api_key', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('config', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # employer_board_connections table
    op.create_table(
        'employer_board_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('employer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employer_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_connected', sa.Boolean, default=False),
        sa.Column('api_key', sa.String(500)),
        sa.Column('credentials', postgresql.JSONB, default={}),
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('employer_id', 'board_id', name='uq_employer_board'),
    )

    # job_distributions table
    op.create_table(
        'job_distributions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employer_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_job_id', sa.String(255)),
        sa.Column('distribution_status', sa.String(50), default='pending'),  # pending, live, syncing, failed, removed
        sa.Column('posted_at', sa.DateTime(timezone=True)),
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('job_id', 'board_id', name='uq_job_board_distribution'),
    )

    # distribution_metrics table
    op.create_table(
        'distribution_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('distribution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_distributions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('impressions', sa.Integer, default=0),
        sa.Column('clicks', sa.Integer, default=0),
        sa.Column('applications', sa.Integer, default=0),
        sa.Column('cost_spent', sa.Numeric(10, 2), default=0),
        sa.Column('last_updated_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # distribution_events table (audit log)
    op.create_table(
        'distribution_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('distribution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_distributions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),  # posted, synced, removed, error
        sa.Column('event_data', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index('idx_job_distributions_job_id', 'job_distributions', ['job_id'])
    op.create_index('idx_job_distributions_board_id', 'job_distributions', ['board_id'])
    op.create_index('idx_job_distributions_status', 'job_distributions', ['distribution_status'])
    op.create_index('idx_distribution_events_distribution_id', 'distribution_events', ['distribution_id'])
    op.create_index('idx_distribution_events_type', 'distribution_events', ['event_type'])
    op.create_index('idx_employer_board_connections_employer', 'employer_board_connections', ['employer_id'])


def downgrade():
    op.drop_table('distribution_events')
    op.drop_table('distribution_metrics')
    op.drop_table('job_distributions')
    op.drop_table('employer_board_connections')
    op.drop_table('job_boards')
```

**How to edit the migration file in Cursor:**

1. In Cursor, navigate to: `services/api/alembic/versions/`
2. Find the file that starts with the newest timestamp
3. Open it
4. Replace ALL the code with the code above
5. **IMPORTANT:** Keep the auto-generated `revision` and `down_revision` IDs at the top - don't change those
6. Save the file (Ctrl+S)

### 1.3 - Run the Migration

**In PowerShell** (make sure you're still in `services/api` with venv activated):

```powershell
alembic upgrade head
```

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade xxxx -> yyyy, add job distribution tables
```

---

## Step 2: Create Database Models

### File to create: `services/api/app/models/distribution.py`

**Full path:** `services/api/app/models/distribution.py`

**What this file does:**
- Defines SQLAlchemy models for job boards, distributions, metrics, and events
- Maps to the database tables we just created

**Code to add:**

```python
"""
Distribution models for job board integrations.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class JobBoard(Base):
    """
    Available job boards for distribution.
    Pre-populated with major boards (Indeed, LinkedIn, etc.)
    """
    __tablename__ = "job_boards"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    api_endpoint = Column(String(500))
    requires_api_key = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    config = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    connections = relationship("EmployerBoardConnection", back_populates="board", cascade="all, delete-orphan")
    distributions = relationship("JobDistribution", back_populates="board", cascade="all, delete-orphan")


class EmployerBoardConnection(Base):
    """
    Employer's connection to a specific job board.
    Stores API keys and credentials.
    """
    __tablename__ = "employer_board_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    board_id = Column(UUID(as_uuid=True), ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False)
    
    is_connected = Column(Boolean, default=False)
    api_key = Column(String(500))  # Encrypted in production
    credentials = Column(JSONB, default={})  # Other auth data
    last_synced_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('employer_id', 'board_id', name='uq_employer_board'),
    )
    
    # Relationships
    employer = relationship("EmployerProfile", back_populates="board_connections")
    board = relationship("JobBoard", back_populates="connections")


class JobDistribution(Base):
    """
    Tracks distribution of a specific job to a specific board.
    One job can be distributed to multiple boards.
    """
    __tablename__ = "job_distributions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("employer_jobs.id", ondelete="CASCADE"), nullable=False)
    board_id = Column(UUID(as_uuid=True), ForeignKey("job_boards.id", ondelete="CASCADE"), nullable=False)
    
    external_job_id = Column(String(255))  # The ID from the external board
    distribution_status = Column(String(50), default="pending")  # pending, live, syncing, failed, removed
    posted_at = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('job_id', 'board_id', name='uq_job_board_distribution'),
    )
    
    # Relationships
    job = relationship("EmployerJob", back_populates="distributions")
    board = relationship("JobBoard", back_populates="distributions")
    metrics = relationship("DistributionMetric", back_populates="distribution", uselist=False, cascade="all, delete-orphan")
    events = relationship("DistributionEvent", back_populates="distribution", cascade="all, delete-orphan")


class DistributionMetric(Base):
    """
    Performance metrics for each job distribution.
    Updated periodically from board APIs.
    """
    __tablename__ = "distribution_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distribution_id = Column(UUID(as_uuid=True), ForeignKey("job_distributions.id", ondelete="CASCADE"), nullable=False)
    
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    applications = Column(Integer, default=0)
    cost_spent = Column(Numeric(10, 2), default=0)
    
    last_updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    distribution = relationship("JobDistribution", back_populates="metrics")


class DistributionEvent(Base):
    """
    Audit log of distribution events.
    Tracks when jobs are posted, synced, removed, or encounter errors.
    """
    __tablename__ = "distribution_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distribution_id = Column(UUID(as_uuid=True), ForeignKey("job_distributions.id", ondelete="CASCADE"), nullable=False)
    
    event_type = Column(String(100), nullable=False)  # posted, synced, removed, error
    event_data = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    distribution = relationship("JobDistribution", back_populates="events")
```

**How to create this file in Cursor:**

1. Navigate to: `services/api/app/models/`
2. Create new file: `distribution.py`
3. Paste the code above
4. Save (Ctrl+S)

### 2.1 - Update Existing Models

We need to add relationships to existing models.

**File to edit:** `services/api/app/models/employer.py`

**Find this section** (around line 30):

```python
# Relationships
jobs = relationship("EmployerJob", back_populates="employer", cascade="all, delete-orphan")
```

**Add this line below it:**

```python
board_connections = relationship("EmployerBoardConnection", back_populates="employer", cascade="all, delete-orphan")
```

**File to edit:** `services/api/app/models/job.py`

**Find this section** (around line 50):

```python
# Relationships
employer = relationship("EmployerProfile", back_populates="jobs")
```

**Add this line below it:**

```python
distributions = relationship("JobDistribution", back_populates="job", cascade="all, delete-orphan")
```

### 2.2 - Update Models __init__.py

**File to edit:** `services/api/app/models/__init__.py`

**Add this import at the bottom:**

```python
from app.models.distribution import JobBoard, EmployerBoardConnection, JobDistribution, DistributionMetric, DistributionEvent
```

---

## Step 3: Create Board Adapter Interface

### File to create: `services/api/app/services/board_adapters/base.py`

**Full path:** `services/api/app/services/board_adapters/base.py`

First, **create the folder structure:**
1. In Cursor, navigate to: `services/api/app/services/`
2. Create new folder: `board_adapters`
3. Inside that folder, create file: `base.py`

**What this file does:**
- Defines the interface that all job board adapters must implement
- Ensures consistent behavior across different boards

**Code to add:**

```python
"""
Base adapter interface for job board integrations.
All board adapters must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class JobBoardAdapter(ABC):
    """
    Abstract base class for job board integrations.
    Each board (Indeed, LinkedIn, etc.) implements this interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with board-specific configuration.
        
        Args:
            config: Board configuration (API endpoints, credentials, etc.)
        """
        self.config = config
        self.board_name = config.get('name', 'Unknown Board')
    
    @abstractmethod
    async def post_job(self, job_data: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a job to the board.
        
        Args:
            job_data: Job details (title, description, location, salary, etc.)
            credentials: Employer's credentials for this board (API key, etc.)
        
        Returns:
            {
                'success': bool,
                'external_job_id': str,  # The board's ID for this posting
                'posted_at': datetime,
                'error': Optional[str]
            }
        """
        pass
    
    @abstractmethod
    async def update_job(self, external_job_id: str, job_data: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing job on the board.
        
        Args:
            external_job_id: The board's ID for this job
            job_data: Updated job details
            credentials: Employer's credentials
        
        Returns:
            {
                'success': bool,
                'updated_at': datetime,
                'error': Optional[str]
            }
        """
        pass
    
    @abstractmethod
    async def remove_job(self, external_job_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove a job from the board.
        
        Args:
            external_job_id: The board's ID for this job
            credentials: Employer's credentials
        
        Returns:
            {
                'success': bool,
                'removed_at': datetime,
                'error': Optional[str]
            }
        """
        pass
    
    @abstractmethod
    async def fetch_metrics(self, external_job_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch performance metrics from the board.
        
        Args:
            external_job_id: The board's ID for this job
            credentials: Employer's credentials
        
        Returns:
            {
                'success': bool,
                'impressions': int,
                'clicks': int,
                'applications': int,
                'cost_spent': float,
                'last_updated_at': datetime,
                'error': Optional[str]
            }
        """
        pass
    
    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate employer's credentials for this board.
        
        Args:
            credentials: Credentials to validate
        
        Returns:
            {
                'valid': bool,
                'error': Optional[str]
            }
        """
        pass
    
    def format_job_data(self, winnow_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Winnow job format to board-specific format.
        Override this in each adapter as needed.
        
        Args:
            winnow_job: Job data in Winnow's standard format
        
        Returns:
            Job data in board-specific format
        """
        return winnow_job
```

### 3.1 - Create Mock Adapter (for testing)

**File to create:** `services/api/app/services/board_adapters/mock_board.py`

**Location:** `services/api/app/services/board_adapters/mock_board.py`

**What this file does:**
- Implements a fake job board for testing
- Simulates posting, updating, and removing jobs
- Generates fake metrics

**Code to add:**

```python
"""
Mock job board adapter for testing and development.
Simulates a job board without making real API calls.
"""
import uuid
from datetime import datetime
from typing import Dict, Any
import random

from .base import JobBoardAdapter


class MockBoardAdapter(JobBoardAdapter):
    """
    Mock adapter that simulates job board operations.
    Used for testing and local development.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.board_name = config.get('name', 'Mock Board')
        # In-memory storage of "posted" jobs
        self._posted_jobs = {}
    
    async def post_job(self, job_data: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate posting a job."""
        # Generate fake external ID
        external_job_id = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
        
        # Store job data
        self._posted_jobs[external_job_id] = {
            'job_data': job_data,
            'posted_at': datetime.utcnow(),
            'status': 'live'
        }
        
        return {
            'success': True,
            'external_job_id': external_job_id,
            'posted_at': datetime.utcnow(),
            'error': None
        }
    
    async def update_job(self, external_job_id: str, job_data: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate updating a job."""
        if external_job_id not in self._posted_jobs:
            return {
                'success': False,
                'updated_at': None,
                'error': f'Job {external_job_id} not found on {self.board_name}'
            }
        
        # Update stored job data
        self._posted_jobs[external_job_id]['job_data'] = job_data
        self._posted_jobs[external_job_id]['updated_at'] = datetime.utcnow()
        
        return {
            'success': True,
            'updated_at': datetime.utcnow(),
            'error': None
        }
    
    async def remove_job(self, external_job_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate removing a job."""
        if external_job_id not in self._posted_jobs:
            return {
                'success': False,
                'removed_at': None,
                'error': f'Job {external_job_id} not found on {self.board_name}'
            }
        
        # Mark as removed
        self._posted_jobs[external_job_id]['status'] = 'removed'
        self._posted_jobs[external_job_id]['removed_at'] = datetime.utcnow()
        
        return {
            'success': True,
            'removed_at': datetime.utcnow(),
            'error': None
        }
    
    async def fetch_metrics(self, external_job_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fake metrics for testing."""
        if external_job_id not in self._posted_jobs:
            return {
                'success': False,
                'impressions': 0,
                'clicks': 0,
                'applications': 0,
                'cost_spent': 0.0,
                'last_updated_at': None,
                'error': f'Job {external_job_id} not found on {self.board_name}'
            }
        
        # Generate random but realistic metrics
        impressions = random.randint(100, 5000)
        clicks = int(impressions * random.uniform(0.02, 0.08))  # 2-8% CTR
        applications = int(clicks * random.uniform(0.05, 0.15))  # 5-15% application rate
        cost_spent = round(clicks * random.uniform(0.50, 2.00), 2)  # $0.50-$2.00 per click
        
        return {
            'success': True,
            'impressions': impressions,
            'clicks': clicks,
            'applications': applications,
            'cost_spent': cost_spent,
            'last_updated_at': datetime.utcnow(),
            'error': None
        }
    
    async def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Mock credential validation - always succeeds."""
        # For mock board, any credentials are valid
        return {
            'valid': True,
            'error': None
        }
```

### 3.2 - Create Adapter Factory

**File to create:** `services/api/app/services/board_adapters/__init__.py`

**Location:** `services/api/app/services/board_adapters/__init__.py`

**What this file does:**
- Factory pattern to get the right adapter for each board
- Maps board slugs to adapter classes

**Code to add:**

```python
"""
Board adapter factory.
Maps board slugs to their adapter implementations.
"""
from typing import Dict, Any
from .base import JobBoardAdapter
from .mock_board import MockBoardAdapter


# Registry of available adapters
ADAPTER_REGISTRY = {
    'mock-board': MockBoardAdapter,
    'test-board': MockBoardAdapter,
    # Future adapters:
    # 'indeed': IndeedAdapter,
    # 'linkedin': LinkedInAdapter,
    # 'google-jobs': GoogleJobsAdapter,
}


def get_adapter(board_slug: str, config: Dict[str, Any]) -> JobBoardAdapter:
    """
    Get the appropriate adapter for a job board.
    
    Args:
        board_slug: Board identifier (e.g., 'indeed', 'linkedin')
        config: Board configuration
    
    Returns:
        Initialized adapter instance
    
    Raises:
        ValueError: If board_slug not found in registry
    """
    adapter_class = ADAPTER_REGISTRY.get(board_slug)
    
    if not adapter_class:
        raise ValueError(f"No adapter found for board: {board_slug}")
    
    return adapter_class(config)


__all__ = ['JobBoardAdapter', 'get_adapter', 'MockBoardAdapter']
```

---

## Step 4: Create Distribution Service

This is a large file - take your time with it!

### File to create: `services/api/app/services/distribution_engine.py`

**Full path:** `services/api/app/services/distribution_engine.py`

**What this file does:**
- Orchestrates job distribution to multiple boards
- Handles sync logic when jobs are updated
- Manages metrics fetching and error handling

**Code to add:**

```python
"""
Distribution engine for managing job postings across multiple boards.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.distribution import (
    JobBoard,
    EmployerBoardConnection,
    JobDistribution,
    DistributionMetric,
    DistributionEvent
)
from app.models.job import EmployerJob
from app.services.board_adapters import get_adapter


async def distribute_job(
    job_id: uuid.UUID,
    employer_id: uuid.UUID,
    board_slugs: List[str],
    db: Session
) -> Dict[str, Any]:
    """
    Distribute a job to multiple boards.
    
    Args:
        job_id: Job to distribute
        employer_id: Employer posting the job
        board_slugs: List of board slugs to post to (e.g., ['indeed', 'linkedin'])
        db: Database session
    
    Returns:
        {
            'success': bool,
            'results': List[{
                'board': str,
                'status': str,  # 'success' or 'failed'
                'external_job_id': Optional[str],
                'error': Optional[str]
            }]
        }
    """
    # Get job
    job = db.query(EmployerJob).filter(EmployerJob.id == job_id).first()
    if not job:
        return {'success': False, 'error': 'Job not found'}
    
    # Prepare job data for distribution
    job_data = {
        'title': job.title,
        'description': job.description,
        'requirements': job.requirements,
        'nice_to_haves': job.nice_to_haves,
        'location': job.location,
        'remote_policy': job.remote_policy,
        'employment_type': job.employment_type,
        'salary_min': job.salary_min,
        'salary_max': job.salary_max,
        'application_url': job.application_url,
        'application_email': job.application_email,
    }
    
    results = []
    
    for board_slug in board_slugs:
        try:
            # Get board
            board = db.query(JobBoard).filter(JobBoard.slug == board_slug).first()
            if not board or not board.is_active:
                results.append({
                    'board': board_slug,
                    'status': 'failed',
                    'external_job_id': None,
                    'error': f'Board {board_slug} not found or inactive'
                })
                continue
            
            # Get employer's connection to this board
            connection = db.query(EmployerBoardConnection).filter(
                and_(
                    EmployerBoardConnection.employer_id == employer_id,
                    EmployerBoardConnection.board_id == board.id
                )
            ).first()
            
            if not connection or not connection.is_connected:
                results.append({
                    'board': board_slug,
                    'status': 'failed',
                    'external_job_id': None,
                    'error': f'Not connected to {board_slug}'
                })
                continue
            
            # Get adapter
            adapter = get_adapter(board_slug, board.config)
            
            # Prepare credentials
            credentials = {
                'api_key': connection.api_key,
                **connection.credentials
            }
            
            # Post job
            result = await adapter.post_job(job_data, credentials)
            
            if result['success']:
                # Create distribution record
                distribution = JobDistribution(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    board_id=board.id,
                    external_job_id=result['external_job_id'],
                    distribution_status='live',
                    posted_at=result['posted_at']
                )
                db.add(distribution)
                
                # Create metrics record
                metrics = DistributionMetric(
                    id=uuid.uuid4(),
                    distribution_id=distribution.id,
                    impressions=0,
                    clicks=0,
                    applications=0,
                    cost_spent=0,
                    last_updated_at=datetime.utcnow()
                )
                db.add(metrics)
                
                # Log event
                event = DistributionEvent(
                    id=uuid.uuid4(),
                    distribution_id=distribution.id,
                    event_type='posted',
                    event_data={'external_job_id': result['external_job_id']}
                )
                db.add(event)
                
                db.commit()
                
                results.append({
                    'board': board_slug,
                    'status': 'success',
                    'external_job_id': result['external_job_id'],
                    'error': None
                })
            else:
                # Create failed distribution record
                distribution = JobDistribution(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    board_id=board.id,
                    distribution_status='failed',
                    error_message=result.get('error')
                )
                db.add(distribution)
                
                # Log error event
                event = DistributionEvent(
                    id=uuid.uuid4(),
                    distribution_id=distribution.id,
                    event_type='error',
                    event_data={'error': result.get('error')}
                )
                db.add(event)
                
                db.commit()
                
                results.append({
                    'board': board_slug,
                    'status': 'failed',
                    'external_job_id': None,
                    'error': result.get('error')
                })
        
        except Exception as e:
            results.append({
                'board': board_slug,
                'status': 'failed',
                'external_job_id': None,
                'error': str(e)
            })
    
    return {
        'success': any(r['status'] == 'success' for r in results),
        'results': results
    }


async def sync_job(job_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """
    Sync job changes to all boards where it's distributed.
    Called when job is updated.
    
    Args:
        job_id: Job to sync
        db: Database session
    
    Returns:
        {'success': bool, 'synced_count': int, 'errors': List[str]}
    """
    job = db.query(EmployerJob).filter(EmployerJob.id == job_id).first()
    if not job:
        return {'success': False, 'synced_count': 0, 'errors': ['Job not found']}
    
    # Get all distributions for this job
    distributions = db.query(JobDistribution).filter(
        and_(
            JobDistribution.job_id == job_id,
            JobDistribution.distribution_status == 'live'
        )
    ).all()
    
    if not distributions:
        return {'success': True, 'synced_count': 0, 'errors': []}
    
    job_data = {
        'title': job.title,
        'description': job.description,
        'requirements': job.requirements,
        'nice_to_haves': job.nice_to_haves,
        'location': job.location,
        'remote_policy': job.remote_policy,
        'employment_type': job.employment_type,
        'salary_min': job.salary_min,
        'salary_max': job.salary_max,
        'application_url': job.application_url,
        'application_email': job.application_email,
    }
    
    synced_count = 0
    errors = []
    
    for dist in distributions:
        try:
            board = dist.board
            connection = db.query(EmployerBoardConnection).filter(
                and_(
                    EmployerBoardConnection.employer_id == job.employer_id,
                    EmployerBoardConnection.board_id == board.id
                )
            ).first()
            
            if not connection:
                continue
            
            adapter = get_adapter(board.slug, board.config)
            credentials = {
                'api_key': connection.api_key,
                **connection.credentials
            }
            
            result = await adapter.update_job(dist.external_job_id, job_data, credentials)
            
            if result['success']:
                dist.last_synced_at = datetime.utcnow()
                dist.distribution_status = 'live'
                
                # Log sync event
                event = DistributionEvent(
                    id=uuid.uuid4(),
                    distribution_id=dist.id,
                    event_type='synced',
                    event_data={}
                )
                db.add(event)
                
                synced_count += 1
            else:
                dist.distribution_status = 'failed'
                dist.error_message = result.get('error')
                errors.append(f"{board.name}: {result.get('error')}")
                
                # Log error event
                event = DistributionEvent(
                    id=uuid.uuid4(),
                    distribution_id=dist.id,
                    event_type='error',
                    event_data={'error': result.get('error')}
                )
                db.add(event)
        
        except Exception as e:
            errors.append(f"{dist.board.name}: {str(e)}")
    
    db.commit()
    
    return {
        'success': len(errors) == 0,
        'synced_count': synced_count,
        'errors': errors
    }


async def remove_job_from_boards(job_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """
    Remove job from all boards.
    Called when job is closed or deleted.
    
    Args:
        job_id: Job to remove
        db: Database session
    
    Returns:
        {'success': bool, 'removed_count': int, 'errors': List[str]}
    """
    job = db.query(EmployerJob).filter(EmployerJob.id == job_id).first()
    if not job:
        return {'success': False, 'removed_count': 0, 'errors': ['Job not found']}
    
    distributions = db.query(JobDistribution).filter(
        and_(
            JobDistribution.job_id == job_id,
            JobDistribution.distribution_status.in_(['live', 'syncing'])
        )
    ).all()
    
    removed_count = 0
    errors = []
    
    for dist in distributions:
        try:
            board = dist.board
            connection = db.query(EmployerBoardConnection).filter(
                and_(
                    EmployerBoardConnection.employer_id == job.employer_id,
                    EmployerBoardConnection.board_id == board.id
                )
            ).first()
            
            if not connection:
                continue
            
            adapter = get_adapter(board.slug, board.config)
            credentials = {
                'api_key': connection.api_key,
                **connection.credentials
            }
            
            result = await adapter.remove_job(dist.external_job_id, credentials)
            
            if result['success']:
                dist.distribution_status = 'removed'
                
                # Log removal event
                event = DistributionEvent(
                    id=uuid.uuid4(),
                    distribution_id=dist.id,
                    event_type='removed',
                    event_data={}
                )
                db.add(event)
                
                removed_count += 1
            else:
                errors.append(f"{board.name}: {result.get('error')}")
        
        except Exception as e:
            errors.append(f"{dist.board.name}: {str(e)}")
    
    db.commit()
    
    return {
        'success': len(errors) == 0,
        'removed_count': removed_count,
        'errors': errors
    }


async def fetch_all_metrics(job_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """
    Fetch latest metrics from all boards for a job.
    
    Args:
        job_id: Job ID
        db: Database session
    
    Returns:
        {'success': bool, 'metrics': List[dict], 'errors': List[str]}
    """
    distributions = db.query(JobDistribution).filter(
        and_(
            JobDistribution.job_id == job_id,
            JobDistribution.distribution_status == 'live'
        )
    ).all()
    
    all_metrics = []
    errors = []
    
    for dist in distributions:
        try:
            board = dist.board
            connection = db.query(EmployerBoardConnection).filter(
                EmployerBoardConnection.board_id == board.id
            ).first()
            
            if not connection:
                continue
            
            adapter = get_adapter(board.slug, board.config)
            credentials = {
                'api_key': connection.api_key,
                **connection.credentials
            }
            
            result = await adapter.fetch_metrics(dist.external_job_id, credentials)
            
            if result['success']:
                # Update metrics in database
                if not dist.metrics:
                    metrics = DistributionMetric(
                        id=uuid.uuid4(),
                        distribution_id=dist.id
                    )
                    db.add(metrics)
                else:
                    metrics = dist.metrics
                
                metrics.impressions = result['impressions']
                metrics.clicks = result['clicks']
                metrics.applications = result['applications']
                metrics.cost_spent = result['cost_spent']
                metrics.last_updated_at = result['last_updated_at']
                
                all_metrics.append({
                    'board': board.name,
                    'impressions': result['impressions'],
                    'clicks': result['clicks'],
                    'applications': result['applications'],
                    'cost_spent': float(result['cost_spent'])
                })
            else:
                errors.append(f"{board.name}: {result.get('error')}")
        
        except Exception as e:
            errors.append(f"{dist.board.name}: {str(e)}")
    
    db.commit()
    
    return {
        'success': len(errors) == 0,
        'metrics': all_metrics,
        'errors': errors
    }
```

---

## Due to character limits, I'll create the remaining Phase 2 files in a separate prompt file.

**How to create this file in Cursor:**

1. Navigate to: `services/api/app/services/`
2. Create file: `distribution_engine.py`
3. Paste all the code above
4. Save (Ctrl+S)

---

**Would you like me to:**
1. Continue with Phase 2 (Part 2) - API routes and frontend UI?
2. Move to Phase 3 - Candidate Pipeline CRM?

Let me know and I'll create the next prompt file!
