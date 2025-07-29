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
    from pii_detection import PIIDetector 
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

        print(f"Audit logs exported to {filepath}")
    
    def export_session_logs_to_json(self, file_id):
        """Export all audit logs for a given file_id to a JSON file"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM audit_logs WHERE file_id = ? ORDER BY timestamp ASC', (file_id,))
            logs = cursor.fetchall()

        audit_data = []
        for log in logs:
            log_dict = dict(log)
            if log_dict['details']:
                log_dict['details'] = json.loads(log_dict['details'])
            if log_dict['metadata']:
                log_dict['metadata'] = json.loads(log_dict['metadata'])
            audit_data.append(log_dict)

        export_data = {
            "file_id": file_id,
            "export_timestamp": datetime.now().isoformat(),
            "total_logs": len(audit_data),
            "logs": audit_data
        }
         # Use timestamp in filename
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_log_{file_id}_{timestamp_str}.json"
        filepath = os.path.join(AUDIT_LOGS_FOLDER, filename)
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

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def detect_file_type(file_path):
    """Detect the actual file type using python-magic"""
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except:
        # Fallback to extension-based detection
        extension = file_path.lower().split('.')[-1]
        mime_types = {
            'pdf': 'application/pdf',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel',
            'csv': 'text/csv',
            'txt': 'text/plain',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff'
        }
        return mime_types.get(extension, 'unknown')

def extract_text_from_image(image_path):
    """Extract text from image using OCR"""
    try:
        # Use OpenCV to preprocess image for better OCR
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply some preprocessing
        gray = cv2.medianBlur(gray, 3)

        # Use PIL for pytesseract
        pil_img = Image.fromarray(gray)
        text = pytesseract.image_to_string(pil_img, config='--psm 6')
        return text.strip()
    except Exception as e:
        print(f"Error in image OCR: {e}")
        return None

def extract_text_from_pdf(file_path):
    """Extract text from PDF, with OCR fallback for scanned PDFs"""
    try:
        text = ""

        # First, try to extract text directly (for text-based PDFs)
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += f"--- Page {page_num + 1} ---\n"
                    text += page_text + "\n\n"

        # If we got substantial text, return it
        if len(text.strip()) > 50:  # Threshold for "substantial" text
            return text.strip(), "direct_extraction"

        # If no text or very little text, treat as scanned PDF and use OCR
        print("PDF appears to be scanned, using OCR...")
        return extract_text_from_scanned_pdf(file_path), "ocr_extraction"

    except Exception as e:
        print(f"Error in PDF processing: {e}")
        return None, "error"

def extract_text_from_scanned_pdf(file_path):
    """Extract text from scanned PDF using OCR"""
    try:
        import pdf2image
        
        # Convert PDF pages to images
        pages = pdf2image.convert_from_path(file_path)
        
        all_text = ""
        for page_num, page_image in enumerate(pages):
            # Convert PIL image to numpy array for OpenCV
            open_cv_image = np.array(page_image)
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
            
            # Preprocess for better OCR
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 3)

            # Extract text using OCR
            pil_img = Image.fromarray(gray)
            page_text = pytesseract.image_to_string(pil_img, config='--psm 6')

            if page_text.strip():
                all_text += f"--- Page {page_num + 1} ---\n"
                all_text += page_text + "\n\n"

        return all_text.strip()

    except ImportError:
        return "Error: pdf2image package required for scanned PDF processing. Install with: pip install pdf2image"
    except Exception as e:
        print(f"Error in scanned PDF OCR: {e}")
        return None

def extract_text_from_excel(file_path):
    """Extract text from Excel files"""
    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        all_text = ""

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            all_text += f"--- Sheet: {sheet_name} ---\n"
            all_text += df.to_string(index=False) + "\n\n"

        return all_text.strip()
    except Exception as e:
        print(f"Error in Excel processing: {e}")
        return None

def extract_text_from_csv(file_path):
    """Extract text from CSV files"""
    try:
        df = pd.read_csv(file_path)
        return df.to_string(index=False)
    except Exception as e:
        print(f"Error in CSV processing: {e}")
        return None

def extract_text_from_txt(file_path):
    """Extract text from plain text files"""
    try:
        # Try different encodings to handle various text files
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                    # If we successfully read the file, return the text
                    return text.strip()
            except UnicodeDecodeError:
                continue

        # If all encodings fail, try binary mode and decode with error handling
        with open(file_path, 'rb') as f:
            raw_content = f.read()
            text = raw_content.decode('utf-8', errors='ignore')
            return text.strip()

    except Exception as e:
        print(f"Error reading text file: {e}")
        return None

@app.route('/extract', methods=['POST'])
def extract_text():
    file_id = None
    file_path = None

    try:
        if 'file' not in request.files:
            audit_logger.log_activity(
                "file_upload_failed",
                details={"error": "No file provided"},
                status="error",
                metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
            )
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            audit_logger.log_activity(
                "file_upload_failed",
                details={"error": "No file selected"},
                status="error",
                metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
            )
            return jsonify({'error': 'No file selected'}), 400

        # Generate unique file ID and filename
        file_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        stored_filename = f"{file_id}.{file_extension}" if file_extension else file_id
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)

        # Log file upload started
        audit_logger.log_activity(
            "file_upload_started",
            file_id=file_id,
            details={
                "original_filename": file.filename,
                "file_extension": file_extension,
                "stored_filename": stored_filename
            },
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )

        # Save file
        file.save(file_path)
        
        # Get file information
        file_size = os.path.getsize(file_path)
        file_hash = calculate_file_hash(file_path)
        mime_type = detect_file_type(file_path)
        
        # Log file saved successfully
        audit_logger.log_activity(
            "file_saved",
            file_id=file_id,
            details={
                "file_size": file_size,
                "file_hash": file_hash,
                "mime_type": mime_type,
                "file_path": file_path
            }
        )
        
        # Store document in database
        metadata = {
            'user_agent': request.headers.get('User-Agent'),
            'upload_ip': request.remote_addr
        }
        
        doc_id = db_manager.store_document(
            file_id=file_id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_path=file_path,
            mime_type=mime_type,
            file_size=file_size,
            file_hash=file_hash,
            metadata=metadata
        )
        
        # Log document stored in database
        audit_logger.log_activity(
            "document_stored",
            file_id=file_id,
            details={
                "doc_id": doc_id,
                "original_filename": file.filename,
                "mime_type": mime_type,
                "file_size": file_size
            }
        )
        
        # Process and extract text based on file type
        extracted_text = None
        extraction_method = None
        extraction_confidence = None
        extraction_errors = None
        
        try:
            # Log text extraction started
            audit_logger.log_activity(
                "text_extraction_started",
                file_id=file_id,
                details={"mime_type": mime_type}
            )
            
            if mime_type.startswith('image/'):
                extracted_text = extract_text_from_image(file_path)
                extraction_method = "OCR (Image)"
                
            elif mime_type == 'application/pdf':
                extracted_text, method = extract_text_from_pdf(file_path)
                extraction_method = f"PDF ({method})"
                
            elif mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                              'application/vnd.ms-excel']:
                extracted_text = extract_text_from_excel(file_path)
                extraction_method = "Excel Parser"
                
            elif mime_type == 'text/csv':
                extracted_text = extract_text_from_csv(file_path)
                extraction_method = "CSV Parser"
                
            elif mime_type == 'text/plain':
                extracted_text = extract_text_from_txt(file_path)
                extraction_method = "Text File Parser"
                
            else:
                # Log unsupported file type
                audit_logger.log_activity(
                    "text_extraction_failed",
                    file_id=file_id,
                    details={"error": f"Unsupported file type: {mime_type}"},
                    status="error"
                )
                # Clean up and return error
                os.remove(file_path)
                return jsonify({
                    'error': f'Unsupported file type: {mime_type}',
                    'supported_types': [
                        'Images (JPEG, PNG, BMP, TIFF)',
                        'PDF (text-based and scanned)',
                        'Excel (XLS, XLSX)',
                        'CSV',
                        'Text files (TXT)'
                    ]
                }), 400
        
        except Exception as extraction_error:
            extraction_errors = str(extraction_error)
            audit_logger.log_activity(
                "text_extraction_error",
                file_id=file_id,
                status="error",
                error_message=str(extraction_error),
                details={"extraction_method": extraction_method}
            )
            print(f"Extraction error: {extraction_error}")
        
        # Store extracted text in database
        character_count = len(extracted_text) if extracted_text else 0
        if extracted_text or extraction_errors:
            db_manager.store_extracted_text(
                file_id=file_id,
                extracted_text=extracted_text,
                extraction_method=extraction_method,
                character_count=character_count,
                extraction_confidence=extraction_confidence,
                extraction_errors=extraction_errors
            )
            
            # Log text extraction completed
            if extracted_text:
                audit_logger.log_activity(
                    "text_extraction_completed",
                    file_id=file_id,
                    details={
                        "character_count": character_count,
                        "extraction_method": extraction_method
                    }
                )
            else:
                audit_logger.log_activity(
                    "text_extraction_failed",
                    file_id=file_id,
                    details={"extraction_errors": extraction_errors},
                    status="warning"
                )
        
        # *** TRIGGER PII DETECTION AFTER SUCCESSFUL EXTRACTION ***
        if extracted_text and character_count > 0:
            # Start PII detection in a separate thread to avoid blocking the response
            pii_thread = threading.Thread(
                target=process_pii_detection, 
                args=(file_id, extracted_text)
            )
            pii_thread.daemon = True
            pii_thread.start()
            print(f"PII detection started in background for file {file_id}")
        
        # Prepare response
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if extracted_text:
            response_data = {
                'success': True,
                'file_id': file_id,
                'text': extracted_text,
                'filename': file.filename,
                'file_type': mime_type,
                'extraction_method': extraction_method,
                'timestamp': timestamp,
                'character_count': character_count,
                'file_size': file_size,
                'pii_detection_status': 'started' if PII_DETECTION_AVAILABLE and character_count > 0 else 'unavailable'
            }
            
            # Log successful response
            audit_logger.log_activity(
                "extract_text_success",
                file_id=file_id,
                details={
                    "character_count": character_count,
                    "pii_detection_started": PII_DETECTION_AVAILABLE and character_count > 0
                }
            )
            
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'file_id': file_id,
                'message': f'No text could be extracted from the {extraction_method.lower() if extraction_method else "file"}',
                'filename': file.filename,
                'file_type': mime_type,
                'extraction_method': extraction_method,
                'timestamp': timestamp,
                'errors': extraction_errors,
                'pii_detection_status': 'not_applicable'
            })
    
    except Exception as e:
        # Log critical error
        audit_logger.log_activity(
            "extract_text_critical_error",
            file_id=file_id,
            status="error",
            error_message=str(e),
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': str(e)}), 500

@app.route("/api/pii/save", methods=["POST"])
def save_pii_results():
    try:
        data = request.get_json()
        file_id = data.get("file_id")
        reviewed_data = json.dumps(data)

        # Log PII save started
        audit_logger.log_activity(
            "pii_review_save_started",
            file_id=file_id,
            details={
                "data_keys": list(data.keys()) if data else None,
                "reviewed_data_size": len(reviewed_data)
            },
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reviewed (file_id, reviewed_data)
            VALUES (?, ?)
        """, (file_id, reviewed_data))

        conn.commit()
        conn.close()

        # Log successful save
        audit_logger.log_activity(
            "pii_review_saved",
            file_id=file_id,
            details={"reviewed_data_size": len(reviewed_data)}
        )

        audit_logger.export_session_logs_to_json(file_id)
        return jsonify({"message": "PII review data saved successfully"}), 200

    except Exception as e:
        # Log error
        audit_logger.log_activity(
            "pii_review_save_error",
            file_id=file_id if 'file_id' in locals() else None,
            status="error",
            error_message=str(e),
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        return jsonify({"error": str(e)}), 500

# New audit log endpoints
@app.route('/audit/logs', methods=['GET'])
def get_audit_logs():
    """Get audit logs with optional filtering"""
    try:
        limit = min(int(request.args.get('limit', 100)), 500)  # Max 500 items
        offset = int(request.args.get('offset', 0))
        file_id = request.args.get('file_id')
        activity_type = request.args.get('activity_type')
        
        logs = audit_logger.get_audit_logs(
            limit=limit, 
            offset=offset, 
            file_id=file_id, 
            activity_type=activity_type
        )
        
        # Convert logs to list of dictionaries and parse JSON fields
        audit_data = []
        for log in logs:
            log_dict = dict(log)
            # Parse JSON fields
            if log_dict['details']:
                log_dict['details'] = json.loads(log_dict['details'])
            if log_dict['metadata']:
                log_dict['metadata'] = json.loads(log_dict['metadata'])
            audit_data.append(log_dict)
        
        return jsonify({
            'logs': audit_data,
            'limit': limit,
            'offset': offset,
            'count': len(audit_data),
            'filters': {
                'file_id': file_id,
                'activity_type': activity_type
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audit/export', methods=['POST'])
def export_audit_logs():
    """Export audit logs to JSON file"""
    try:
        data = request.get_json() or {}
        filename = data.get('filename')  # Optional custom filename
        
        # Export logs to file
        filepath = audit_logger.export_audit_logs_to_json(filename)
        
        # Log the export activity
        audit_logger.log_activity(
            "audit_logs_exported",
            details={
                "export_filepath": filepath,
                "requested_filename": filename,
                "file_size": os.path.getsize(filepath)
            },
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        
        return jsonify({
            "message": "Audit logs exported successfully",
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "file_size": os.path.getsize(filepath)
        }), 200
    
    except Exception as e:
        audit_logger.log_activity(
            "audit_logs_export_error",
            status="error",
            error_message=str(e),
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        return jsonify({"error": str(e)}), 500

@app.route('/audit/summary', methods=['GET'])
def get_audit_summary():
    """Get audit log summary statistics"""
    try:
        with audit_logger.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM audit_logs')
            total_logs = cursor.fetchone()[0]
            
            # Get count by status
            cursor.execute('SELECT status, COUNT(*) FROM audit_logs GROUP BY status')
            status_counts = dict(cursor.fetchall())
            
            # Get count by activity type
            cursor.execute('SELECT activity_type, COUNT(*) FROM audit_logs GROUP BY activity_type ORDER BY COUNT(*) DESC LIMIT 10')
            activity_counts = dict(cursor.fetchall())
            
            # Get recent activity (last 24 hours)
            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE datetime(timestamp) > datetime('now', '-1 day')")
            recent_activity = cursor.fetchone()[0]
            
            # Get date range
            cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM audit_logs')
            date_range = cursor.fetchone()
        
        return jsonify({
            'total_logs': total_logs,
            'status_breakdown': status_counts,
            'top_activities': activity_counts,
            'recent_activity_24h': recent_activity,
            'date_range': {
                'earliest': date_range[0],
                'latest': date_range[1]
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Enhanced existing endpoints with audit logging
@app.route('/document/<file_id>', methods=['GET'])
def get_document(file_id):
    """Retrieve document information by file_id"""
    try:
        # Log document access
        audit_logger.log_activity(
            "document_accessed",
            file_id=file_id,
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        
        doc = db_manager.get_document(file_id)
        if not doc:
            audit_logger.log_activity(
                "document_not_found",
                file_id=file_id,
                status="warning",
                metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
            )
            return jsonify({'error': 'Document not found'}), 404
        
        extracted_text = db_manager.get_extracted_text(file_id)
        pii_results = db_manager.get_pii_results(file_id)
        
        response = {
            'file_id': doc['file_id'],
            'original_filename': doc['original_filename'],
            'mime_type': doc['mime_type'],
            'file_size': doc['file_size'],
            'upload_timestamp': doc['upload_timestamp'],
            'extraction_method': doc['extraction_method'],
            'character_count': doc['character_count'],
            'status': doc['status'],
            'pii_processed': bool(doc['pii_processed']),
            'pii_processing_timestamp': doc['pii_processing_timestamp']
        }
        
        if extracted_text:
            response['extracted_text'] = extracted_text['extracted_text']
            response['extraction_timestamp'] = extracted_text['created_at']
        
        if pii_results:
            response['pii_summary'] = json.loads(pii_results['pii_summary'])
            response['pii_processing_duration'] = pii_results['processing_duration']
            response['pii_model_used'] = pii_results['model_used']
        
        return jsonify(response)
    
    except Exception as e:
        audit_logger.log_activity(
            "document_access_error",
            file_id=file_id,
            status="error",
            error_message=str(e),
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        return jsonify({'error': str(e)}), 500

@app.route('/document/<file_id>/pii', methods=['GET'])
def get_pii_results(file_id):
    """Get detailed PII results for a specific document"""
    try:
        # Log PII results access
        audit_logger.log_activity(
            "pii_results_accessed",
            file_id=file_id,
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        
        pii_results = db_manager.get_pii_results(file_id)
        if not pii_results:
            return jsonify({'error': 'PII results not found for this document'}), 404
        
        response = {
            'file_id': file_id,
            'pii_summary': json.loads(pii_results['pii_summary']),
            'pii_matches': json.loads(pii_results['pii_matches']),
            'processing_timestamp': pii_results['processing_timestamp'],
            'processing_duration': pii_results['processing_duration'],
            'model_used': pii_results['model_used']
        }
        
        audit_logger.export_session_logs_to_json(file_id)
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    """List all documents with pagination"""
    try:
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 items
        offset = int(request.args.get('offset', 0))
        
        documents = db_manager.list_documents(limit=limit, offset=offset)
        
        # Log documents list access
        audit_logger.log_activity(
            "documents_list_accessed",
            details={"limit": limit, "offset": offset, "count": len(documents)},
            metadata={"user_agent": request.headers.get('User-Agent'), "ip": request.remote_addr}
        )
        
        return jsonify({
            'documents': [dict(doc) for doc in documents],
            'limit': limit,
            'offset': offset,
            'count': len(documents)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with db_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM documents')
            doc_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM pii_results')
            pii_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM audit_logs')
            audit_count = cursor.fetchone()[0]
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'documents_count': doc_count,
            'pii_results_count': pii_count,
            'audit_logs_count': audit_count,
            'pii_detection_available': PII_DETECTION_AVAILABLE,
            'supported_formats': {
                'images': ['JPEG', 'PNG', 'BMP', 'TIFF'],
                'documents': ['PDF (text + scanned)', 'TXT'],
                'spreadsheets': ['Excel (XLS, XLSX)', 'CSV']
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Flask application with audit logging...")
    print(f"Audit logs will be stored in: {AUDIT_LOGS_FOLDER}")
    print("Available audit endpoints:")
    print("  GET /audit/logs - View audit logs with filtering")
    print("  POST /audit/export - Export audit logs to JSON")
    print("  GET /audit/summary - Get audit statistics")
    print("Using database at:", DATABASE_PATH)
    app.run(debug=True, host='0.0.0.0', port=5000)