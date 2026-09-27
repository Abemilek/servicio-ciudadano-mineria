# ============================================
# src/database.py
# SERVICIO CIUDADANO 1800 - CONEXIÓN SQL SERVER
# Adaptado del ejemplo del profesor para: Zorin OS (Linux),
# SQL Server en contenedor Docker, driver ODBC 18.
# ============================================

import os
import pandas as pd
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_connection_string():
    """
    Construye la cadena de conexión para SQL Server corriendo en Docker.
    En Linux, el driver típico es 'ODBC Driver 18 for SQL Server', y ese
    driver exige indicar explícitamente Encrypt/TrustServerCertificate
    porque por defecto fuerza TLS estricto (el contenedor usa un
    certificado autofirmado).
    """
    server   = os.getenv('DB_SERVER', 'localhost')
    port     = os.getenv('DB_PORT', '1433')
    database = os.getenv('DB_NAME', 'ServicioCiudadanoDW')
    driver   = os.getenv('DB_DRIVER', 'ODBC Driver 18 for SQL Server')
    user     = os.getenv('DB_USER', 'sa')
    password = os.getenv('DB_PASSWORD', '')
    encrypt  = os.getenv('DB_ENCRYPT', 'no')  # 'no' es lo normal en desarrollo local con Docker

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate=yes;"
    )
    return conn_str


def get_connection():
    """Establece y retorna una conexión activa a SQL Server."""
    try:
        conn = pyodbc.connect(get_connection_string())
        return conn
    except pyodbc.Error as e:
        print("❌ Error de conexión a SQL Server:")
        print(f"   {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que el contenedor esté corriendo: docker ps")
        print("   2. Revisa las credenciales en el archivo .env")
        print(f"   3. Asegúrate de que la base '{os.getenv('DB_NAME')}' ya exista "
              "(corre sql/01_datawarehouse.sql primero)")
        print("   4. Verifica que el driver ODBC 18 esté instalado (ver INSTALACION.md)")
        return None


def execute_query(query, params=None):
    """Ejecuta un SELECT y retorna un DataFrame de pandas."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        df = pd.read_sql_query(query, conn, params=params) if params else pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"❌ Error en consulta SQL: {e}")
        return None
    finally:
        conn.close()


def execute_non_query(sql):
    """Ejecuta una sentencia sin retorno (INSERT/UPDATE/DELETE/DDL)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"❌ Error ejecutando sentencia: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def execute_script_file(script_path):
    """
    Ejecuta un archivo .sql completo separando por 'GO' (que pyodbc no
    entiende) y por ';'. Pensado para correr sql/01_datawarehouse.sql y
    sql/02_poblar_dw_y_datasets.sql desde Python si no quieres usar
    sqlcmd ni una extensión de VSCodium.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            contenido = f.read()

        # separar por lotes GO (cada lote puede tener varias sentencias con ';')
        lotes = [l for l in contenido.split('\nGO') if l.strip()]
        cursor = conn.cursor()
        for i, lote in enumerate(lotes, 1):
            lote = lote.strip()
            if not lote:
                continue
            try:
                cursor.execute(lote)
                conn.commit()
            except Exception as e:
                print(f"  ⚠️ Lote {i} con advertencia: {str(e)[:120]}")
                conn.rollback()
        cursor.close()
        print(f"✅ Script completado: {script_path}")
        return True
    except Exception as e:
        print(f"❌ Error ejecutando script: {e}")
        return False
    finally:
        conn.close()


def test_connection():
    """Prueba de conexión: versión del servidor, BD activa y tablas."""
    print("=" * 60)
    print("🔍 PRUEBA DE CONEXIÓN A SQL SERVER (Docker)")
    print("=" * 60)

    conn = get_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        print(f"\n📊 Versión SQL Server:\n   {cursor.fetchone()[0][:80]}...")

        cursor.execute("SELECT DB_NAME()")
        print(f"\n📁 Base de datos activa: {cursor.fetchone()[0]}")

        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME
        """)
        tablas = [row[0] for row in cursor.fetchall()]
        print(f"\n📋 Tablas encontradas ({len(tablas)}):")
        for t in tablas:
            print(f"   • {t}")

        cursor.close()
        print("\n🎉 ¡Conexión verificada exitosamente!")
        return True
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    test_connection()
