import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def decrypt_pii_from_json(log_path: str, encrypted_file_path: str):
    # Load encrypted file
    with open(encrypted_file_path, "r") as f:
        encrypted_text = f.read()

    # Load redaction log
    with open(log_path, "r") as f:
        metadata = json.load(f)

    key = base64.b64decode(metadata["key"])
    nonce = base64.b64decode(metadata["nonce"])
    pii_log = metadata["log"]

    aesgcm = AESGCM(key)

    # Replace encrypted segments
    for pii in pii_log:
        b64_cipher = pii["encrypted"]
        ciphertext = base64.b64decode(b64_cipher)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None).decode()

        encrypted_token = f"<enc:{b64_cipher}>"
        encrypted_text = encrypted_text.replace(encrypted_token, decrypted)

    # Save decrypted output
    output_path = encrypted_file_path.replace("_encrypted.txt", "_decrypted.txt")
    with open(output_path, "w") as f:
        f.write(encrypted_text)

    print(f"Decrypted file saved to: {output_path}")


decrypt_pii_from_json("input_encryption_metadata.json", "input_encrypted.txt")
