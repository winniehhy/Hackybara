import os
import base64
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime
from multi_file import DatabaseManager
from typing import Optional
import sqlite3

DB_PATH = 'document_storage.db'
db_manager = DatabaseManager(DB_PATH)

def get_latest_extracted_text_only(db_path: str) -> Optional[str]:
    """
    Retrieves only the latest 'extracted_text' field from the database.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT extracted_text 
            FROM extracted_text 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if result:
            (extracted_text,) = result
            return extracted_text
        else:
            print("No extracted text found.")
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def encrypt_pii_from_reviewed(file_id: str):
    # Fetch reviewed metadata from DB
    metadata = db_manager.get_reviewed(file_id)
    print(f"Metadata for file_id {file_id}: {metadata}")
    
    text = get_latest_extracted_text_only(DB_PATH)
    print(f"Extracted text for file_id {file_id}: {text}")
    
    if text is None:
        raise ValueError(f"No text found for file_id: {file_id}")
    
    def get_start_end(match):
        if "position" in match:
            return match["position"][0], match["position"][1]
        return match["start_pos"], match["end_pos"]

    matches = sorted(metadata["pii_matches"], key=lambda x: get_start_end(x)[0])

    # Generate AES-GCM key and nonce
    key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    encrypted_text = ""
    token_map = {}
    last_idx = 0

    for match in matches:
        start, end = get_start_end(match)
        pii_text = text[start:end]
        pii_type = match["type"]

        ciphertext = aesgcm.encrypt(nonce, pii_text.encode(), None)
        b64_cipher = base64.b64encode(ciphertext).decode()
        token_id = str(uuid.uuid4())[:8]

        encrypted_text += text[last_idx:start]
        encrypted_text += f"<enc:id={token_id};type={pii_type}>"
        last_idx = end

        token_map[token_id] = {
            "original": pii_text,
            "type": pii_type,
            "cipher": b64_cipher
        }

    encrypted_text += text[last_idx:]

    metadata_record = {
        "key": base64.b64encode(key).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "tokens": token_map,
        "tokenized_text": encrypted_text
    }

    # Save to DB instead of file
    db_manager.save_encrypted_pii(file_id, encrypted_text, metadata_record)

    print(f"✅ Tokenized text and metadata saved to database for file_id: {file_id}")
