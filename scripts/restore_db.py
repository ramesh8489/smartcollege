import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "database_backups"
DB_FILE = BASE_DIR / "db.sqlite3"


def restore():
    print("=" * 60)
    print(" SmartCollege ERP - Restore Database Backup")
    print("=" * 60)
    
    if not BACKUP_DIR.exists():
        print(f"[!] No backup directory found at: {BACKUP_DIR}")
        return

    # Look for latest db or json
    latest_db = BACKUP_DIR / "latest_db.sqlite3"
    db_backups = sorted(BACKUP_DIR.glob("db_*.sqlite3"), reverse=True)
    json_backups = sorted(BACKUP_DIR.glob("data_*.json"), reverse=True)

    if not db_backups and not json_backups:
        print("[!] No backups found in database_backups directory.")
        return

    print("Found available backups:")
    if db_backups:
        print(f" - Latest SQLite snapshot: {db_backups[0].name}")
    if json_backups:
        print(f" - Latest JSON export:     {json_backups[0].name}")

    # Restore physical file
    target_db = db_backups[0] if db_backups else None
    if target_db:
        # Keep emergency copy of current DB if exists
        if DB_FILE.exists():
            shutil.copy2(DB_FILE, BACKUP_DIR / "before_restore_db.sqlite3")
            print("[*] Created safety copy of current db.sqlite3 as before_restore_db.sqlite3")
        
        shutil.copy2(target_db, DB_FILE)
        print(f"[OK] Successfully restored db.sqlite3 from {target_db.name}!")
    
    # Run django check to verify
    python_exe = sys.executable
    check_res = subprocess.run([python_exe, str(BASE_DIR / "manage.py"), "check"], cwd=BASE_DIR)
    if check_res.returncode == 0:
        print("[OK] Django database system check passed with 0 issues!")
    
    print("\n" + "=" * 60)
    print(" Database restore completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    restore()
