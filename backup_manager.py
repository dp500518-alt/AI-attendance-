import os
import zipfile
import datetime
import json
import shutil
import config

MAX_BACKUPS = 30


def get_backup_list():
    """
    Scans config.BACKUPS_DIR for zip backup files and returns sorted list of backups.
    """
    if not os.path.exists(config.BACKUPS_DIR):
        return []

    files = [f for f in os.listdir(config.BACKUPS_DIR) if f.endswith('.zip')]
    backups = []

    for fname in sorted(files, reverse=True):
        fpath = os.path.join(config.BACKUPS_DIR, fname)
        size_bytes = os.path.getsize(fpath) if os.path.exists(fpath) else 0
        size_mb = round(size_bytes / (1024 * 1024), 2)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")

        backups.append({
            'filename': fname,
            'filepath': fpath,
            'size_mb': size_mb,
            'created_at': mtime
        })

    return backups


def create_backup(notes="Automated Daily Backup"):
    """
    Creates a timestamped .zip backup of Database, Dataset, Embeddings, Models, and Timetables.
    Prunes old backups exceeding MAX_BACKUPS limit.
    """
    try:
        os.makedirs(config.BACKUPS_DIR, exist_ok=True)
        now_str = datetime.datetime.now().strftime("%Y%m%d_%HMM%S")
        zip_filename = f"smart_attendance_backup_{now_str}.zip"
        zip_filepath = os.path.join(config.BACKUPS_DIR, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Backup SQLite Database
            if os.path.exists(config.DB_PATH):
                zipf.write(config.DB_PATH, arcname="database/smart_attendance.db")

            # 2. Backup Dataset Directory
            if os.path.exists(config.DATASET_DIR):
                for root, _, files in os.walk(config.DATASET_DIR):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, config.DATA_DIR)
                        zipf.write(full_path, arcname=rel_path)

            # 3. Backup Embeddings Directory
            if os.path.exists(config.EMBEDDINGS_DIR):
                for root, _, files in os.walk(config.EMBEDDINGS_DIR):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, config.DATA_DIR)
                        zipf.write(full_path, arcname=rel_path)

            # 4. Backup Models Directory
            if os.path.exists(config.MODELS_DIR):
                for root, _, files in os.walk(config.MODELS_DIR):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, config.DATA_DIR)
                        zipf.write(full_path, arcname=rel_path)

            # 5. Save Backup Manifest
            manifest = {
                'backup_filename': zip_filename,
                'created_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'notes': notes,
                'data_dir': config.DATA_DIR
            }
            zipf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

        # Prune old backups keeping latest MAX_BACKUPS (30)
        prune_old_backups(max_keep=MAX_BACKUPS)

        size_mb = round(os.path.getsize(zip_filepath) / (1024 * 1024), 2)
        print(f"Backup created successfully: {zip_filename} ({size_mb} MB)")
        return {
            'success': True,
            'filename': zip_filename,
            'filepath': zip_filepath,
            'size_mb': size_mb,
            'message': f"Backup {zip_filename} created ({size_mb} MB)."
        }

    except Exception as e:
        print(f"Error creating backup: {e}")
        return {'success': False, 'message': str(e)}


def prune_old_backups(max_keep=30):
    """Prunes old backups keeping only the latest max_keep files."""
    backups = get_backup_list()
    if len(backups) > max_keep:
        to_delete = backups[max_keep:]
        for b in to_delete:
            try:
                if os.path.exists(b['filepath']):
                    os.remove(b['filepath'])
                    print(f"Pruned old backup: {b['filename']}")
            except Exception as e:
                print(f"Error pruning {b['filename']}: {e}")


def restore_backup(zip_filename):
    """
    Restores the specified backup .zip archive into config.DATA_DIR.
    """
    zip_filepath = os.path.join(config.BACKUPS_DIR, zip_filename)
    if not os.path.exists(zip_filepath):
        return {'success': False, 'message': f"Backup file {zip_filename} not found."}

    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zipf:
            zipf.extractall(config.DATA_DIR)

        print(f"Backup {zip_filename} restored successfully into {config.DATA_DIR}.")
        
        # Re-initialize DB
        import database
        database.init_db()

        return {'success': True, 'message': f"Successfully restored system from {zip_filename}."}
    except Exception as e:
        print(f"Error restoring backup {zip_filename}: {e}")
        return {'success': False, 'message': str(e)}
