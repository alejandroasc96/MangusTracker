# OBSOLETO - No ejecutar en producción
#
# Este script fue creado durante una iteración anterior del proyecto en la que
# las columnas start_hour, end_hour y timezone pertenecían a la tabla 'tracker'.
#
# El esquema actual (desde el PR #2) separa esa información en la tabla
# 'user_configs', por lo que estas columnas ya NO existen en 'tracker' y
# este script no tiene ningún efecto útil.
#
# Se mantiene como referencia histórica. Si en el futuro se necesita una
# migración real, crear un nuevo script con la fecha como prefijo, por ejemplo:
#   migrate_20261120_add_feature_x.py
#
# import sqlite3
#
# def migrate():
#     conn = sqlite3.connect('tracking_data.db')
#     cursor = conn.cursor()
#     print("Iniciando migracion de base de datos...")
#     try:
#         cursor.execute("ALTER TABLE tracker ADD COLUMN start_hour INTEGER DEFAULT 16")
#         cursor.execute("ALTER TABLE tracker ADD COLUMN end_hour INTEGER DEFAULT 22")
#         cursor.execute("ALTER TABLE tracker ADD COLUMN timezone TEXT DEFAULT 'Atlantic/Canary'")
#         conn.commit()
#         print("Columnas anadidas correctamente.")
#     except sqlite3.OperationalError as e:
#         print(f"Nota: {e} (Probablemente las columnas ya existian)")
#     finally:
#         conn.close()
#
# if __name__ == "__main__":
#     migrate()
