from lib_utils import TMP_DIR
from pathlib import Path

# Normalize TMP_DIR as a Path
TMP_DIR = Path(TMP_DIR)

LOCK_DIGEST = TMP_DIR / "digest.lock"

def main():
    print("Digest v2 OK, lock path:", LOCK_DIGEST)

if __name__ == "__main__":
    main()
