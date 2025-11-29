import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def decode_survival_dat(file_bytes):
    """
    Decrypts .dat files from the 'local-survival' source.
    These files are encrypted with AES-128-CBC.
    """
    try:
        key = b"holoearthmasters"
        iv = file_bytes[:16]
        encrypted_content = file_bytes[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        decrypted_data = unpad(cipher.decrypt(encrypted_content), AES.block_size)
        return json.loads(decrypted_data)
    except Exception as e:
        print(f"ERROR: Failed to decrypt and parse data. Reason: {e}")
        return None
