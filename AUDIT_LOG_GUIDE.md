# Audit Log System Guide

## Overview

The audit logging system tracks every operation in your document processing application without requiring user login. It provides a complete trail of what happened to each file, when it happened, and what the results were.

## Features

### ✅ Complete Operation Tracking
- **File Upload**: Records filename, size, type, hash
- **Text Extraction**: Tracks method used, character count, duration
- **PII Detection**: Logs processing time, findings, model used
- **File Operations**: Documents saves, reviews, exports
- **Error Handling**: Captures failures with detailed error information

### ✅ Multiple Access Methods
- **Individual File Trails**: Complete history for specific files
- **Global Audit Logs**: All operations across the system
- **Filtered Views**: By operation type or file ID
- **JSON Export**: Export all logs for external analysis

## API Endpoints

### 1. Get All Audit Logs
```http
GET /audit/logs?limit=100&offset=0&operation_type=file_upload&file_id=abc123
```

**Parameters:**
- `limit`: Number of records to return (max 500)
- `offset`: Pagination offset
- `operation_type`: Filter by operation type
- `file_id`: Filter by specific file

**Response:**
```json
{
  "audit_logs": [
    {
      "id": 1,
      "operation_type": "file_upload",
      "file_id": "12345678-1234-1234-1234-123456789012",
      "operation_details": {
        "original_filename": "document.pdf",
        "mime_type": "application/pdf",
        "file_size": 245760
      },
      "status": "success",
      "duration": null,
      "timestamp": "2024-01-15T10:30:15"
    }
  ],
  "limit": 100,
  "offset": 0,
  "count": 1
}
```

### 2. Get File-Specific Audit Trail
```http
GET /audit/trail/{file_id}
```

**Response:**
```json
{
  "file_id": "12345678-1234-1234-1234-123456789012",
  "audit_trail": [
    {
      "operation_type": "file_upload",
      "operation_details": {...},
      "status": "success",
      "duration": null,
      "timestamp": "2024-01-15T10:30:15"
    },
    {
      "operation_type": "text_extraction_completed",
      "operation_details": {
        "extraction_method": "PDF (direct_extraction)",
        "character_count": 1250,
        "success": true
      },
      "status": "success",
      "duration": 2.1,
      "timestamp": "2024-01-15T10:30:18"
    }
  ],
  "total_operations": 7
}
```

### 3. Export Audit Logs
```http
GET /audit/export
```

Creates a JSON file with all audit logs and returns download information.

## Operation Types Tracked

| Operation Type | Description | Key Details Logged |
|---|---|---|
| `file_upload` | File uploaded to system | filename, size, type, hash |
| `text_extraction_started` | Text extraction begins | mime type |
| `text_extraction_completed` | Text extraction finishes | method, character count, duration |
| `pii_detection_started` | PII detection begins | text length, model |
| `pii_detection_completed` | PII detection finishes | findings count, duration |
| `file_saved` | File saved to disk | output path, file type |
| `pii_review_save` | PII review data saved | data size |
| `document_retrieval` | Document info accessed | operation type |
| `audit_logs_retrieval` | Audit logs accessed | filter parameters |
| `audit_export` | Audit logs exported | export path, record count |

## Status Values

- **`success`**: Operation completed successfully
- **`error`**: Operation failed with error
- **`warning`**: Operation completed with warnings

## Example Workflow Audit Trail

Here's what a complete audit trail looks like for a typical file processing workflow:

```json
{
  "file_id": "12345678-1234-1234-1234-123456789012",
  "audit_trail": [
    {
      "operation_type": "file_upload",
      "status": "success", 
      "timestamp": "2024-01-15 10:30:15",
      "operation_details": {
        "original_filename": "document.pdf",
        "mime_type": "application/pdf",
        "file_size": 245760,
        "file_hash": "sha256:abc123..."
      }
    },
    {
      "operation_type": "text_extraction_started",
      "status": "success",
      "timestamp": "2024-01-15 10:30:16", 
      "operation_details": {
        "mime_type": "application/pdf"
      }
    },
    {
      "operation_type": "text_extraction_completed",
      "status": "success",
      "timestamp": "2024-01-15 10:30:18",
      "duration": 2.1,
      "operation_details": {
        "extraction_method": "PDF (direct_extraction)",
        "character_count": 1250,
        "success": true
      }
    },
    {
      "operation_type": "pii_detection_started", 
      "status": "success",
      "timestamp": "2024-01-15 10:30:18",
      "operation_details": {
        "text_length": 1250,
        "model": "gemma3"
      }
    },
    {
      "operation_type": "pii_detection_completed",
      "status": "success", 
      "timestamp": "2024-01-15 10:30:22",
      "duration": 4.2,
      "operation_details": {
        "pii_instances_found": 3,
        "total_pii_found": 3,
        "high_confidence_count": 2,
        "model_used": "gemma3"
      }
    },
    {
      "operation_type": "file_saved",
      "status": "success",
      "timestamp": "2024-01-15 10:30:22", 
      "operation_details": {
        "output_path": "pii_results/pii_results_12345678-1234-1234-1234-123456789012.json",
        "file_type": "pii_results_json"
      }
    },
    {
      "operation_type": "pii_review_save",
      "status": "success",
      "timestamp": "2024-01-15 10:35:45",
      "operation_details": {
        "data_size": 2048
      }
    }
  ],
  "total_operations": 7
}
```

## Database Schema

The audit logs are stored in the `audit_logs` table:

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    file_id TEXT,
    operation_details TEXT,  -- JSON field for additional details
    status TEXT NOT NULL,    -- 'success', 'error', 'warning'
    duration REAL,          -- Operation duration in seconds
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (file_id) REFERENCES documents (file_id)
);
```

## Usage Examples

### 1. Monitor File Processing
```python
import requests

# Get audit trail for a specific file
file_id = "your-file-id-here"
response = requests.get(f"http://localhost:5000/audit/trail/{file_id}")
trail = response.json()

print(f"File {file_id} has {trail['total_operations']} operations:")
for op in trail['audit_trail']:
    print(f"- {op['operation_type']}: {op['status']} at {op['timestamp']}")
```

### 2. Check for Errors
```python
# Get recent audit logs and filter for errors
response = requests.get("http://localhost:5000/audit/logs?limit=100")
logs = response.json()

errors = [log for log in logs['audit_logs'] if log['status'] == 'error']
print(f"Found {len(errors)} errors in recent operations")
```

### 3. Export for Analysis
```python
# Export all audit logs
response = requests.get("http://localhost:5000/audit/export")
export_info = response.json()
print(f"Exported {export_info['records_exported']} records to {export_info['export_file']}")
```

## Benefits

### 🔍 **Transparency**
Every operation is logged with detailed information about what happened, when, and how long it took.

### 🐛 **Debugging** 
When something goes wrong, the audit trail shows exactly where the failure occurred and what the error was.

### 📊 **Analytics**
Export logs to analyze performance patterns, error rates, and usage statistics.

### 🔒 **Compliance**
Maintain a complete record of all document processing activities for regulatory requirements.

### 📈 **Performance Monitoring**
Track operation durations to identify bottlenecks and optimization opportunities.

## Testing

Run the included test script to verify audit logging functionality:

```bash
python test_audit_logs.py
```

This will:
1. Test all audit logging endpoints
2. Simulate a complete file processing workflow
3. Show the resulting audit trail
4. Demonstrate export functionality

## Integration

The audit logging system is automatically integrated into all existing endpoints. No changes are needed to your current workflow - just start using the audit endpoints to access the logs.

All operations are logged automatically in the background without affecting performance or requiring any authentication.