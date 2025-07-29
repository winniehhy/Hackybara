import os
import base64
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime
from multi_file import DatabaseManager
from typing import Optional
import sqlite3
import json

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

def get_encrypted_record_with_metadata(file_id: str) -> Optional[dict]:
    """
    Retrieves the encrypted record with metadata for a given file_id.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tokenized_text, encryption_metadata 
            FROM pii_encrypted 
            WHERE file_id = ?
            ORDER BY created_at DESC 
            LIMIT 1
        """, (file_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "tokenized_text": row[0],
                "encryption_metadata": json.loads(row[1])
            }
        return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def decrypt_pii_text(file_id: str, decryption_key: str) -> Optional[str]:
    """
    Decrypts the tokenized text using the provided decryption key.
    
    Args:
        file_id: The file ID to decrypt
        decryption_key: The base64-encoded decryption key
    
    Returns:
        The decrypted original text, or None if decryption fails
    """
    try:
        # Get encrypted record
        encrypted_record = get_encrypted_record_with_metadata(file_id)
        if not encrypted_record:
            raise ValueError(f"No encrypted record found for file_id: {file_id}")
        
        tokenized_text = encrypted_record["tokenized_text"]
        metadata = encrypted_record["encryption_metadata"]
        
        # Decode the key and nonce
        try:
            key = base64.b64decode(decryption_key)
            nonce = base64.b64decode(metadata["nonce"])
        except Exception as e:
            raise ValueError(f"Invalid decryption key format: {e}")
        
        # Initialize AES-GCM
        aesgcm = AESGCM(key)
        tokens = metadata["tokens"]
        
        # Decrypt the text
        decrypted_text = tokenized_text
        
        # Replace each token with its decrypted value
        for token_id, token_data in tokens.items():
            token_pattern = f"<enc:id={token_id};type={token_data['type']}>"
            
            if token_pattern in decrypted_text:
                try:
                    # Decrypt the ciphertext
                    ciphertext = base64.b64decode(token_data["cipher"])
                    decrypted_pii = aesgcm.decrypt(nonce, ciphertext, None)
                    decrypted_text = decrypted_text.replace(token_pattern, decrypted_pii.decode())
                except Exception as e:
                    print(f"Failed to decrypt token {token_id}: {e}")
                    # If decryption fails, keep the token as is
                    continue
        
        return decrypted_text
        
    except Exception as e:
        print(f"Decryption failed: {e}")
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
    
    # Return the key for the user to save
    return {
        "file_id": file_id,
        "decryption_key": base64.b64encode(key).decode(),
        "message": "Encryption completed successfully. Save the decryption key securely!"
    }
