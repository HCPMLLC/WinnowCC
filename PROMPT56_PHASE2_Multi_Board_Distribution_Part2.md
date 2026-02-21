# PHASE 2 PART 2: Distribution API Routes & Frontend UI

**This continues from PHASE2_Part1.md - make sure you've completed Part 1 first!**

## Step 5: Seed Job Boards Data

Before we can use the distribution system, we need to add some job boards to the database.

### 5.1 - Create Seed Data Script

**File to create:** `services/api/app/db/seed_boards.py`

**Full path:** `services/api/app/db/seed_boards.py`

**Code to add:**

```python
"""
Seed job boards data.
Run this once to populate the job_boards table.
"""
import uuid
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.distribution import JobBoard


def seed_job_boards():
    """Create initial job board records."""
    db = SessionLocal()
    
    boards = [
        {
            'id': uuid.uuid4(),
            'name': 'Mock Board (Testing)',
            'slug': 'mock-board',
            'api_endpoint': 'http://localhost:8000/mock',
            'requires_api_key': False,
            'is_active': True,
            'config': {
                'supports_metrics': True,
                'supports_updates': True
            }
        },
        {
            'id': uuid.uuid4(),
            'name': 'Test Board',
            'slug': 'test-board',
            'api_endpoint': 'http://localhost:8000/test',
            'requires_api_key': False,
            'is_active': True,
            'config': {
                'supports_metrics': True,
                'supports_updates': True
            }
        },
        # Future real boards (inactive for now):
        {
            'id': uuid.uuid4(),
            'name': 'Indeed',
            'slug': 'indeed',
            'api_endpoint': 'https://api.indeed.com/v1',
            'requires_api_key': True,
            'is_active': False,
            'config': {
                'supports_metrics': True,
                'supports_updates': True,
                'cost_per_click': 1.50
            }
        },
        {
            'id': uuid.uuid4(),
            'name': 'LinkedIn Jobs',
            'slug': 'linkedin',
            'api_endpoint': 'https://api.linkedin.com/v2/jobs',
            'requires_api_key': True,
            'is_active': False,
            'config': {
                'supports_metrics': True,
                'supports_updates': True
            }
        },
        {
            'id': uuid.uuid4(),
            'name': 'Google for Jobs',
            'slug': 'google-jobs',
            'api_endpoint': 'https://jobs.google.com/api',
            'requires_api_key': False,
            'is_active': False,
            'config': {
                'supports_metrics': True,
                'supports_updates': False,
                'note': 'Uses structured data, not direct API'
            }
        },
    ]
    
    # Check if boards already exist
    existing = db.query(JobBoard).count()
    if existing > 0:
        print(f"Job boards already seeded ({existing} boards found). Skipping.")
        db.close()
        return
    
    # Add boards
    for board_data in boards:
        board = JobBoard(**board_data)
        db.add(board)
    
    db.commit()
    print(f"Seeded {len(boards)} job boards successfully!")
    db.close()


if __name__ == '__main__':
    seed_job_boards()
```

### 5.2 - Run the Seed Script

**In PowerShell** (make sure you're in `services/api` with venv activated):

```powershell
python -m app.db.seed_boards
```

You should see:
```
Seeded 5 job boards successfully!
```

---

## Step 6: Create Distribution API Routes

### File to create: `services/api/app/routers/distribution.py`

**Full path:** `services/api/app/routers/distribution.py`

**What this file does:**
- API endpoints for managing job distribution
- Connect to boards, distribute jobs, sync changes, fetch metrics

**Code to add:**

```python
"""
Distribution API routes.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import require_employer
from app.models.distribution import (
    JobBoard,
    EmployerBoardConnection,
    JobDistribution,
    DistributionMetric
)
from app.services import distribution_engine


router = APIRouter(prefix="/api/employer/distribution", tags=["distribution"])


# --- Pydantic Schemas ---

class BoardConnectionCreate(BaseModel):
    board_slug: str
    api_key: str | None = None
    credentials: dict = {}


class DistributeJobRequest(BaseModel):
    job_id: str
    board_slugs: List[str]


class BoardInfo(BaseModel):
    id: str
    name: str
    slug: str
    requires_api_key: bool
    is_active: bool
    is_connected: bool


class DistributionStatus(BaseModel):
    board_name: str
    board_slug: str
    status: str
    external_job_id: str | None
    posted_at: str | None
    last_synced_at: str | None
    error_message: str | None
    metrics: dict | None


# --- Routes ---

@router.get("/boards", response_model=List[BoardInfo])
async def list_boards(
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    List all available job boards.
    Shows which ones the employer is connected to.
    """
    employer_id = current_user.employer_profile.id
    
    boards = db.query(JobBoard).all()
    
    result = []
    for board in boards:
        # Check if employer is connected
        connection = db.query(EmployerBoardConnection).filter(
            EmployerBoardConnection.employer_id == employer_id,
            EmployerBoardConnection.board_id == board.id
        ).first()
        
        result.append(BoardInfo(
            id=str(board.id),
            name=board.name,
            slug=board.slug,
            requires_api_key=board.requires_api_key,
            is_active=board.is_active,
            is_connected=connection.is_connected if connection else False
        ))
    
    return result


@router.post("/connect")
async def connect_to_board(
    request: BoardConnectionCreate,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Connect employer to a job board.
    Stores API key and validates credentials.
    """
    employer_id = current_user.employer_profile.id
    
    # Get board
    board = db.query(JobBoard).filter(JobBoard.slug == request.board_slug).first()
    if not board:
        raise HTTPException(status_code=404, detail=f"Board {request.board_slug} not found")
    
    if not board.is_active:
        raise HTTPException(status_code=400, detail=f"Board {request.board_slug} is not active yet")
    
    # Check if already connected
    existing = db.query(EmployerBoardConnection).filter(
        EmployerBoardConnection.employer_id == employer_id,
        EmployerBoardConnection.board_id == board.id
    ).first()
    
    if existing:
        # Update existing connection
        existing.api_key = request.api_key
        existing.credentials = request.credentials
        existing.is_connected = True
    else:
        # Create new connection
        connection = EmployerBoardConnection(
            id=uuid.uuid4(),
            employer_id=employer_id,
            board_id=board.id,
            api_key=request.api_key,
            credentials=request.credentials,
            is_connected=True
        )
        db.add(connection)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Connected to {board.name}"
    }


@router.post("/distribute")
async def distribute_job(
    request: DistributeJobRequest,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Distribute a job to multiple boards.
    """
    employer_id = current_user.employer_profile.id
    
    result = await distribution_engine.distribute_job(
        job_id=uuid.UUID(request.job_id),
        employer_id=employer_id,
        board_slugs=request.board_slugs,
        db=db
    )
    
    return result


@router.post("/jobs/{job_id}/sync")
async def sync_job(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Sync job changes to all boards where it's distributed.
    """
    result = await distribution_engine.sync_job(
        job_id=uuid.UUID(job_id),
        db=db
    )
    
    return result


@router.delete("/jobs/{job_id}/remove")
async def remove_job(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Remove job from all boards.
    """
    result = await distribution_engine.remove_job_from_boards(
        job_id=uuid.UUID(job_id),
        db=db
    )
    
    return result


@router.get("/jobs/{job_id}/status", response_model=List[DistributionStatus])
async def get_distribution_status(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Get distribution status and metrics for a job across all boards.
    """
    distributions = db.query(JobDistribution).filter(
        JobDistribution.job_id == uuid.UUID(job_id)
    ).all()
    
    result = []
    for dist in distributions:
        metrics_data = None
        if dist.metrics:
            metrics_data = {
                'impressions': dist.metrics.impressions,
                'clicks': dist.metrics.clicks,
                'applications': dist.metrics.applications,
                'cost_spent': float(dist.metrics.cost_spent)
            }
        
        result.append(DistributionStatus(
            board_name=dist.board.name,
            board_slug=dist.board.slug,
            status=dist.distribution_status,
            external_job_id=dist.external_job_id,
            posted_at=dist.posted_at.isoformat() if dist.posted_at else None,
            last_synced_at=dist.last_synced_at.isoformat() if dist.last_synced_at else None,
            error_message=dist.error_message,
            metrics=metrics_data
        ))
    
    return result


@router.post("/jobs/{job_id}/fetch-metrics")
async def fetch_metrics(
    job_id: str,
    current_user=Depends(require_employer),
    db: Session = Depends(get_db)
):
    """
    Fetch latest metrics from all boards for a job.
    """
    result = await distribution_engine.fetch_all_metrics(
        job_id=uuid.UUID(job_id),
        db=db
    )
    
    return result
```

### 6.1 - Register the Router

**File to edit:** `services/api/app/main.py`

**Find the section** where routers are included (around line 40):

```python
from app.routers import candidate, employer
```

**Change it to:**

```python
from app.routers import candidate, employer, distribution
```

**Then find** where routers are registered:

```python
app.include_router(candidate.router)
app.include_router(employer.router)
```

**Add this line below:**

```python
app.include_router(distribution.router)
```

---

## Step 7: Frontend - Board Connections Page

### File to create: `apps/web/app/employer/boards/page.tsx`

**Full path:** `apps/web/app/employer/boards/page.tsx`

**What this file does:**
- Shows available job boards
- Allows employer to connect to boards
- Displays connection status

**Code to add:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface Board {
  id: string;
  name: string;
  slug: string;
  requires_api_key: boolean;
  is_active: boolean;
  is_connected: boolean;
}

export default function BoardsPage() {
  const router = useRouter();
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  useEffect(() => {
    fetchBoards();
  }, []);

  const fetchBoards = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/employer/distribution/boards', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setBoards(data);
      }
    } catch (err) {
      console.error('Error fetching boards:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (board: Board) => {
    setConnecting(board.slug);

    try {
      const token = localStorage.getItem('access_token');
      
      // For mock board, no API key needed
      const payload = {
        board_slug: board.slug,
        api_key: null,
        credentials: {}
      };

      const response = await fetch('http://localhost:8000/api/employer/distribution/connect', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        alert(`Successfully connected to ${board.name}!`);
        fetchBoards(); // Refresh list
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to connect');
      }
    } catch (err) {
      alert('Error connecting to board');
    } finally {
      setConnecting(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading boards...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Job Board Connections</h1>
          <p className="text-gray-600 mt-1">Connect to boards to distribute your jobs</p>
        </div>
      </div>

      {/* Boards Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {boards.map((board) => (
            <div
              key={board.id}
              className={`bg-white rounded-xl shadow p-6 border-2 ${
                board.is_connected ? 'border-green-500' : 'border-gray-200'
              }`}
            >
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-semibold text-gray-900">{board.name}</h3>
                {board.is_connected && (
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                    ✓ Connected
                  </span>
                )}
              </div>

              <div className="space-y-2 text-sm text-gray-600 mb-4">
                <p>
                  <span className="font-medium">Status:</span>{' '}
                  {board.is_active ? (
                    <span className="text-green-600">Active</span>
                  ) : (
                    <span className="text-gray-500">Coming Soon</span>
                  )}
                </p>
                {board.requires_api_key && (
                  <p className="text-xs text-yellow-700">
                    ⚠️ Requires API key
                  </p>
                )}
              </div>

              {board.is_active && (
                <button
                  onClick={() => handleConnect(board)}
                  disabled={connecting === board.slug || board.is_connected}
                  className={`w-full px-4 py-2 rounded-lg font-medium transition ${
                    board.is_connected
                      ? 'bg-gray-100 text-gray-500 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {connecting === board.slug
                    ? 'Connecting...'
                    : board.is_connected
                    ? 'Already Connected'
                    : 'Connect'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**How to create this file:**
1. Navigate to: `apps/web/app/employer/`
2. Create folder: `boards`
3. Inside boards folder, create: `page.tsx`
4. Paste code above
5. Save

---

## Step 8: Add Distribution to Job Creation Flow

We need to update the job creation page to allow distribution.

**File to edit:** `apps/web/app/employer/jobs/new/page.tsx`

**Find the handleSubmit function** (around line 50)

**Replace the entire handleSubmit function** with this:

```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setLoading(true);
  setError(null);

  try {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    // Convert salary to integers
    const payload = {
      ...formData,
      salary_min: formData.salary_min ? parseInt(formData.salary_min) : null,
      salary_max: formData.salary_max ? parseInt(formData.salary_max) : null,
      status: 'active', // Immediately publish
    };

    // Step 1: Create the job
    const createResponse = await fetch('http://localhost:8000/api/employer/jobs', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (createResponse.status === 403) {
      const data = await createResponse.json();
      setError(data.detail || 'Job limit reached for your subscription tier');
      return;
    }

    if (!createResponse.ok) {
      throw new Error('Failed to create job');
    }

    const jobData = await createResponse.json();
    const jobId = jobData.id;

    // Step 2: Distribute to connected boards (mock-board and test-board)
    const distributeResponse = await fetch('http://localhost:8000/api/employer/distribution/distribute', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_id: jobId,
        board_slugs: ['mock-board', 'test-board']
      }),
    });

    if (distributeResponse.ok) {
      const distResult = await distributeResponse.json();
      console.log('Distribution result:', distResult);
    }

    // Success - redirect to jobs list
    router.push('/employer/jobs');
  } catch (err) {
    setError(err instanceof Error ? err.message : 'An error occurred');
  } finally {
    setLoading(false);
  }
};
```

---

## Step 9: Add Distribution Status to Jobs List

**File to edit:** `apps/web/app/employer/jobs/page.tsx`

**Add this new component** at the top of the file, before the main component:

```typescript
interface DistributionStatus {
  board_name: string;
  status: string;
  metrics: {
    impressions: number;
    clicks: number;
    applications: number;
  } | null;
}

function DistributionBadges({ jobId }: { jobId: string }) {
  const [distributions, setDistributions] = useState<DistributionStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDistribution();
  }, [jobId]);

  const fetchDistribution = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(
        `http://localhost:8000/api/employer/distribution/jobs/${jobId}/status`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setDistributions(data);
      }
    } catch (err) {
      console.error('Error fetching distribution:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || distributions.length === 0) return null;

  return (
    <div className="flex gap-2 mt-2">
      {distributions.map((dist, idx) => (
        <span
          key={idx}
          className={`px-2 py-1 rounded text-xs ${
            dist.status === 'live'
              ? 'bg-green-100 text-green-800'
              : dist.status === 'failed'
              ? 'bg-red-100 text-red-800'
              : 'bg-yellow-100 text-yellow-800'
          }`}
        >
          {dist.board_name}: {dist.status}
        </span>
      ))}
    </div>
  );
}
```

**Then, inside the job card** (around line 200), **add this line** after the job stats:

```typescript
<DistributionBadges jobId={job.id} />
```

---

## Step 10: Testing Phase 2

### 10.1 - Restart Everything

**Stop all services** (Ctrl+C in each terminal), then restart:

**Terminal 1:**
```powershell
cd infra
docker compose up -d
```

**Terminal 2:**
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3:**
```powershell
cd apps/web
npm run dev
```

### 10.2 - Test Distribution Flow

**Test 1: Connect to Boards**
1. Go to: `http://localhost:3000/employer/boards`
2. You should see Mock Board and Test Board
3. Click "Connect" on both boards
4. Status should change to "✓ Connected"

**Test 2: Create and Distribute Job**
1. Go to: `http://localhost:3000/employer/jobs/new`
2. Create a new job (fill in all fields)
3. Click "Publish Job"
4. Job should be created AND distributed to both boards

**Test 3: Check Distribution Status**
1. Go to: `http://localhost:3000/employer/jobs`
2. You should see your job listed
3. Below the job stats, you should see badges: "Mock Board: live" and "Test Board: live"

**Test 4: Fetch Metrics**
1. In browser console, or using curl:
```bash
curl -X POST http://localhost:8000/api/employer/distribution/jobs/{JOB_ID}/fetch-metrics \
  -H "Authorization: Bearer YOUR_TOKEN"
```
2. Should return fake metrics from both boards

---

## Success Criteria for Phase 2

✅ Job boards table seeded with mock boards  
✅ Distribution models and migrations complete  
✅ Board adapter interface implemented  
✅ Mock adapter generates fake metrics  
✅ Distribution engine distributes jobs  
✅ API routes for distribution created  
✅ Frontend boards connection page works  
✅ Jobs are auto-distributed on creation  
✅ Distribution status shows on jobs list  
✅ Can fetch metrics from boards  

---

## What's Next?

Phase 2 is complete! You now have:
- One-click job distribution to multiple boards
- Real-time status tracking
- Per-board metrics (impressions, clicks, applications, cost)
- Mock boards for testing

**Phase 3 will add:**
- Candidate Pipeline CRM
- Silver medalist auto-capture
- Kanban-style pipeline view
- Pipeline search for new jobs

Ready for Phase 3?
