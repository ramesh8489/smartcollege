import os
import sys
import shutil
import datetime
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "database_backups"
DB_FILE = BASE_DIR / "db.sqlite3"


def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("=" * 60)
    print(" SmartCollege ERP - Safe Database Backup")
    print("=" * 60)
    
    # 1. Physical SQLite Copy
    if DB_FILE.exists():
        backup_db_file = BACKUP_DIR / f"db_{timestamp}.sqlite3"
        shutil.copy2(DB_FILE, backup_db_file)
        shutil.copy2(DB_FILE, BACKUP_DIR / "latest_db.sqlite3")
        print(f"[OK] Physical SQLite file backed up to:")
        print(f"     {backup_db_file.name}")
    else:
        print("[!] Warning: db.sqlite3 not found in root directory.")

    # 2. Django dumpdata JSON fixture
    json_backup_file = BACKUP_DIR / f"data_{timestamp}.json"
    latest_json_file = BACKUP_DIR / "latest_data.json"
    
    python_exe = sys.executable
    cmd = [
        python_exe,
        str(BASE_DIR / "manage.py"),
        "dumpdata",
        "--natural-foreign",
        "--natural-primary",
        "-e", "contenttypes",
        "-e", "auth.Permission",
        "-e", "sessions",
        "--indent", "2",
    ]
    
    print("\n[*] Exporting all records (Users, Students, Faculty, Fees, etc.) to JSON...")
    sub_env = os.environ.copy()
    sub_env["PYTHONIOENCODING"] = "utf-8"
    sub_env["PYTHONUTF8"] = "1"
    try:
        with open(json_backup_file, "w", encoding="utf-8") as f:
            res = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR, env=sub_env)
        
        if res.returncode == 0 and json_backup_file.stat().st_size > 100:
            shutil.copy2(json_backup_file, latest_json_file)
            print(f"[OK] JSON data exported successfully ({json_backup_file.stat().st_size // 1024} KB):")
            print(f"     {json_backup_file.name}")
            print(f"     latest_data.json")
        else:
            print(f"[!] Warning during dumpdata: {res.stderr}")
    except Exception as e:
        print(f"[!] Error exporting JSON: {e}")

    print("\n" + "=" * 60)
    print(" Backup completed! Your accounts and records are safe.")
    print(f" Saved in: {BACKUP_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    backup()
