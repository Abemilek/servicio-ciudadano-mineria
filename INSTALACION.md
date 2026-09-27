# Instalación — Zorin OS + Docker + VSCodium

Pensado para tu setup: **Zorin OS** (basado en Ubuntu), **SQL Server en Docker**,
**VSCodium** como editor.

---

## 1. Docker (si aún no lo tienes)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker

# para no tener que usar sudo con cada comando docker:
sudo usermod -aG docker $USER
# cierra sesión y vuelve a entrar (o reinicia) para que aplique
```

Verifica:
```bash
docker --version
docker compose version
```

## 2. Levantar SQL Server en un contenedor

Desde la raíz del proyecto (donde está `docker-compose.yml`):

```bash
docker compose up -d
```

Espera unos 15–20 segundos a que el contenedor termine de arrancar (SQL Server
tarda en inicializar). Verifica que esté sano:

```bash
docker ps
# debe mostrar servicio-ciudadano-sqlserver como "healthy" o "Up"
```

## 3. Driver ODBC 18 para SQL Server en Linux (necesario para pyodbc)

Microsoft no lo trae Ubuntu/Zorin por defecto, hay que agregar su repositorio:

```bash
sudo apt update
sudo apt install -y curl gnupg2

curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc

curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
# si tu Zorin está basado en una versión distinta de Ubuntu, cambia "22.04" por
# la que corresponda (lsb_release -rs te dice cuál usa tu sistema)

sudo apt update
ACCEPT_EULA=Y sudo apt install -y msodbcsql18 unixodbc-dev
```

Verifica que quedó instalado:
```bash
odbcinst -q -d
# debe listar: [ODBC Driver 18 for SQL Server]
```

## 4. Entorno virtual de Python

```bash
cd ruta/al/proyecto
python3 -m venv venv
source venv/bin/activate       # en Linux es "source", no "venv\Scripts\activate"

pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configurar el `.env`

```bash
cp .env.example .env
```

Los valores por defecto ya coinciden con la contraseña del `docker-compose.yml`
(`Integrador2026!`), así que si no cambiaste nada, no necesitas tocar el `.env`.

## 6. Crear la base de datos y el Data Warehouse

Puedes usar `sqlcmd` dentro del propio contenedor (no requiere instalar nada más):

```bash
docker exec -it servicio-ciudadano-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Integrador2026!' -C \
  -i /dev/stdin < sql/01_datawarehouse.sql
```

Con eso queda creada la base `ServicioCiudadanoDW` y toda la estructura
(staging + dimensiones + hecho).

> **Alternativa desde VSCodium:** instala la extensión **"SQL Server (mssql)"**
> (de Microsoft) desde Open VSX, conéctate a `localhost,1433` con usuario `sa`
> y la contraseña del `.env`, abre `sql/01_datawarehouse.sql` y ejecútalo con
> el botón "Run".

## 7. Generar los datos y poblar el Data Warehouse

```bash
# sigue con el entorno virtual activado
python verificar_instalacion.py     # confirma que todo esté instalado
python test_conexion.py             # confirma que conecta (aún sin datos)

cd src
python generar_semilla.py           # inserta ~365 registros sintéticos en c15_callcenter_v0
cd ..
```

Luego corre el segundo script SQL (ETL: staging → dimensiones/hecho + vistas de KPI),
igual que en el paso 6:

```bash
docker exec -it servicio-ciudadano-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Integrador2026!' -C \
  -i /dev/stdin < sql/02_poblar_dw_y_datasets.sql
```

Verifica que todo quedó poblado:
```bash
python test_conexion.py
```

## 8. Abrir el notebook

**Opción A — VSCodium:** instala la extensión **"Jupyter"** (de Microsoft, disponible
en Open VSX) y el kernel de Python del entorno virtual (VSCodium te lo pedirá al
abrir el `.ipynb` — selecciona el intérprete de `venv/bin/python`). Abre
`notebooks/01_kpis_recontacto_duracion.ipynb` y ejecuta las celdas.

**Opción B — JupyterLab en el navegador:**
```bash
jupyter lab
```
y abre `notebooks/01_kpis_recontacto_duracion.ipynb` desde ahí.

---

## Apagar / limpiar

```bash
docker compose down          # detiene el contenedor, conserva los datos
docker compose down -v       # detiene y BORRA los datos (vuelves a foja cero)
```
