# WXCC Simulator

A Webex Contact Center (WXCC) simulator that provides API-compatible endpoints for testing the call processing pipeline without access to the real WXCC system.

## Features

- **WXCC-Compatible APIs**: Exposes the same endpoints as the real WXCC API
  - `GET /v1/tasks` - List tasks with filtering
  - `POST /v1/captures/query` - Get recording URLs for task IDs
  - Recording file streaming

- **Admin APIs**: For test data management
  - Create/update/delete mock tasks
  - Upload recording files
  - Seed with sample data
  - Reset simulator

- **S3 Backend**: All data stored in S3 for persistence

## Quick Start

### 1. Configure Environment

Add to your `.env` file:

```bash
# Enable simulator
WXCC_SIMULATOR_ENABLED=true

# S3 storage
WXCC_SIMULATOR_BUCKET=your-bucket-name
WXCC_SIMULATOR_PREFIX=wxcc-simulator

# Authentication
WXCC_SIM_TOKEN=test-token-12345
WXCC_SIM_ORG_ID=sim-org-001

# Optional: Base URL for recording URLs
WXCC_SIMULATOR_BASE_URL=http://localhost:8000
```

### 2. Start the Gateway

```bash
cd /opt/mycode/trilogy/starhub-backend
python mcp_http_gateway.py
```

### 3. Seed Sample Data

```bash
# Via API (gateway must be running)
python scripts/wxcc-simulator/seed_simulator.py --api http://localhost:8000 --tasks 20

# Or directly to S3
python scripts/wxcc-simulator/seed_simulator.py --bucket your-bucket --tasks 20
```

### 4. Test with Call Processing Scripts

```bash
cd scripts/call-scripts

# Point to simulator instead of real WXCC
export WEBEX_BASE_URL=http://localhost:8000/v1
export ACCESS_TOKEN=test-token-12345

python test_wxcc.py
```

## API Endpoints

### WXCC-Compatible (require Bearer token)

All APIs are mounted at `/api/v1/simulator`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/simulator/tasks` | GET | List tasks with from/to/orgId/channelType filters |
| `/api/v1/simulator/captures/query` | POST | Get recordings for task IDs |
| `/api/v1/simulator/recordings/{id}` | GET | Stream recording file |
| `/api/v1/simulator/recordings/{id}/url` | GET | Get presigned S3 URL |

### Admin (no auth required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/simulator/status` | GET | Get simulator status |
| `/api/v1/simulator/tasks` | POST | Create a task |
| `/api/v1/simulator/tasks/{id}` | PUT | Update a task |
| `/api/v1/simulator/tasks/{id}` | DELETE | Delete a task |
| `/api/v1/simulator/tasks/{id}/recordings` | POST | Upload recording |
| `/api/v1/simulator/seed` | POST | Seed sample data |
| `/api/v1/simulator/reset` | POST | Reset all data |
| `/api/v1/simulator/health` | GET | Health check |

## Local Recordings

The simulator can use real audio files instead of generating synthetic tones. Place audio files in the `recordings/` directory:

```
scripts/wxcc-simulator/recordings/
├── 1_Badri.mp3
├── 2_Fida.mp3
├── 3_Louise.mp3
└── ...
```

**Supported formats:** MP3, WAV, M4A, OGG, FLAC

When seeding data, the simulator will:
1. **If local recordings exist**: Randomly pick from available files for each task
2. **If no local recordings**: Generate synthetic WAV files with tone audio

This allows testing with realistic call recordings to verify transcription and AI analysis work correctly.

## S3 Data Structure

```
s3://{bucket}/{prefix}/
├── data.json           # Task and recording metadata
└── recordings/
    ├── {recording-id}.mp3   # Uploaded from local recordings
    ├── {recording-id}.wav   # Or generated synthetic audio
    └── ...
```

## Usage Examples

### Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/simulator/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "Test Call",
    "origin": "+6591234567",
    "destination": "+6560001111",
    "duration_seconds": 300,
    "status": "completed"
  }'
```

### Query Tasks

```bash
curl -X GET "http://localhost:8000/api/v1/simulator/tasks?orgId=sim-org-001&channelType=telephony" \
  -H "Authorization: Bearer test-token-12345"
```

### Get Recordings

```bash
curl -X POST http://localhost:8000/api/v1/simulator/captures/query \
  -H "Authorization: Bearer test-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"query": {"taskIds": ["task-uuid-here"]}}'
```

### Seed Sample Data

```bash
curl -X POST http://localhost:8000/api/v1/simulator/seed \
  -H "Content-Type: application/json" \
  -d '{
    "num_tasks": 50,
    "include_recordings": true,
    "days_back": 7
  }'
```

## Integration with Call Processing

The simulator is designed to be a drop-in replacement for the real WXCC API:

```python
# Original code pointing to real WXCC
api = WXCCAPI(
    base_url="https://api.wxcc-us1.cisco.com/v1",
    access_token=real_token,
    org_id=real_org_id,
)

# Switch to simulator for testing
api = WXCCAPI(
    base_url="http://localhost:8000/v1",
    access_token="test-token-12345",
    org_id="sim-org-001",
)

# Same code works with both!
tasks = api.get_tasks(days_back=7)
```

