import json
import re
import os
import requests
import sqlite3
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum

class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    IC = "ic"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    DRIVER_LICENSE = "driver_license"
    PASSPORT = "passport"
    BANK_ACCOUNT = "bank_account"
    IP_ADDRESS = "ip_address"
    RELIGION = "religion"
    ETHNICITY = "ethnicity"
    OTHER = "other"

@dataclass
class PIIMatch:
    text: str
    pii_type: PIIType
    start_pos: int
    end_pos: int
    confidence: float

class PIIDetector:
    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "gemma3"):
        """
        Initialize PII Detector with Ollama configuration
        
        Args:
            ollama_host: Ollama server URL
            model: Model name to use (e.g., 'llama3.2', 'mistral', 'codellama')
        """
        self.ollama_host = ollama_host
        self.model = model
        self.regex_patterns = self._compile_regex_patterns()
    
    def _compile_regex_patterns(self) -> Dict[PIIType, re.Pattern]:
        """Compile regex patterns for common PII types"""
        patterns = {
            PIIType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            PIIType.PHONE: re.compile(r'\b(?:\+?60|0)1[0-46-9]-?\d{7,8}\b'),
            PIIType.IC: re.compile(r'\b\d{6}-\d{2}-\d{4}\b'),
            PIIType.CREDIT_CARD: re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            PIIType.IP_ADDRESS: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            # PIIType.ADDRESS: re.compile(r'\b(?:jalan|jln|lorong|lrg|taman|tmn|kampung|kg|bandar|persiaran|blok|block|blk|unit|no\.?|apt|apartment|condo|mines|flat)[\s,.:#\-]*[a-zA-Z0-9\s,\'\-/.()]{3,}\b', re.IGNORECASE),
            PIIType.PASSPORT: re.compile(r'\b[A-Z]{1}\d{7,8}\b'),
        }

        return patterns
    
    def _regex_detect(self, text: str) -> List[PIIMatch]:
        """Use regex patterns to detect obvious PII"""
        matches = []
        
        for pii_type, pattern in self.regex_patterns.items():
            for match in pattern.finditer(text):
                matches.append(PIIMatch(
                    text=match.group(),
                    pii_type=pii_type,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=0.95  # High confidence for regex matches
                ))
        
        return matches
    
    def _call_ollama(self, prompt: str) -> str:
        """Make API call to Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent results
                        "top_p": 0.9,
                        "num_predict": 1000
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama: {e}")
            return ""
    
    def _llm_detect(self, text: str, debug: bool = False) -> List[PIIMatch]:
        """Use LLM to detect PII that regex might miss"""
        
        # Take only first 2000 characters to avoid overwhelming the LLM
        text_sample = text[:2000] if len(text) > 2000 else text
        
        prompt = f"""
You are a data privacy expert. Analyze the following text and identify all personally identifiable information (PII).

Text to analyze:
\"\"\"{text_sample}\"\"\"

Instructions:
1. Identify all PII including:
- Full names (especially Malaysian or regionally common names like "Ahmad bin Ali", "Tan Siew Ling", "Muthu Kumar", "A/P Rani", "Wang Chen", "Lee Ming", etc.)
- Religious affiliation (e.g., Islam, Christianity, Hinduism, Buddhism, Taoism, Atheist, etc.)
- Ethnic identity (e.g., Malay, Chinese, Indian, Bumiputera, Foreigner, Sabahan, Sarawakian, Bidayuh, etc.)
- Addresses (house number, street, city, postcode, state, country)
- Date of birth or age
- NRIC / IC number (e.g., 920101-14-5678)
- Driver license numbers
- Passport numbers
- Bank account or credit card numbers
- Phone numbers and emails
- Any other sensitive personal or identifying data

2. Do NOT identify false positives like company names, generic terms, system messages, or placeholders.

3. Return your findings in this exact JSON format:

{{
    "pii_found": [
        {{
            "text": "exact text found",
            "type": "name|address|date_of_birth|driver_license|passport|bank_account|email|phone|nric|ethnicity|religion|other",
            "start_position": start_index,
            "end_position": end_index,
            "confidence": confidence_score_0_to_1
        }}
    ]
}}

Only return the JSON, no other text.
"""
        
        response = self._call_ollama(prompt)
        
        if debug:
            print("=== LLM RESPONSE DEBUG ===")
            print(f"Raw response length: {len(response)}")
            print(f"First 500 chars: {response[:500]}")
            print("========================")
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                
                if debug:
                    print(f"Extracted JSON: {json_str[:200]}...")
                
                result = json.loads(json_str)
                
                matches = []
                for item in result.get("pii_found", []):
                    # Map string types to enum
                    type_mapping = {
                        "name": PIIType.NAME,
                        "address": PIIType.ADDRESS,
                        "date_of_birth": PIIType.DATE_OF_BIRTH,
                        "driver_license": PIIType.DRIVER_LICENSE,
                        "passport": PIIType.PASSPORT,
                        "bank_account": PIIType.BANK_ACCOUNT,
                        "email": PIIType.EMAIL,
                        "phone": PIIType.PHONE,
                        "nric": PIIType.IC,
                        "ethnicity": PIIType.ETHNICITY,
                        "religion": PIIType.RELIGION,
                        "other": PIIType.OTHER
                    }
                    
                    pii_type = type_mapping.get(item.get("type", "other"), PIIType.OTHER)
                    
                    matches.append(PIIMatch(
                        text=item.get("text", ""),
                        pii_type=pii_type,
                        start_pos=item.get("start_position", 0),
                        end_pos=item.get("end_position", 0),
                        confidence=item.get("confidence", 0.5)
                    ))
                
                if debug:
                    print(f"Parsed {len(matches)} LLM matches")
                
                return matches
                
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing LLM response: {e}")
            if debug:
                print(f"Failed JSON string: {json_str if 'json_str' in locals() else 'Could not extract JSON'}")
        
        return []
    
    def detect_pii(self, text: str, use_llm: bool = True, confidence_threshold: float = 0.7, debug: bool = False) -> List[PIIMatch]:
        """
        Detect PII in text using both regex and LLM
        
        Args:
            text: Text to analyze
            use_llm: Whether to use LLM detection (slower but more accurate)
            confidence_threshold: Minimum confidence score to include results
            debug: Whether to print debug information
            
        Returns:
            List of PII matches found
        """
        all_matches = []
        
        # First, use regex for fast detection of obvious patterns
        regex_matches = self._regex_detect(text)
        all_matches.extend(regex_matches)
        
        if debug:
            print(f"Found {len(regex_matches)} regex matches")
        
        # Then use LLM for more sophisticated detection
        if use_llm:
            llm_matches = self._llm_detect(text, debug=debug)
            all_matches.extend(llm_matches)
        
        # Remove duplicates and filter by confidence
        filtered_matches = []
        seen_positions = set()
        
        for match in all_matches:
            if match.confidence >= confidence_threshold:
                # Check for overlaps
                overlap = False
                for start, end in seen_positions:
                    if (match.start_pos < end and match.end_pos > start):
                        overlap = True
                        break
                
                if not overlap:
                    filtered_matches.append(match)
                    seen_positions.add((match.start_pos, match.end_pos))
        
        return sorted(filtered_matches, key=lambda x: x.start_pos)
    
    def get_pii_summary(self, matches: List[PIIMatch]) -> Dict[str, Any]:
        """Generate summary of detected PII"""
        summary = {
            "total_pii_found": len(matches),
            "pii_types": {},
            "high_confidence_count": 0,
            "matches": []
        }
        
        for match in matches:
            pii_type_str = match.pii_type.value
            summary["pii_types"][pii_type_str] = summary["pii_types"].get(pii_type_str, 0) + 1
            
            if match.confidence >= 0.9:
                summary["high_confidence_count"] += 1
            
            summary["matches"].append({
                "text": match.text,
                "type": pii_type_str,
                "position": [match.start_pos, match.end_pos],
                "confidence": match.confidence
            })
        
        return summary

# Database functions remain the same
def get_latest_extracted_text(db_path: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Connects to the SQLite database and retrieves the latest extracted_text value based on created_at timestamp.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT id, extracted_text, created_at 
        FROM extracted_text 
        ORDER BY created_at DESC 
        LIMIT 1
        """
        
        print(f"Executing query: {query}")
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            record_id, extracted_text, created_at = result
            print(f"Retrieved latest record (ID: {record_id}) from {created_at}")
            print(f"Text length: {len(extracted_text)} characters")
            return record_id, extracted_text, created_at
        else:
            print("No extracted text found in the database.")
            return None, None, None
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None, None, None

def test_database_connection(db_path: str):
    """Test the database connection and show table structure"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_text'")
        if not cursor.fetchone():
            print("Table 'extracted_text' does not exist!")
            return
        
        # Show table structure
        cursor.execute("PRAGMA table_info(extracted_text)")
        columns = cursor.fetchall()
        print("Table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM extracted_text")
        count = cursor.fetchone()[0]
        print(f"Total records: {count}")
        
        # Show latest records with timestamps
        cursor.execute("""
            SELECT id, LENGTH(extracted_text), created_at 
            FROM extracted_text 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        samples = cursor.fetchall()
        print("Latest records (ID, text_length, timestamp):")
        for sample in samples:
            print(f"  Record {sample[0]}: {sample[1]} chars, {sample[2]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def main():
    """Example usage with enhanced debugging"""
    db_path = "document_storage.db"
    
    # Test database first
    print("=== Testing Database Connection ===")
    test_database_connection(db_path)
    
    # Get latest text based on timestamp
    print("\n=== Getting Latest Text (by timestamp) ===")
    record_id, sample_text, created_at = get_latest_extracted_text(db_path)
    
    if not sample_text:
        print("No text to analyze.")
        return
    
    print(f"Processing record {record_id} created at {created_at}")
    print(f"Text length: {len(sample_text)} characters")
    
    # Initialize detector
    detector = PIIDetector(model="gemma3")
    
    # Detect PII with debugging enabled
    print("\nDetecting PII...")
    matches = detector.detect_pii(sample_text, use_llm=True, debug=True)
    
    # Print results by type
    print(f"\nFound {len(matches)} PII instances:")
    
    # Group by type for better overview
    by_type = {}
    for match in matches:
        pii_type = match.pii_type.value
        if pii_type not in by_type:
            by_type[pii_type] = []
        by_type[pii_type].append(match)
    
    for pii_type, type_matches in by_type.items():
        print(f"\n{pii_type.upper()} ({len(type_matches)} found):")
        for match in type_matches[:5]:  # Show first 5 of each type
            print(f"  - '{match.text}' (confidence: {match.confidence:.2f})")
        if len(type_matches) > 5:
            print(f"  ... and {len(type_matches) - 5} more")
    
    # Get summary
    summary = detector.get_pii_summary(matches)
    
    # Save results with record ID and timestamp
    output_data = {
        "record_id": record_id,
        "created_at": created_at,
        "processing_timestamp": "2025-07-27T20:30:00",
        "pii_summary": summary,
        "original_text_length": len(sample_text),
        "matches": [{
            "text": match.text,
            "type": match.pii_type.value,
            "start_pos": match.start_pos,
            "end_pos": match.end_pos,
            "confidence": match.confidence
        } for match in matches],
        "original_text": sample_text
    }
    
    # Ensure the folder exists
    output_dir = "json_output"
    os.makedirs(output_dir, exist_ok=True)

    # Clean up timestamp for filename safety
    timestamp_clean = created_at.replace(':', '-').replace(' ', '_').replace('.', '_')
    output_filename = f"pii_results_record_{record_id}_{timestamp_clean}.json"

    # Join the folder path and filename
    output_path = os.path.join(output_dir, output_filename)

    # Write JSON to the file
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()