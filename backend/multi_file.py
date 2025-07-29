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

# Create directories if they don't exist
for folder in [UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

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
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_id ON documents (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_timestamp ON documents (upload_timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_text_file_id ON extracted_text (file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pii_results_file_id ON pii_results (file_id)')
            
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

# Initialize database
db_manager = DatabaseManager(DATABASE_PATH)

def process_pii_detection(file_id, extracted_text):
    """
    Process PII detection in a separate thread after text extraction
    Enhanced version with detailed messaging about detection methods
    """
    if not PII_DETECTION_AVAILABLE:
        print(f"PII Detection not available for file {file_id}")
        return
    
    try:
        print(f"\n{'='*60}")
        print(f"STARTING PII DETECTION FOR FILE: {file_id}")
        print(f"{'='*60}")
        print(f"Text length: {len(extracted_text):,} characters")
        print(f"Sample text (first 200 chars): {repr(extracted_text[:200])}")
        
        start_time = time.time()
        
        # Initialize PII detector (using original unchanged code)
        detector = PIIDetector(model="gemma3")
        
        # STEP 1: Run regex detection first to see what it finds
        print(f"\n{'='*40}")
        print("STEP 1: REGEX PATTERN DETECTION")
        print(f"{'='*40}")
        print("Checking for patterns: EMAIL, PHONE, IC, CREDIT_CARD, IP_ADDRESS, PASSPORT")
        
        regex_matches = detector._regex_detect(extracted_text)
        
        if regex_matches:
            print(f"✅ REGEX DETECTED {len(regex_matches)} matches:")
            regex_by_type = {}
            for match in regex_matches:
                pii_type = match.pii_type.value
                if pii_type not in regex_by_type:
                    regex_by_type[pii_type] = []
                regex_by_type[pii_type].append(match)
            
            for pii_type, matches in regex_by_type.items():
                print(f"  📋 {pii_type.upper()}: {len(matches)} found")
                for match in matches[:3]:  # Show first 3 examples
                    print(f"    - '{match.text}' (confidence: {match.confidence:.2f})")
                if len(matches) > 3:
                    print(f"    ... and {len(matches) - 3} more")
        else:
            print("❌ No regex patterns detected")
        
        # STEP 2: Run LLM detection to find what regex missed
        print(f"\n{'='*40}")
        print("STEP 2: LLM DETECTION")
        print(f"{'='*40}")
        print("LLM will look for: NAMES, ADDRESSES, RELIGION, ETHNICITY, DATE_OF_BIRTH, etc.")
        print("(Plus verify regex findings)")
        
        # Use the original detect_pii method unchanged
        all_matches = detector.detect_pii(extracted_text, use_llm=True, debug=False)
        
        # Separate LLM-only matches from regex matches
        llm_only_matches = []
        regex_types = {'email', 'phone', 'ic', 'credit_card', 'ip_address', 'passport'}
        
        for match in all_matches:
            if match.pii_type.value not in regex_types:
                llm_only_matches.append(match)
        
        if llm_only_matches:
            print(f"✅ LLM DETECTED {len(llm_only_matches)} additional matches:")
            llm_by_type = {}
            for match in llm_only_matches:
                pii_type = match.pii_type.value
                if pii_type not in llm_by_type:
                    llm_by_type[pii_type] = []
                llm_by_type[pii_type].append(match)
            
            for pii_type, matches in llm_by_type.items():
                print(f"  🤖 {pii_type.upper()}: {len(matches)} found")
                for match in matches[:3]:  # Show first 3 examples
                    print(f"    - '{match.text}' (confidence: {match.confidence:.2f})")
                if len(matches) > 3:
                    print(f"    ... and {len(matches) - 3} more")
        else:
            print("❌ LLM found no additional PII beyond regex patterns")
        
        # STEP 3: Summary of combined results
        print(f"\n{'='*40}")
        print("STEP 3: COMBINED RESULTS SUMMARY")
        print(f"{'='*40}")
        
        # Get summary using original method
        summary = detector.get_pii_summary(all_matches)
        
        print(f"📊 TOTAL PII INSTANCES FOUND: {len(all_matches)}")
        print(f"📊 HIGH CONFIDENCE MATCHES: {summary['high_confidence_count']}")
        
        print(f"\n📋 BREAKDOWN BY DETECTION METHOD:")
        print(f"  🔍 Regex detected: {len(regex_matches)} instances")
        print(f"  🤖 LLM detected: {len(llm_only_matches)} additional instances")
        
        print(f"\n📋 BREAKDOWN BY PII TYPE:")
        for pii_type, count in summary['pii_types'].items():
            detection_method = "🔍 REGEX" if pii_type in regex_types else "🤖 LLM"
            print(f"  {detection_method} {pii_type.upper()}: {count}")
        
        # Convert matches to serializable format
        pii_matches = [{
            "text": match.text,
            "type": match.pii_type.value,
            "start_pos": match.start_pos,
            "end_pos": match.end_pos,
            "confidence": match.confidence,
            "detection_method": "regex" if match.pii_type.value in regex_types else "llm"
        } for match in all_matches]
        
        processing_duration = time.time() - start_time
        
        # Store results in database (using original method)
        db_manager.store_pii_results(file_id, summary, pii_matches, processing_duration)
        
        print(f"\n{'='*60}")
        print(f"PII DETECTION COMPLETED FOR FILE: {file_id}")
        print(f"⏱️  Processing time: {processing_duration:.2f} seconds")
        print(f"💾 Results stored in database")
        print(f"{'='*60}")
        
        # Save detailed results to JSON file with enhanced info
        output_dir = "pii_results"
        os.makedirs(output_dir, exist_ok=True)
        
        output_data = {
            "file_id": file_id,
            "processing_timestamp": datetime.now().isoformat(),
            "processing_duration": processing_duration,
            "detection_summary": {
                "total_matches": len(all_matches),
                "regex_matches": len(regex_matches),
                "llm_only_matches": len(llm_only_matches),
                "high_confidence_count": summary['high_confidence_count']
            },
            "pii_summary": summary,
            "matches_with_detection_method": pii_matches,
            "original_text_length": len(extracted_text),
            "regex_types_checked": list(regex_types),
            "llm_types_possible": ['name', 'address', 'religion', 'ethnicity', 'date_of_birth', 'driver_license', 'bank_account', 'other']
        }
        
        output_filename = f"pii_results_{file_id}.json"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"📁 Detailed results saved to: {output_path}")
        
        # Final diagnostic if no LLM matches found
        if not llm_only_matches:
            print(f"\n⚠️  DIAGNOSTIC: LLM found no additional PII")
            print(f"   - Text length: {len(extracted_text):,} characters")
            print(f"   - This might indicate:")
            print(f"     • Text only contains PII detectable by regex")
            print(f"     • LLM confidence threshold too high")
            print(f"     • Text format not suitable for LLM analysis")
            print(f"     • Ollama/LLM service issues")
            
            # Show a sample of what LLM is analyzing
            sample_size = min(500, len(extracted_text))
            print(f"   - Sample text being analyzed by LLM:")
            print(f"     {repr(extracted_text[:sample_size])}")
        
    except Exception as e:
        print(f"\n❌ ERROR in PII detection for file {file_id}: {e}")
        import traceback
        traceback.print_exc()

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

        # === DIAGNOSTIC BLOCK START ===
        if extracted_text and character_count > 0:
            print(f"\n{'='*50}")
            print("TEXT EXTRACTION SUCCESSFUL - PREPARING PII DETECTION")
            print(f"{'='*50}")
            print(f"📄 File ID: {file_id}")
            print(f"📄 Original filename: {file.filename}")
            print(f"📄 File type: {mime_type}")
            print(f"📄 Extraction method: {extraction_method}")
            print(f"📊 Character count: {character_count:,}")
            print(f"📊 File size: {file_size:,} bytes")
            print(f"🔧 PII Detection Available: {PII_DETECTION_AVAILABLE}")
            
            if character_count > 100:
                print(f"📝 Text preview (first 300 characters):")
                print(f"   {repr(extracted_text[:300])}")
                if len(extracted_text) > 300:
                    print(f"   ... (and {len(extracted_text) - 300:,} more characters)")
            
            if PII_DETECTION_AVAILABLE:
                print(f"🚀 Starting PII detection in background thread...")
                # Start PII detection in a separate thread
                pii_thread = threading.Thread(
                    target=process_pii_detection, 
                    args=(file_id, extracted_text)
                )
                pii_thread.daemon = True
                pii_thread.start()
                print(f"✅ PII detection thread started for file {file_id}")
            else:
                print("❌ PII detection module not available")
                
            pii_status = 'started' if PII_DETECTION_AVAILABLE and character_count > 0 else 'unavailable'
            
        else:
            print(f"\n{'='*50}")
            print("TEXT EXTRACTION FAILED OR NO TEXT FOUND")
            print(f"{'='*50}")
            print(f"📄 File ID: {file_id}")
            print(f"📄 Original filename: {file.filename}")
            print(f"📄 File type: {mime_type}")
            print(f"📄 Extraction method: {extraction_method}")
            print(f"📊 Character count: {character_count}")
            print(f"❌ Extracted text: {repr(extracted_text[:100] if extracted_text else 'None')}")
            print(f"❌ Extraction errors: {extraction_errors}")
            
            pii_status = 'not_applicable'

        # === DIAGNOSTIC BLOCK END ===

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
        # Clean up file if it exists
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': str(e)}), 500

@app.route('/document/<file_id>', methods=['GET'])
def get_document(file_id):
    """Retrieve document information by file_id"""
    try:
        doc = db_manager.get_document(file_id)
        if not doc:
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
        return jsonify({'error': str(e)}), 500

@app.route('/document/<file_id>/pii', methods=['GET'])
def get_pii_results(file_id):
    """Get detailed PII results for a specific document"""
    try:
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
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'documents_count': doc_count,
            'pii_results_count': pii_count,
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
    app.run(debug=True, host='0.0.0.0', port=5000)