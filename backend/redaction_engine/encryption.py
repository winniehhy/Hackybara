# import json
# import os
# from cryptography.hazmat.primitives.ciphers.aead import AESGCM
# import base64

# def encrypt_pii_in_plaintext(input_path: str, pii_metadata_path: str):
#     # Load metadata
#     with open(pii_metadata_path, 'r') as f:
#         metadata = json.load(f)

#     text = metadata["original_text"]
#     matches = sorted(metadata["pii_summary"]["matches"], key=lambda x: x["position"][0])
    
#     # Generate AES-GCM key and nonce
#     key = AESGCM.generate_key(bit_length=256)
#     aesgcm = AESGCM(key)
#     nonce = os.urandom(12)

#     redaction_log = []
#     encrypted_text = ""
#     last_idx = 0

#     for match in matches:
#         start, end = match["position"]
#         pii_text = text[start:end]

#         # Encrypt the PII text
#         ciphertext = aesgcm.encrypt(nonce, pii_text.encode(), None)
#         b64_cipher = base64.b64encode(ciphertext).decode()

#         # Replace in text
#         encrypted_text += text[last_idx:start]
#         encrypted_text += f"<enc:{b64_cipher}>"

#         # Update log
#         redaction_log.append({
#             "original": pii_text,
#             "position": [start, end],
#             "type": match["type"],
#             "encrypted": b64_cipher
#         })
#         last_idx = end

#     encrypted_text += text[last_idx:]  # Append remaining text

#     # Write encrypted output
#     output_file = input_path.replace(".txt", "_encrypted.txt")
#     with open(output_file, "w") as f:
#         f.write(encrypted_text)

# 	# Store log, key, and encrypted_text
#     log_file = input_path.replace(".txt", "_encryption_metadata.json")
#     with open(log_file, "w") as f:
#         json.dump({
#             "key": base64.b64encode(key).decode(),
#             "nonce": base64.b64encode(nonce).decode(),
#             "log": redaction_log,
#             "encrypted_text": encrypted_text
#         }, f, indent=2)


#     print(f"Encrypted file saved to: {output_file}")
#     print(f"Redaction log saved to: {log_file}")


# encrypt_pii_in_plaintext("input.txt", "pii_metadata.json")
import json
import os
import base64
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_pii_in_plaintext(input_path: str, pii_metadata_path: str):
    # Load metadata
    with open(pii_metadata_path, 'r') as f:
        metadata = json.load(f)

    text = metadata["original_text"]
    matches = sorted(metadata["pii_summary"]["matches"], key=lambda x: x["position"][0])

    # Generate AES-GCM key and nonce
    key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    encrypted_text = ""
    token_map = {}
    last_idx = 0

    for match in matches:
        start, end = match["position"]
        pii_text = text[start:end]
        pii_type = match["type"]

        # Encrypt the PII text
        ciphertext = aesgcm.encrypt(nonce, pii_text.encode(), None)
        b64_cipher = base64.b64encode(ciphertext).decode()

        # Generate unique token ID
        token_id = str(uuid.uuid4())[:8]  # shorten UUID to 8 chars for readability

        # Replace in text with token reference
        encrypted_text += text[last_idx:start]
        encrypted_text += f"<enc:id={token_id};type={pii_type}>"
        last_idx = end

        # Store in token map
        token_map[token_id] = {
            "original": pii_text,
            "type": pii_type,
            "cipher": b64_cipher
        }

    encrypted_text += text[last_idx:]  # Append any remaining text

    # Write encrypted output
    output_file = input_path.replace(".txt", "_tokenized.txt")
    with open(output_file, "w") as f:
        f.write(encrypted_text)

    # Write token map and encryption info
    log_file = input_path.replace(".txt", "_encryption_metadata.json")
    with open(log_file, "w") as f:
        json.dump({
            "key": base64.b64encode(key).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "tokens": token_map,
            "tokenized_text": encrypted_text
        }, f, indent=2)

    print(f"Tokenized file saved to: {output_file}")
    print(f"Encryption metadata saved to: {log_file}")

# Example usage
encrypt_pii_in_plaintext("input.txt", "pii_metadata.json")
