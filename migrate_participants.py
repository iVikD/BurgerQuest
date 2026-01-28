import json
import os
import sys

# Set encoding for Windows terminal
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_PATH = 'BurgerQuest/data/meals.json'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = 0
    for entry in data:
        if 'participants' not in entry:
            entry['participants'] = [entry['sender']]
            updated += 1
            
    if updated > 0:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: Migrated {updated} entries.")
    else:
        print("INFO: No entries needed migration.")

if __name__ == "__main__":
    migrate()
