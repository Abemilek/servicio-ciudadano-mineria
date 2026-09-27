# ============================================
# verificar_instalacion.py
# Verifica que todas las librerías y el driver ODBC estén listos
# ============================================


def verificar():
    print("=" * 60)
    print("🔍 VERIFICACIÓN DE INSTALACIÓN")
    print("=" * 60)

    errores = []
    import sys
    print(f"\n🐍 Python: {sys.version}")

    for nombre, modulo in [
        ("pandas", "pandas"), ("numpy", "numpy"), ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"), ("sqlalchemy", "sqlalchemy"), ("python-dotenv", "dotenv"),
    ]:
        try:
            mod = __import__(modulo)
            version = getattr(mod, "__version__", "instalado")
            print(f"✅ {nombre}: {version}")
        except ImportError:
            errores.append(nombre)

    # pyodbc + drivers ODBC (crítico para conectar al contenedor)
    try:
        import pyodbc
        print(f"✅ pyodbc: {pyodbc.version}")
        print("\n📋 Drivers ODBC disponibles en el sistema:")
        drivers = pyodbc.drivers()
        if drivers:
            for d in drivers:
                print(f"   • {d}")
            if not any("SQL Server" in d for d in drivers):
                print("   ⚠️ No se ve 'ODBC Driver 18 for SQL Server'. Revisa INSTALACION.md, paso 3.")
                errores.append("ODBC Driver 18 for SQL Server")
        else:
            print("   ⚠️ No se encontraron drivers ODBC instalados.")
            errores.append("ODBC Driver 18 for SQL Server")
    except ImportError:
        errores.append("pyodbc")

    print("\n" + "=" * 60)
    if errores:
        print(f"❌ Faltan {len(errores)} dependencias: {', '.join(errores)}")
        print("💡 Revisa INSTALACION.md — para el driver ODBC no basta con pip install.")
    else:
        print("🎉 ¡Todas las dependencias están instaladas!")
    print("=" * 60)


if __name__ == "__main__":
    verificar()
