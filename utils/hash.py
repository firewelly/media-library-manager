import hashlib

def calculate_md5(path: str, chunk_size: int = 4 * 1024 * 1024) -> str:
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

