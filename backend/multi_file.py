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
import functools

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
DATABASE_PATH = 'document_storage.db'
SQLCIPHER_KEY = '121314'  # encryption key

# Create directories if they don't exist
for folder in [UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def require_access_key(f):
    """Decorator to require access key for read operations"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for access key in header or query parameter
        access_key = request.headers.get('X-Access-Key') or request.args.get('access_key')
        
        if not access_key or access_key != SQLCIPHER_KEY:
            return jsonify({
                'error': 'Access denied. Valid access key required for data retrieval.',
                'message': 'Provide access key via X-Access-Key header or access_key parameter'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

class DatabaseManager:
    def __init__(self, db_path, cipher_key):
        self.db_path = db_path
        self.cipher_key = cipher_key
        self.init_database()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with SQLCipher"""
        try:
            # Try to import pysqlcipher3 first
            import pysqlcipher3.dbapi2 as sqlite3_cipher
            
            conn = sqlite3_cipher.connect(self.db_path)
            # Set the encryption key
            conn.execute(f"PRAGMA key = '{self.cipher_key}'")
            conn.row_factory = sqlite3_cipher.Row  # Enable column access by name
            
            # Test if the database can be accessed with this key
            conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            
        except ImportError:
            # Fallback to regular SQLite if pysqlcipher3 is not available
            print("WARNING: pysqlcipher3 not found. Using regular SQLite without encryption.")
            print("Install with: pip install pysqlcipher3")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
        except Exception as db_error:
            # If database access fails, it might be due to wrong key or corrupted database
            raise Exception(f"Database access failed. Check encryption key or database integrity: {str(db_error)}")
        
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create documents table (same structure as original)
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
                    metadata TEXT  -- JSON field for additional metadata
                )
            ''')
            
            # Create extracted_text table (same structure as original)
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
            
            # Create encryption_keys table (for future PII detection keys)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS encryption_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT UNIQUE NOT NULL,
                    key_type TEXT NOT NULL,  -- 'pii_detection', 'file_encryption', etc.
                    encrypted_key TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    last_used DATETIME,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Create access_log table to track who accesses what
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    access_type TEXT NOT NULL,  -- 'upload', 'read', 'list'
                    file_id TEXT,
                    client_ip TEXT,
                    user_agent TEXT,
                    has_access_key BOOLEAN NOT NULL,
                    timestamp DATETIME NOT NULL,
                    success BOOLEAN NOT NULL
                )
            ''')
            
            # Create indexes for better performance (same as original)
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_id ON documents (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_timestamp ON documents (upload_timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_text_file_id ON extracted_text (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_log_timestamp ON access_log (timestamp)')
            
            conn.commit()
            print("Encrypted database initialized successfully")
    
    def log_access(self, access_type, file_id=None, client_ip=None, user_agent=None, has_access_key=False, success=True):
        """Log access attempts for audit purposes"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO access_log 
                    (access_type, file_id, client_ip, user_agent, has_access_key, timestamp, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (access_type, file_id, client_ip, user_agent, has_access_key, datetime.now(), success))
                conn.commit()
        except Exception as e:
            print(f"Failed to log access: {e}")
    
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
    
    def list_documents(self, limit=50, offset=0):
        """List all documents with pagination"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_id, original_filename, mime_type, file_size, 
                       upload_timestamp, extraction_method, status, character_count
                FROM documents 
                ORDER BY upload_timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return cursor.fetchall()
    
    def get_access_stats(self):
        """Get access statistics (requires access key)"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_accesses,
                    SUM(CASE WHEN has_access_key = 1 THEN 1 ELSE 0 END) as authorized_accesses,
                    SUM(CASE WHEN access_type = 'upload' THEN 1 ELSE 0 END) as uploads,
                    SUM(CASE WHEN access_type = 'read' THEN 1 ELSE 0 END) as reads,
                    COUNT(DISTINCT file_id) as unique_files_accessed
                FROM access_log
                WHERE timestamp >= datetime('now', '-30 days')
            ''')
            return cursor.fetchone()

# Initialize database
db_manager = DatabaseManager(DATABASE_PATH, SQLCIPHER_KEY)

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
    """Upload and extract text from files - RETURNS EXTRACTED TEXT (like original)"""
    file_id = None  # Initialize file_id for error handling
    file_path = None  # Initialize file_path for cleanup
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Generate unique file ID and filename
        file_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        stored_filename = f"{file_id}.{file_extension}" if file_extension else file_id
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
        
        # Log the upload attempt NOW that we have file_id
        db_manager.log_access(
            access_type='upload',
            file_id=file_id,  # Now we have the file_id
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=False,  # Upload doesn't require key
            success=True
        )
        
        # Save file
        file.save(file_path)
        
        # Get file information
        file_size = os.path.getsize(file_path)
        file_hash = calculate_file_hash(file_path)
        mime_type = detect_file_type(file_path)
        
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
        
        # Process and extract text based on file type
        extracted_text = None
        extraction_method = None
        extraction_confidence = None
        extraction_errors = None
        
        try:
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
                # Log the failure with file_id
                db_manager.log_access(
                    access_type='upload',
                    file_id=file_id,
                    client_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    has_access_key=False,
                    success=False
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
        
        # Log successful completion (optional - you can remove this if too verbose)
        db_manager.log_access(
            access_type='upload_complete',
            file_id=file_id,
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=False,
            success=extracted_text is not None
        )
        
        # Prepare response - RETURN THE EXTRACTED TEXT (same as original)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if extracted_text:
            return jsonify({
                'success': True,
                'file_id': file_id,
                'text': extracted_text,  # THIS IS THE KEY FIX - return the extracted text
                'filename': file.filename,
                'file_type': mime_type,
                'extraction_method': extraction_method,
                'timestamp': timestamp,
                'character_count': character_count,
                'file_size': file_size
            })
        else:
            return jsonify({
                'success': False,
                'file_id': file_id,
                'message': f'No text could be extracted from the {extraction_method.lower() if extraction_method else "file"}',
                'filename': file.filename,
                'file_type': mime_type,
                'extraction_method': extraction_method,
                'timestamp': timestamp,
                'errors': extraction_errors
            })
    
    except Exception as e:
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        # Log the failure with file_id if we have it
        db_manager.log_access(
            access_type='upload',
            file_id=file_id,  # This might be None if error occurred before file_id generation
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=False,
            success=False
        )
        
        return jsonify({'error': str(e)}), 500

@app.route('/document/<file_id>', methods=['GET'])
@require_access_key
def get_document(file_id):
    """Retrieve document information by file_id - REQUIRES ACCESS KEY"""
    try:
        # Log the read attempt
        db_manager.log_access(
            access_type='read',
            file_id=file_id,
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=True,
            success=True
        )
        
        doc = db_manager.get_document(file_id)
        if not doc:
            return jsonify({'error': 'Document not found'}), 404
        
        extracted_text = db_manager.get_extracted_text(file_id)
        
        response = {
            'file_id': doc['file_id'],
            'original_filename': doc['original_filename'],
            'mime_type': doc['mime_type'],
            'file_size': doc['file_size'],
            'upload_timestamp': doc['upload_timestamp'],
            'extraction_method': doc['extraction_method'],
            'character_count': doc['character_count'],
            'status': doc['status']
        }
        
        if extracted_text:
            response['extracted_text'] = extracted_text['extracted_text']
            response['extraction_timestamp'] = extracted_text['created_at']
        
        return jsonify(response)
    
    except Exception as e:
        db_manager.log_access(
            access_type='read',
            file_id=file_id,
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=True,
            success=False
        )
        return jsonify({'error': str(e)}), 500

@app.route('/documents', methods=['GET'])
@require_access_key
def list_documents():
    """List all documents with pagination - REQUIRES ACCESS KEY"""
    try:
        # Log the list attempt
        db_manager.log_access(
            access_type='list',
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=True,
            success=True
        )
        
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 items
        offset = int(request.args.get('offset', 0))
        
        documents = db_manager.list_documents(limit=limit, offset=offset)
        
        return jsonify({
            'documents': [dict(doc) for doc in documents],
            'limit': limit,
            'offset': offset,
            'count': len(documents)
        })
    
    except Exception as e:
        db_manager.log_access(
            access_type='list',
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            has_access_key=True,
            success=False
        )
        return jsonify({'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
@require_access_key
def get_stats():
    """Get access statistics - REQUIRES ACCESS KEY"""
    try:
        stats = db_manager.get_access_stats()
        return jsonify(dict(stats) if stats else {})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - NO ACCESS KEY REQUIRED"""
    try:
        # Test database connection
        with db_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM documents')
            doc_count = cursor.fetchone()[0]
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected (encrypted)',
            'documents_count': doc_count,
            'access_model': 'Upload returns text immediately, Read operations require access key',
            'supported_formats': {
                'images': ['JPEG', 'PNG', 'BMP', 'TIFF'],
                'documents': ['PDF (text + scanned)', 'TXT'],
                'spreadsheets': ['Excel (XLS, XLSX)', 'CSV']
            },
            'note': 'Upload endpoint returns extracted text immediately. Use X-Access-Key header for data retrieval endpoints.'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("✅ Fixed: file_id now properly logged in access_log table")
    app.run(debug=True, port=5000)