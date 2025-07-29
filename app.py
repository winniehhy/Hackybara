from flask import Flask, request, jsonify
from flask_cors import CORS
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pdfplumber
import pandas as pd
import openpyxl
import os
import uuid
from datetime import datetime
import io
import magic
import sqlite3
import hashlib
import json
from contextlib import contextmanager
import threading
import time

# Import PII detection from the separate file
try:
    from pii_detection import PIIDetector  # Assuming your PII file is named pii_detection.py
    PII_DETECTION_AVAILABLE = True
    print("PII Detection module loaded successfully")
except ImportError as e:
    print(f"PII Detection module not available: {e}")
    PII_DETECTION_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
DATABASE_PATH = 'document_storage.db'
AUDIT_LOGS_FOLDER = 'audit_logs'

# Create directories if they don't exist
for folder in [UPLOAD_FOLDER, AUDIT_LOGS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

class AuditLogger:
    def __init__(self, db_path):
        self.db_path = db_path
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def log_activity(self, activity_type, file_id=None, details=None, status="success", error_message=None, metadata=None):
        """Log an activity to the audit log"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs 
                (activity_type, file_id, details, status, error_message, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                activity_type,
                file_id,
                json.dumps(details) if details else None,
                status,
                error_message,
                json.dumps(metadata) if metadata else None,
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_audit_logs(self, limit=100, offset=0, file_id=None, activity_type=None):
        """Retrieve audit logs with optional filtering"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM audit_logs WHERE 1=1'
            params = []
            
            if file_id:
                query += ' AND file_id = ?'
                params.append(file_id)
            
            if activity_type:
                query += ' AND activity_type = ?'
                params.append(activity_type)
            
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def export_audit_logs_to_json(self, filename=None):
        """Export all audit logs to a JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_log_export_{timestamp}.json"
        
        filepath = os.path.join(AUDIT_LOGS_FOLDER, filename)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM audit_logs ORDER BY timestamp DESC')
            logs = cursor.fetchall()
        
        # Convert to list of dictionaries
        audit_data = []
        for log in logs:
            log_dict = dict(log)
            # Parse JSON fields
            if log_dict['details']:
                log_dict['details'] = json.loads(log_dict['details'])
            if log_dict['metadata']:
                log_dict['metadata'] = json.loads(log_dict['metadata'])
            audit_data.append(log_dict)
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_logs": len(audit_data),
            "logs": audit_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return filepath

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create documents table (with PII fields added)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    upload_timestamp DATETIME NOT NULL,
                    extraction_method TEXT,
                    extraction_timestamp DATETIME,
                    character_count INTEGER,
                    status TEXT DEFAULT 'uploaded',
                    metadata TEXT,
                    pii_processed BOOLEAN DEFAULT 0,
                    pii_processing_timestamp DATETIME
                )
            ''')
            
            # Create extracted_text table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS extracted_text (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    extracted_text TEXT,
                    extraction_confidence REAL,
                    extraction_errors TEXT,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES documents (file_id)
                )
            ''')
            
            # Create PII results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pii_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    pii_summary TEXT,  -- JSON field containing PII summary
                    pii_matches TEXT,  -- JSON field containing all matches
                    total_pii_found INTEGER DEFAULT 0,
                    high_confidence_count INTEGER DEFAULT 0,
                    processing_timestamp DATETIME NOT NULL,
                    processing_duration REAL,  -- Processing time in seconds
                    model_used TEXT DEFAULT 'gemma3',
                    FOREIGN KEY (file_id) REFERENCES documents (file_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviewed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    reviewed_data TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create audit logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    file_id TEXT,
                    details TEXT,  -- JSON field with activity details
                    status TEXT NOT NULL DEFAULT 'success',  -- success, error, warning
                    error_message TEXT,
                    metadata TEXT,  -- JSON field for additional metadata
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES documents (file_id)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_id ON documents (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_timestamp ON documents (upload_timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_text_file_id ON extracted_text (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pii_results_file_id ON pii_results (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_file_id ON audit_logs (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_activity_type ON audit_logs (activity_type)')
            
            conn.commit()
            print("Database initialized successfully")
    
    def store_document(self, file_id, original_filename, stored_filename, file_path, 
                      mime_type, file_size, file_hash, metadata=None):
        """Store document information in the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents 
                (file_id, original_filename, stored_filename, file_path, mime_type, 
                 file_size, file_hash, upload_timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, original_filename, stored_filename, file_path, mime_type,
                  file_size, file_hash, datetime.now(), json.dumps(metadata or {})))
            conn.commit()
            return cursor.lastrowid
    
    def store_extracted_text(self, file_id, extracted_text, extraction_method, 
                           character_count, extraction_confidence=None, extraction_errors=None):
        """Store extracted text and update document status"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert extracted text
            cursor.execute('''
                INSERT INTO extracted_text 
                (file_id, extracted_text, extraction_confidence, extraction_errors, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_id, extracted_text, extraction_confidence, extraction_errors, datetime.now()))
            
            # Update document with extraction info
            cursor.execute('''
                UPDATE documents 
                SET extraction_method = ?, extraction_timestamp = ?, 
                    character_count = ?, status = ?
                WHERE file_id = ?
            ''', (extraction_method, datetime.now(), character_count, 'processed', file_id))
            
            conn.commit()
    
    def store_pii_results(self, file_id, pii_summary, pii_matches, processing_duration, model_used="gemma3"):
        """Store PII detection results"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO pii_results 
                (file_id, pii_summary, pii_matches, total_pii_found, high_confidence_count, 
                 processing_timestamp, processing_duration, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id,
                json.dumps(pii_summary),
                json.dumps(pii_matches),
                pii_summary.get('total_pii_found', 0),
                pii_summary.get('high_confidence_count', 0),
                datetime.now(),
                processing_duration,
                model_used
            ))
            
            # Update document to mark PII as processed
            cursor.execute('''
                UPDATE documents 
                SET pii_processed = 1, pii_processing_timestamp = ?
                WHERE file_id = ?
            ''', (datetime.now(), file_id))
            
            conn.commit()
    
    def get_document(self, file_id):
        """Retrieve document information by file_id"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents WHERE file_id = ?', (file_id,))
            return cursor.fetchone()
    
    def get_extracted_text(self, file_id):
        """Retrieve extracted text by file_id"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM extracted_text WHERE file_id = ? ORDER BY created_at DESC LIMIT 1', (file_id,))
            return cursor.fetchone()
    
    def get_pii_results(self, file_id):
        """Retrieve PII results by file_id"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM pii_results WHERE file_id = ? ORDER BY processing_timestamp DESC LIMIT 1', (file_id,))
            return cursor.fetchone()
    
    def list_documents(self, limit=50, offset=0):
        """List all documents with pagination"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_id, original_filename, mime_type, file_size, 
                       upload_timestamp, extraction_method, status, character_count,
                       pii_processed, pii_processing_timestamp
                FROM documents 
                ORDER BY upload_timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return cursor.fetchall()

# Initialize database and audit logger
db_manager = DatabaseManager(DATABASE_PATH)
audit_logger = AuditLogger(DATABASE_PATH)

def process_pii_detection(file_id, extracted_text):
    """
    Process PII detection in a separate thread after text extraction
    """
    if not PII_DETECTION_AVAILABLE:
        audit_logger.log_activity(
            "pii_detection_unavailable",
            file_id=file_id,
            details={"reason": "PII detection module not available"},
            status="warning"
        )
        print(f"PII Detection not available for file {file_id}")
        return
    
    try:
        print(f"Starting PII detection for file {file_id}")
        audit_logger.log_activity(
            "pii_detection_started",
            file_id=file_id,
            details={"text_length": len(extracted_text)}
        )
        
        start_time = time.time()
        
        # Initialize PII detector
        detector = PIIDetector(model="gemma3")
        
        # Detect PII
        matches = detector.detect_pii(extracted_text, use_llm=True, debug=False)
        
        # Get summary
        summary = detector.get_pii_summary(matches)
        
        # Convert matches to serializable format
        pii_matches = [{
            "text": match.text,
            "type": match.pii_type.value,
            "start_pos": match.start_pos,
            "end_pos": match.end_pos,
            "confidence": match.confidence
        } for match in matches]
        
        processing_duration = time.time() - start_time
        
        # Store results in database
        db_manager.store_pii_results(file_id, summary, pii_matches, processing_duration)
        
        # Log successful PII detection
        audit_logger.log_activity(
            "pii_detection_completed",
            file_id=file_id,
            details={
                "pii_found": len(matches),
                "processing_duration": processing_duration,
                "model_used": "gemma3",
                "high_confidence_count": summary.get('high_confidence_count', 0)
            }
        )
        
        print(f"PII detection completed for file {file_id}. Found {len(matches)} PII instances in {processing_duration:.2f}s")
        
        # Save detailed results to JSON file (optional)
        output_dir = "pii_results"
        os.makedirs(output_dir, exist_ok=True)
        
        output_data = {
            "file_id": file_id,
            "processing_timestamp": datetime.now().isoformat(),
            "processing_duration": processing_duration,
            "pii_summary": summary,
            "matches": pii_matches,
            "original_text_length": len(extracted_text),
            "matches": [{
            "text": match.text,
            "type": match.pii_type.value,
            "start_pos": match.start_pos,
            "end_pos": match.end_pos,
            "confidence": match.confidence
        } for match in matches],
        "original_text": extracted_text
        }
        
        output_filename = f"pii_results_{file_id}.json"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # Log file save
        audit_logger.log_activity(
            "pii_results_file_saved",
            file_id=file_id,
            details={"output_path": output_path, "file_size": os.path.getsize(output_path)}
        )
        
        print(f"PII results saved to: {output_path}")
        
    except Exception as e:
        audit_logger.log_activity(
            "pii_detection_error",
            file_id=file_id,
            status="error",
            error_message=str(e),
            details={"processing_duration": time.time() - start_time if 'start_time' in locals() else None}
        )
        print(f"Error in PII detection for file {file_id}: {e}")