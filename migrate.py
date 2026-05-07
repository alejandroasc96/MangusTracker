import sqlite3

def migrate():
    conn = sqlite3.connect('tracking_data.db')
    cursor = conn.cursor()
    
    print("Iniciando migración de base de datos...")
    
    try:
        cursor.execute("ALTER TABLE tracker ADD COLUMN start_hour INTEGER DEFAULT 16")
        cursor.execute("ALTER TABLE tracker ADD COLUMN end_hour INTEGER DEFAULT 22")
        cursor.execute("ALTER TABLE tracker ADD COLUMN timezone TEXT DEFAULT 'Atlantic/Canary'")
        
        conn.commit()
        print("✅ Columnas añadidas correctamente.")
    except sqlite3.OperationalError as e:
        print(f"⚠️ Nota: {e} (Probablemente las columnas ya existían)")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()