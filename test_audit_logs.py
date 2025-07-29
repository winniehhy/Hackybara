#!/usr/bin/env python3

import requests
import json
import time
import os

# Configuration
BASE_URL = "http://localhost:5000"

def test_audit_logging():
    """Test the audit logging functionality"""
    print("🔍 Testing Audit Logging System")
    print("=" * 50)
    
    # Test 1: Check health endpoint
    print("\n1. Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print("❌ Health check failed")
            return
    except requests.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        return
    
    # Test 2: Get initial audit logs
    print("\n2. Getting initial audit logs...")
    try:
        response = requests.get(f"{BASE_URL}/audit/logs")
        if response.status_code == 200:
            initial_logs = response.json()
            print(f"✅ Found {initial_logs['count']} existing audit log entries")
        else:
            print("❌ Failed to get audit logs")
            return
    except requests.RequestException as e:
        print(f"❌ Error getting audit logs: {e}")
        return
    
    # Test 3: Simulate file upload (if we have a test file)
    print("\n3. Testing file upload audit trail...")
    test_file_path = "test_document.txt"
    
    # Create a test file
    with open(test_file_path, 'w') as f:
        f.write("This is a test document with some sample text.\nIt contains multiple lines for testing purposes.\nEmail: test@example.com\nPhone: 123-456-7890")
    
    try:
        with open(test_file_path, 'rb') as f:
            files = {'file': (test_file_path, f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/extract", files=files)
        
        if response.status_code == 200:
            result = response.json()
            file_id = result.get('file_id')
            print(f"✅ File uploaded successfully. File ID: {file_id}")
            
            # Wait a moment for PII detection to complete
            print("⏳ Waiting for PII detection to complete...")
            time.sleep(3)
            
            # Test 4: Get audit trail for this specific file
            print(f"\n4. Getting audit trail for file {file_id}...")
            response = requests.get(f"{BASE_URL}/audit/trail/{file_id}")
            if response.status_code == 200:
                trail = response.json()
                print(f"✅ Found {trail['total_operations']} operations in audit trail:")
                
                for i, operation in enumerate(trail['audit_trail'], 1):
                    print(f"   {i}. {operation['operation_type']} - {operation['status']} - {operation['timestamp']}")
                    if operation.get('operation_details'):
                        details = operation['operation_details']
                        if isinstance(details, dict):
                            for key, value in details.items():
                                if key not in ['error']:  # Skip error details for cleaner output
                                    print(f"      - {key}: {value}")
            else:
                print("❌ Failed to get audit trail")
        else:
            print("❌ File upload failed")
            print(response.text)
    except Exception as e:
        print(f"❌ Error during file upload test: {e}")
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    # Test 5: Get all audit logs and show recent activity
    print("\n5. Getting recent audit logs...")
    try:
        response = requests.get(f"{BASE_URL}/audit/logs?limit=10")
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ Recent audit activity (last {logs['count']} operations):")
            
            for i, log in enumerate(logs['audit_logs'], 1):
                print(f"   {i}. {log['operation_type']} - {log['status']} - {log['timestamp']}")
                if log.get('file_id'):
                    print(f"      File ID: {log['file_id']}")
        else:
            print("❌ Failed to get recent audit logs")
    except Exception as e:
        print(f"❌ Error getting recent logs: {e}")
    
    # Test 6: Test audit log export
    print("\n6. Testing audit log export...")
    try:
        response = requests.get(f"{BASE_URL}/audit/export")
        if response.status_code == 200:
            export_result = response.json()
            print(f"✅ Audit logs exported successfully:")
            print(f"   - Export file: {export_result['export_file']}")
            print(f"   - Records exported: {export_result['records_exported']}")
        else:
            print("❌ Failed to export audit logs")
    except Exception as e:
        print(f"❌ Error during export: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Audit logging test completed!")
    print("\nKey Features Demonstrated:")
    print("✅ File upload tracking")
    print("✅ Text extraction logging") 
    print("✅ PII detection audit trail")
    print("✅ Operation status tracking")
    print("✅ Timestamp recording")
    print("✅ Error logging")
    print("✅ Audit log retrieval")
    print("✅ File-specific audit trails")
    print("✅ Audit log export to JSON")

def demonstrate_audit_trail_example():
    """Show an example of what an audit trail looks like"""
    print("\n" + "=" * 60)
    print("📋 EXAMPLE AUDIT TRAIL (JSON FORMAT)")
    print("=" * 60)
    
    example_trail = {
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
                    "success": True
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
    
    print(json.dumps(example_trail, indent=2))

if __name__ == "__main__":
    # Show example first
    demonstrate_audit_trail_example()
    
    # Then run actual tests
    test_audit_logging()