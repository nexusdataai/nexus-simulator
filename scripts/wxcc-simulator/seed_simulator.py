#!/usr/bin/env python3
"""
WXCC Simulator Seed Script

Seeds the WXCC simulator with sample tasks and recordings for testing.
Can be run standalone or via the admin API.

Usage:
    # Seed with default settings (10 tasks over 7 days)
    python seed_simulator.py
    
    # Seed with custom settings
    python seed_simulator.py --tasks 50 --days 14 --include-recordings
    
    # Seed via API (if gateway is running)
    python seed_simulator.py --api http://localhost:8000 --tasks 20
    
    # Reset simulator first
    python seed_simulator.py --reset --tasks 20
    
    # Upload local sample recordings to S3 (one-time setup for Docker)
    python seed_simulator.py --upload-samples --bucket my-bucket
"""

import os
import sys
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Detection - Load .env.local and auto-detect bucket
# ═══════════════════════════════════════════════════════════════════════════════

def load_env_local():
    """Load environment variables from .env.local in project root."""
    # Find .env.local in project root (starhub-backend/)
    project_root = Path(__file__).parent.parent.parent
    env_files = [
        project_root / ".env.local",
        project_root / ".env",
    ]
    
    for env_file in env_files:
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
            break


def get_default_simulator_bucket():
    """
    Get the simulator bucket name from environment or construct from naming convention.
    
    Priority:
    1. WXCC_SIMULATOR_BUCKET env var (explicit override)
    2. Construct from CAPABILITY_NAME and ENVIRONMENT: {capability}-{env}-wxcc-simulator
    """
    # First, load .env.local if not already loaded
    load_env_local()
    
    # Check for explicit bucket setting
    explicit_bucket = os.getenv("WXCC_SIMULATOR_BUCKET", "")
    if explicit_bucket:
        return explicit_bucket
    
    # Auto-construct from naming convention
    capability = os.getenv("CAPABILITY_NAME", "call-processing")
    environment = os.getenv("ENVIRONMENT", "dev")
    
    bucket_name = f"{capability}-{environment}-wxcc-simulator"
    return bucket_name


# ═══════════════════════════════════════════════════════════════════════════════
# Table Formatting Utilities
# ═══════════════════════════════════════════════════════════════════════════════

class TableFormatter:
    """Utility class for creating ASCII tables."""
    
    STYLES = {
        "single": {"h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "lj": "├", "rj": "┤", "tj": "┬", "bj": "┴", "x": "┼"},
        "double": {"h": "═", "v": "║", "tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "lj": "╠", "rj": "╣", "tj": "╦", "bj": "╩", "x": "╬"},
        "rounded": {"h": "─", "v": "│", "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "lj": "├", "rj": "┤", "tj": "┬", "bj": "┴", "x": "┼"},
    }
    
    @classmethod
    def create_table(cls, headers: list, rows: list, col_widths: list = None, style: str = "single", title: str = None) -> str:
        """Create a formatted ASCII table."""
        s = cls.STYLES.get(style, cls.STYLES["single"])
        
        # Calculate column widths
        if col_widths is None:
            col_widths = []
            for i, header in enumerate(headers):
                max_width = len(str(header))
                for row in rows:
                    if i < len(row):
                        max_width = max(max_width, len(str(row[i])))
                col_widths.append(max_width + 2)
        
        total_width = sum(col_widths) + len(col_widths) + 1
        
        lines = []
        
        # Title
        if title:
            lines.append(s["tl"] + s["h"] * (total_width - 2) + s["tr"])
            lines.append(s["v"] + title.center(total_width - 2) + s["v"])
            lines.append(s["lj"] + s["tj"].join(s["h"] * w for w in col_widths) + s["rj"])
        else:
            lines.append(s["tl"] + s["tj"].join(s["h"] * w for w in col_widths) + s["tr"])
        
        # Headers
        header_cells = []
        for i, header in enumerate(headers):
            header_cells.append(str(header).center(col_widths[i]))
        lines.append(s["v"] + s["v"].join(header_cells) + s["v"])
        lines.append(s["lj"] + s["x"].join(s["h"] * w for w in col_widths) + s["rj"])
        
        # Data rows
        for row in rows:
            row_cells = []
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    row_cells.append((" " + str(cell)).ljust(col_widths[i]))
            lines.append(s["v"] + s["v"].join(row_cells) + s["v"])
        
        lines.append(s["bl"] + s["bj"].join(s["h"] * w for w in col_widths) + s["br"])
        
        return "\n".join(lines)
    
    @classmethod
    def create_banner(cls, text: str, width: int = 70, style: str = "double") -> str:
        """Create a centered banner."""
        s = cls.STYLES.get(style, cls.STYLES["double"])
        
        lines = [
            s["tl"] + s["h"] * (width - 2) + s["tr"],
            s["v"] + text.center(width - 2) + s["v"],
            s["bl"] + s["h"] * (width - 2) + s["br"],
        ]
        return "\n".join(lines)
    
    @classmethod
    def create_key_value_box(cls, data: dict, title: str = None, width: int = 75) -> str:
        """Create a key-value box."""
        s = cls.STYLES["single"]
        
        key_width = max(len(str(k)) for k in data.keys()) + 2
        val_width = width - key_width - 4
        
        lines = []
        
        if title:
            lines.append(s["tl"] + s["h"] * (width - 2) + s["tr"])
            lines.append(s["v"] + title.center(width - 2) + s["v"])
            lines.append(s["lj"] + s["h"] * (width - 2) + s["rj"])
        else:
            lines.append(s["tl"] + s["h"] * (width - 2) + s["tr"])
        
        for key, value in data.items():
            key_str = f" {key}".ljust(key_width)
            val_str = str(value)[:val_width].ljust(val_width)
            lines.append(f"{s['v']}{key_str}{s['v']}{val_str}{s['v']}")
        
        lines.append(s["bl"] + s["h"] * (width - 2) + s["br"])
        
        return "\n".join(lines)


formatter = TableFormatter()


# ═══════════════════════════════════════════════════════════════════════════════
# API Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_simulator_status(base_url: str) -> dict:
    """Get simulator status via API."""
    try:
        response = requests.get(f"{base_url}/api/v1/simulator/status", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"  Warning: Could not get status: {e}")
    return None


def get_tasks_from_api(base_url: str, org_id: str, token: str, days_back: int = 30) -> list:
    """Fetch tasks from the simulator API."""
    try:
        from_time = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp() * 1000)
        
        response = requests.get(
            f"{base_url}/api/v1/simulator/tasks",
            params={
                "from": from_time,
                "orgId": org_id,
                "channelType": "telephony",
                "pageSize": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        print(f"  Warning: Could not fetch tasks: {e}")
    return []


def display_final_state(base_url: str, org_id: str, token: str):
    """Display comprehensive final state of the simulator."""
    print("\n")
    print(formatter.create_banner("📊 SIMULATOR FINAL STATE", width=80))
    print()
    
    # Get status
    status = get_simulator_status(base_url)
    if status:
        status_data = {
            "Enabled": "✅ Yes" if status.get("enabled") else "❌ No",
            "Organization ID": status.get("org_id", "N/A"),
            "S3 Bucket": status.get("bucket", "N/A"),
            "S3 Prefix": status.get("prefix", "N/A"),
            "Total Tasks": status.get("task_count", 0),
            "Total Recordings": status.get("recording_count", 0),
            "Last Updated": str(status.get("last_updated", "N/A"))[:19],
        }
        print(formatter.create_key_value_box(status_data, "🔧 Simulator Status"))
        print()
    
    # Get tasks
    tasks = get_tasks_from_api(base_url, org_id, token)
    
    if not tasks:
        print("  ⚠️  No tasks found in simulator")
        return
    
    # Analyze tasks
    status_counts = defaultdict(int)
    direction_counts = defaultdict(int)
    queue_counts = defaultdict(int)
    tasks_with_recordings = 0
    
    for task in tasks:
        attrs = task.get("attributes", {})
        status_counts[attrs.get("status", "unknown")] += 1
        direction_counts[attrs.get("direction", "unknown")] += 1
        queue_name = attrs.get("queueName", "Unknown")
        queue_counts[queue_name] += 1
    
    # Summary statistics
    summary_data = {
        "Total Tasks": len(tasks),
        "Completed": status_counts.get("completed", 0),
        "Abandoned": status_counts.get("abandoned", 0),
        "Transferred": status_counts.get("transferred", 0),
        "Inbound": direction_counts.get("inbound", 0),
        "Outbound": direction_counts.get("outbound", 0),
    }
    print(formatter.create_key_value_box(summary_data, "📈 Task Statistics"))
    print()
    
    # Queue breakdown
    if queue_counts:
        queue_rows = []
        for i, (queue, count) in enumerate(sorted(queue_counts.items(), key=lambda x: -x[1]), 1):
            pct = (count / len(tasks)) * 100
            queue_rows.append([str(i), queue[:25], str(count), f"{pct:.1f}%"])
        
        print(formatter.create_table(
            headers=["#", "Queue Name", "Count", "Percentage"],
            rows=queue_rows,
            col_widths=[4, 27, 8, 12],
            title="📞 Tasks by Queue"
        ))
        print()
    
    # Status breakdown
    status_rows = []
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = (count / len(tasks)) * 100
        icon = "✅" if status == "completed" else "❌" if status == "abandoned" else "🔄"
        status_rows.append([icon, status.capitalize(), str(count), f"{pct:.1f}%"])
    
    print(formatter.create_table(
        headers=["", "Status", "Count", "Percentage"],
        rows=status_rows,
        col_widths=[3, 15, 8, 12],
        title="📊 Tasks by Status"
    ))
    print()
    
    # Task details table
    display_count = min(len(tasks), 20)  # Show up to 20 tasks
    if len(tasks) > display_count:
        banner_text = f"📋 Task Details (showing {display_count} of {len(tasks)} tasks)"
    else:
        banner_text = f"📋 All Tasks ({len(tasks)} total)"
    print(formatter.create_banner(banner_text, width=120, style="single"))
    print()
    
    task_rows = []
    for i, task in enumerate(tasks[:display_count], 1):
        attrs = task.get("attributes", {})
        task_id = task.get("id", "N/A")[:15] + "..."
        status = attrs.get("status", "N/A")[:10]
        direction = attrs.get("direction", "N/A")[:8]
        origin = attrs.get("origin", "N/A")[:15]
        destination = attrs.get("destination", "N/A")[:15]
        queue = attrs.get("queueName", "N/A")[:12]
        agent = attrs.get("agentName", "N/A")[:12]
        
        status_icon = "✅" if status == "completed" else "❌" if status == "abandoned" else "🔄"
        
        task_rows.append([
            str(i),
            task_id,
            f"{status_icon} {status}",
            direction,
            origin,
            destination,
            queue,
            agent,
        ])
    
    print(formatter.create_table(
        headers=["#", "Task ID", "Status", "Dir", "Origin", "Destination", "Queue", "Agent"],
        rows=task_rows,
        col_widths=[3, 18, 14, 10, 17, 17, 14, 14],
    ))


def seed_via_api(
    base_url: str,
    num_tasks: int,
    days_back: int,
    include_recordings: bool,
    org_id: str = None,
    token: str = None,
    reset_first: bool = False,
    use_current_time: bool = False,
) -> dict:
    """
    Seed simulator via the admin API.
    
    Args:
        base_url: Base URL of the gateway (e.g., http://localhost:8000)
        num_tasks: Number of tasks to create
        days_back: Spread tasks over this many days
        include_recordings: Whether to include mock recordings
        org_id: Organization ID to use
        token: Authentication token
        reset_first: Whether to reset simulator before seeding
        use_current_time: Create tasks with current timestamp (for testing)
        
    Returns:
        API response data
    """
    if not REQUESTS_AVAILABLE:
        print("Error: requests library not installed. Install with: pip install requests")
        sys.exit(1)
    
    print()
    print(formatter.create_banner("🌱 WXCC Simulator Seeder", width=70))
    print()
    
    # Show configuration
    config_data = {
        "API URL": base_url,
        "Tasks to Create": num_tasks,
        "Days Back": days_back if not use_current_time else "N/A (using current time)",
        "Use Current Time": "✅ Yes" if use_current_time else "❌ No",
        "Include Recordings": "✅ Yes" if include_recordings else "❌ No",
        "Organization ID": org_id or "sim-org-001",
        "Reset First": "✅ Yes" if reset_first else "❌ No",
    }
    print(formatter.create_key_value_box(config_data, "⚙️  Seeding Configuration"))
    print()
    
    # Reset if requested
    if reset_first:
        print("🔄 Resetting simulator...")
        response = requests.post(f"{base_url}/api/v1/simulator/reset", timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Reset complete: {result.get('message')}")
        else:
            print(f"   ❌ Reset failed: {response.status_code} - {response.text}")
        print()
    
    # Seed data
    print("🌱 Seeding data...")
    payload = {
        "num_tasks": num_tasks,
        "include_recordings": include_recordings,
        "days_back": days_back,
        "use_current_time": use_current_time,
    }
    if org_id:
        payload["org_id"] = org_id
    
    response = requests.post(
        f"{base_url}/api/v1/simulator/seed",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ {result.get('message')}")
        
        if result.get('data'):
            data = result['data']
            seed_result = {
                "Tasks Created": data.get('tasks_created', 0),
                "Recordings Created": data.get('recordings_created', 0),
                "Organization ID": data.get('org_id', org_id),
            }
            # Show local recordings info if available
            if data.get('used_local_recordings'):
                seed_result["Audio Source"] = f"🎵 Local files ({data.get('local_recordings_available', 0)} available)"
            elif data.get('recordings_created', 0) > 0:
                seed_result["Audio Source"] = "🔊 Generated (synthetic)"
            print()
            print(formatter.create_key_value_box(seed_result, "📦 Seeding Results"))
        
        # Display final state
        display_final_state(base_url, org_id or "sim-org-001", token or "test-token-12345")
        
        return result
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        return {"success": False, "error": response.text}


async def seed_directly(
    bucket: str,
    prefix: str,
    region: str,
    num_tasks: int,
    days_back: int,
    include_recordings: bool,
    org_id: str,
    reset_first: bool = False,
    use_current_time: bool = False,
) -> dict:
    """
    Seed simulator directly by writing to S3.
    
    This is useful when the gateway is not running.
    """
    if not BOTO3_AVAILABLE:
        print("Error: boto3 library not installed. Install with: pip install boto3")
        sys.exit(1)
    
    print()
    print(formatter.create_banner("🌱 WXCC Simulator Seeder (Direct S3)", width=70))
    print()
    
    # Import the service
    from src.services.wxcc_simulator_service import WXCCSimulatorService
    from src.models.wxcc_simulator_models import SeedDataRequest
    
    # Show configuration
    config_data = {
        "S3 Bucket": bucket,
        "S3 Prefix": prefix,
        "AWS Region": region,
        "Tasks to Create": num_tasks,
        "Days Back": days_back if not use_current_time else "N/A (using current time)",
        "Use Current Time": "✅ Yes" if use_current_time else "❌ No",
        "Include Recordings": "✅ Yes" if include_recordings else "❌ No",
        "Organization ID": org_id,
        "Reset First": "✅ Yes" if reset_first else "❌ No",
    }
    print(formatter.create_key_value_box(config_data, "⚙️  Seeding Configuration"))
    print()
    
    # Create service
    service = WXCCSimulatorService(
        bucket=bucket,
        prefix=prefix,
        region=region,
        org_id=org_id,
    )
    
    # Reset if requested
    if reset_first:
        print("🔄 Resetting simulator...")
        result = await service.reset_data()
        print(f"   ✅ {result.message}")
        print()
    
    # Seed data
    print("🌱 Seeding data...")
    request = SeedDataRequest(
        num_tasks=num_tasks,
        include_recordings=include_recordings,
        days_back=days_back,
        use_current_time=use_current_time,
        org_id=org_id,
    )
    
    result = await service.seed_data(request)
    
    if result.success:
        print(f"   ✅ {result.message}")
        
        if result.data:
            data = result.data
            seed_result = {
                "Tasks Created": data.get('tasks_created', 0),
                "Recordings Created": data.get('recordings_created', 0),
                "Organization ID": data.get('org_id', org_id),
            }
            # Show local recordings info if available
            if data.get('used_local_recordings'):
                seed_result["Audio Source"] = f"🎵 Local files ({data.get('local_recordings_available', 0)} available)"
            elif data.get('recordings_created', 0) > 0:
                seed_result["Audio Source"] = "🔊 Generated (synthetic)"
            print()
            print(formatter.create_key_value_box(seed_result, "📦 Seeding Results"))
        
        # Display final state
        print()
        print(formatter.create_banner("📊 FINAL STATE", width=70))
        status = await service.get_status()
        
        status_data = {
            "Enabled": "✅ Yes" if status.enabled else "❌ No",
            "Organization ID": status.org_id,
            "S3 Bucket": status.bucket,
            "S3 Prefix": status.prefix,
            "Total Tasks": status.task_count,
            "Total Recordings": status.recording_count,
            "Last Updated": str(status.last_updated)[:19] if status.last_updated else "N/A",
        }
        print()
        print(formatter.create_key_value_box(status_data, "🔧 Simulator Status"))
        
        # Load and display task breakdown
        data = await service._load_data()
        if data.tasks:
            status_counts = defaultdict(int)
            direction_counts = defaultdict(int)
            
            for stored_task in data.tasks.values():
                task = stored_task.task
                status_counts[task.attributes.status] += 1
                direction_counts[task.attributes.direction] += 1
            
            print()
            summary_data = {
                "Total Tasks": len(data.tasks),
                "Total Recordings": len(data.recordings),
                "Completed": status_counts.get("completed", 0),
                "Abandoned": status_counts.get("abandoned", 0),
                "Transferred": status_counts.get("transferred", 0),
                "Inbound": direction_counts.get("inbound", 0),
                "Outbound": direction_counts.get("outbound", 0),
            }
            print(formatter.create_key_value_box(summary_data, "📈 Task Statistics"))
            
            # Task table
            print()
            display_count = min(len(data.tasks), 20)
            task_items = list(data.tasks.items())[:display_count]
            
            task_rows = []
            for i, (task_id, stored_task) in enumerate(task_items, 1):
                task = stored_task.task
                attrs = task.attributes
                has_rec = "✅" if stored_task.recording_ids else "❌"
                status_icon = "✅" if attrs.status == "completed" else "❌" if attrs.status == "abandoned" else "🔄"
                
                task_rows.append([
                    str(i),
                    task_id[:15] + "...",
                    f"{status_icon} {attrs.status[:10]}",
                    attrs.direction[:8],
                    attrs.origin[:15] if attrs.origin else "N/A",
                    has_rec,
                ])
            
            if len(data.tasks) > display_count:
                title = f"📋 Task Details (showing {display_count} of {len(data.tasks)} tasks)"
            else:
                title = f"📋 All Tasks ({len(data.tasks)} total)"
            
            print(formatter.create_table(
                headers=["#", "Task ID", "Status", "Dir", "Origin", "Rec"],
                rows=task_rows,
                col_widths=[3, 18, 14, 10, 17, 5],
                title=title
            ))
    else:
        print(f"   ❌ Failed: {result.message}")
    
    return result.model_dump()


def upload_sample_recording(
    bucket: str,
    prefix: str,
    region: str,
    sample_file: str,
) -> str:
    """
    Upload a sample recording file to S3.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 prefix
        region: AWS region
        sample_file: Path to local sample file
        
    Returns:
        S3 key of uploaded file
    """
    if not BOTO3_AVAILABLE:
        print("Error: boto3 not available")
        return None
    
    s3 = boto3.client("s3", region_name=region)
    
    import uuid
    recording_id = str(uuid.uuid4())
    s3_key = f"{prefix}/recordings/{recording_id}.wav"
    
    print(f"Uploading {sample_file} to s3://{bucket}/{s3_key}...")
    
    with open(sample_file, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=f.read(),
            ContentType="audio/wav"
        )
    
    print(f"  ✅ Uploaded successfully")
    return s3_key


def upload_all_sample_recordings(
    bucket: str,
    prefix: str,
    region: str,
) -> dict:
    """
    Upload all local sample recordings to S3 sample-recordings/ prefix.
    
    This is a one-time operation to populate S3 with sample audio files
    that Docker containers can use when seeding the simulator.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 prefix (sample-recordings/ will be appended)
        region: AWS region
        
    Returns:
        dict with upload results
    """
    if not BOTO3_AVAILABLE:
        print("Error: boto3 not available. Install with: pip install boto3")
        return {"success": False, "error": "boto3 not available"}
    
    # Path to local recordings directory
    recordings_dir = Path(__file__).parent / "recordings"
    
    if not recordings_dir.exists():
        print(f"Error: Recordings directory not found: {recordings_dir}")
        return {"success": False, "error": "Recordings directory not found"}
    
    # Find all audio files
    audio_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(recordings_dir.glob(f"*{ext}"))
    
    if not audio_files:
        print(f"No audio files found in {recordings_dir}")
        return {"success": False, "error": "No audio files found"}
    
    print()
    print(formatter.create_banner("📤 Upload Sample Recordings to S3", width=70))
    print()
    
    config_data = {
        "S3 Bucket": bucket,
        "S3 Prefix": f"{prefix}/sample-recordings/",
        "AWS Region": region,
        "Local Directory": str(recordings_dir),
        "Files Found": len(audio_files),
    }
    print(formatter.create_key_value_box(config_data, "⚙️  Upload Configuration"))
    print()
    
    s3 = boto3.client("s3", region_name=region)
    sample_prefix = f"{prefix}/sample-recordings/"
    
    uploaded = 0
    failed = 0
    results = []
    
    content_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg',
        '.flac': 'audio/flac',
    }
    
    print("📁 Uploading files...")
    for audio_file in sorted(audio_files):
        filename = audio_file.name
        ext = audio_file.suffix.lower()
        s3_key = f"{sample_prefix}{filename}"
        content_type = content_types.get(ext, 'audio/mpeg')
        
        try:
            with open(audio_file, 'rb') as f:
                file_content = f.read()
            
            s3.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            
            size_kb = len(file_content) / 1024
            print(f"   ✅ {filename} ({size_kb:.1f} KB) -> s3://{bucket}/{s3_key}")
            uploaded += 1
            results.append({"file": filename, "s3_key": s3_key, "status": "uploaded"})
            
        except Exception as e:
            print(f"   ❌ {filename} - Failed: {e}")
            failed += 1
            results.append({"file": filename, "error": str(e), "status": "failed"})
    
    print()
    summary_data = {
        "Files Uploaded": uploaded,
        "Files Failed": failed,
        "S3 Location": f"s3://{bucket}/{sample_prefix}",
    }
    print(formatter.create_key_value_box(summary_data, "📊 Upload Summary"))
    
    return {
        "success": failed == 0,
        "uploaded": uploaded,
        "failed": failed,
        "results": results,
        "s3_prefix": sample_prefix,
    }


def show_status(args):
    """Show simulator status."""
    print()
    print(formatter.create_banner("📊 WXCC Simulator Status", width=70))
    print()
    
    if args.api:
        status = get_simulator_status(args.api)
        if status:
            status_data = {
                "Enabled": "✅ Yes" if status.get("enabled") else "❌ No",
                "Organization ID": status.get("org_id", "N/A"),
                "S3 Bucket": status.get("bucket", "N/A"),
                "S3 Prefix": status.get("prefix", "N/A"),
                "Total Tasks": status.get("task_count", 0),
                "Total Recordings": status.get("recording_count", 0),
                "Last Updated": str(status.get("last_updated", "N/A"))[:19],
            }
            print(formatter.create_key_value_box(status_data, "🔧 Simulator Status"))
            
            # Also fetch and display tasks
            org_id = args.org_id or os.getenv("WXCC_SIM_ORG_ID", "sim-org-001")
            token = os.getenv("WXCC_SIM_TOKEN", "test-token-12345")
            display_final_state(args.api, org_id, token)
        else:
            print("  ❌ Could not retrieve status")
    else:
        async def check_status():
            from src.services.wxcc_simulator_service import WXCCSimulatorService
            service = WXCCSimulatorService(
                bucket=args.bucket,
                prefix=args.prefix,
                region=args.region,
            )
            status = await service.get_status()
            
            status_data = {
                "Enabled": "✅ Yes" if status.enabled else "❌ No",
                "Organization ID": status.org_id,
                "S3 Bucket": status.bucket,
                "S3 Prefix": status.prefix,
                "Total Tasks": status.task_count,
                "Total Recordings": status.recording_count,
                "Last Updated": str(status.last_updated)[:19] if status.last_updated else "N/A",
            }
            print(formatter.create_key_value_box(status_data, "🔧 Simulator Status"))
        
        asyncio.run(check_status())


def main():
    parser = argparse.ArgumentParser(
        description="Seed WXCC Simulator with sample data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Seed with defaults (10 tasks, 7 days, with recordings)
    python seed_simulator.py --api http://localhost:8000
    
    # Seed 50 tasks over 14 days
    python seed_simulator.py --api http://localhost:8000 --tasks 50 --days 14
    
    # Reset and re-seed
    python seed_simulator.py --api http://localhost:8000 --reset --tasks 30
    
    # Seed with current timestamp (for testing with short time windows)
    python seed_simulator.py --api http://localhost:8000 --reset --tasks 5 --now
    
    # Show simulator status
    python seed_simulator.py --api http://localhost:8000 --status
    
    # Direct S3 seeding (no gateway required)
    python seed_simulator.py --bucket my-bucket --tasks 20
    
    # Upload local sample recordings to S3 (one-time setup for Docker)
    python seed_simulator.py --upload-samples --bucket my-bucket
        """
    )
    
    parser.add_argument(
        "--api",
        type=str,
        help="Seed via API (provide gateway URL, e.g., http://localhost:8000)"
    )
    parser.add_argument(
        "--tasks",
        type=int,
        default=10,
        help="Number of tasks to create (default: 10)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Spread tasks over this many days (default: 7)"
    )
    parser.add_argument(
        "--no-recordings",
        action="store_true",
        help="Don't create mock recordings"
    )
    parser.add_argument(
        "--org-id",
        type=str,
        default=None,
        help="Organization ID to use"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset simulator before seeding"
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Create tasks with current timestamp (useful for testing with short time windows)"
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,  # Will be auto-detected if not provided
        help="S3 bucket name (default: auto-detected from .env.local as {capability}-{env}-wxcc-simulator)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=os.getenv("WXCC_SIMULATOR_PREFIX", "wxcc-simulator"),
        help="S3 prefix (default: wxcc-simulator)"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--upload-recording",
        type=str,
        help="Upload a sample recording file to S3"
    )
    parser.add_argument(
        "--upload-samples",
        action="store_true",
        help="Upload all local sample recordings to S3 (one-time setup for Docker)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show simulator status"
    )
    
    args = parser.parse_args()
    
    # Auto-detect bucket if not provided
    if args.bucket is None:
        args.bucket = get_default_simulator_bucket()
        if args.bucket and not args.api:
            capability = os.getenv("CAPABILITY_NAME", "call-processing")
            environment = os.getenv("ENVIRONMENT", "dev")
            print(f"📦 Auto-detected bucket: {args.bucket} (from {capability}/{environment})")
    
    include_recordings = not args.no_recordings
    org_id = args.org_id or os.getenv("WXCC_SIM_ORG_ID", "sim-org-001")
    token = os.getenv("WXCC_SIM_TOKEN", "test-token-12345")
    
    # Handle status check
    if args.status:
        show_status(args)
        return
    
    # Handle bulk upload of sample recordings
    if args.upload_samples:
        if not args.bucket:
            print("Error: --bucket is required for --upload-samples")
            sys.exit(1)
        
        result = upload_all_sample_recordings(
            bucket=args.bucket,
            prefix=args.prefix,
            region=args.region,
        )
        
        if result["success"]:
            print()
            print("─" * 70)
            print(f"✅ Successfully uploaded {result['uploaded']} sample recordings to S3")
            print(f"   Docker containers can now use these samples when seeding.")
            print("─" * 70)
        else:
            print()
            print(f"⚠️  Upload completed with {result['failed']} failures")
        return
    
    # Handle recording upload
    if args.upload_recording:
        if not os.path.exists(args.upload_recording):
            print(f"Error: File not found: {args.upload_recording}")
            sys.exit(1)
        
        if not args.bucket:
            print("Error: --bucket is required for upload")
            sys.exit(1)
        
        s3_key = upload_sample_recording(
            bucket=args.bucket,
            prefix=args.prefix,
            region=args.region,
            sample_file=args.upload_recording,
        )
        print(f"Recording S3 key: {s3_key}")
        return
    
    # Seed via API or directly
    if args.api:
        result = seed_via_api(
            base_url=args.api,
            num_tasks=args.tasks,
            days_back=args.days,
            include_recordings=include_recordings,
            org_id=org_id,
            token=token,
            reset_first=args.reset,
            use_current_time=args.now,
        )
    else:
        if not args.bucket:
            print("Error: Could not determine S3 bucket.")
            print("       Set WXCC_SIMULATOR_BUCKET env, or ensure ENVIRONMENT is set in .env.local")
            print("       Or use --api to seed via the running gateway")
            sys.exit(1)
        
        result = asyncio.run(seed_directly(
            bucket=args.bucket,
            prefix=args.prefix,
            region=args.region,
            num_tasks=args.tasks,
            days_back=args.days,
            include_recordings=include_recordings,
            org_id=org_id,
            reset_first=args.reset,
            use_current_time=args.now,
        ))
    
    print()
    print("─" * 70)
    print(f"✅ Done! Timestamp: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    print("─" * 70)


if __name__ == "__main__":
    main()
