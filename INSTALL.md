# Guía de Instalación — MangusTracker 🥭

Instrucciones para desplegar el bot en un servidor Linux con **systemd**.

---

## Requisitos previos

| Requisito | Versión mínima | Verificar |
|-----------|---------------|-----------|
| Python 3 | 3.9+ | `python3 --version` |
| pip / venv | — | `python3 -c "import venv"` |
| systemd | cualquiera | `systemctl --version` |
| git | cualquiera | `git --version` |

Instalar dependencias del sistema en Debian/Ubuntu/Raspberry Pi OS:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
```

---

## Paso 1 — Clonar el repositorio

Clona el proyecto en la carpeta que prefieras en cada máquina:

```bash
git clone https://github.com/alejandroasc96/MangusTracker.git /ruta/de/tu/eleccion/MangusTracker
cd /ruta/de/tu/eleccion/MangusTracker
```

> **Nota:** El script detecta automáticamente su ubicación (`SCRIPT_DIR`),  
> así que puedes clonarlo en cualquier ruta sin modificar nada.

---

## Paso 2 — Configurar el token de Discord

Crea el archivo `.env` con el token de tu bot:

```bash
nano .env
```

Contenido del archivo:

```dotenv
DISCORD_TOKEN=tu_token_de_discord_aqui
```

> ⚠️ **Nunca subas este archivo a git.** Ya está incluido en `.gitignore`.

Protege el archivo con permisos restrictivos:

```bash
chmod 600 .env
```

---

## Paso 3 — Ejecutar el script de instalación

Desde **dentro del directorio del proyecto**, ejecuta:

```bash
sudo -E bash install.sh
```

> El flag `-E` preserva las variables de entorno del usuario actual,  
> necesario para que `SUDO_USER` sea reconocido correctamente.

El script realiza automáticamente las siguientes acciones:

1. ✅ Detecta la ruta del proyecto (`SCRIPT_DIR`) de forma dinámica
2. ✅ Valida que `python3`, `venv` y `systemctl` estén disponibles
3. ✅ Verifica/crea el archivo `.env` y valida que `DISCORD_TOKEN` no esté vacío
4. ✅ Crea/actualiza el entorno virtual en `./venv/` e instala las dependencias de `requirements.txt`
5. ✅ Genera `/etc/systemd/system/mangus-tracker.service`
6. ✅ Ejecuta `systemctl daemon-reload`
7. ✅ Ejecuta `systemctl enable mangus-tracker` (arranque automático)
8. ✅ Ejecuta `systemctl start mangus-tracker` (o `restart` si ya corría)
9. ✅ Verifica que el servicio quedó activo

---

## Paso 4 — Comprobar que el servicio está activo

Verificar estado y que está habilitado en el arranque:

```bash
sudo systemctl status mangus-tracker
```

La salida debe mostrar:

```
● mangus-tracker.service - MangusTracker Discord Bot
     Loaded: loaded (/etc/systemd/system/mangus-tracker.service; enabled; ...)
     Active: active (running) since ...
```

- **`enabled`** → el bot arrancará automáticamente tras un reinicio del servidor.
- **`active (running)`** → el bot está corriendo en este momento.

---

## Comandos de gestión del servicio

```bash
# Ver estado detallado
sudo systemctl status mangus-tracker

# Ver logs en tiempo real
sudo journalctl -u mangus-tracker -f

# Ver los últimos 50 mensajes de log
sudo journalctl -u mangus-tracker -n 50 --no-pager

# Parar el bot
sudo systemctl stop mangus-tracker

# Iniciar el bot
sudo systemctl start mangus-tracker

# Reiniciar el bot (p.ej. tras actualizar el código)
sudo systemctl restart mangus-tracker

# Deshabilitar el arranque automático
sudo systemctl disable mangus-tracker
```

---

## Actualizar el bot

Cuando haya una nueva versión del código:

```bash
cd /ruta/donde/clonaste/MangusTracker
git pull
sudo -E bash install.sh
```

El script es **idempotente**: puede reejecutarse de forma segura.  
Detectará el venv existente, actualizará dependencias y reiniciará el servicio.

---

## Estructura del servicio generado

El script crea el siguiente archivo en `/etc/systemd/system/mangus-tracker.service`:

```ini
[Unit]
Description=MangusTracker Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<usuario-que-ejecutó-el-script>
WorkingDirectory=<SCRIPT_DIR>
EnvironmentFile=<SCRIPT_DIR>/.env
ExecStart=<SCRIPT_DIR>/venv/bin/python3 <SCRIPT_DIR>/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mangus-tracker
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

| Directiva | Efecto |
|-----------|--------|
| `Restart=always` | El bot se reinicia automáticamente ante cualquier fallo |
| `RestartSec=10` | Espera 10 segundos antes de cada reinicio |
| `EnvironmentFile` | Carga el `.env` sin exponer secretos en el comando |
| `WorkingDirectory` | El bot arranca en su propio directorio (necesario para SQLite) |
| `NoNewPrivileges` | Protección de seguridad básica |
| `WantedBy=multi-user.target` | Se activa en el arranque normal del sistema |

---

## Solución de problemas

### El servicio no arranca

```bash
sudo journalctl -u mangus-tracker -n 100 --no-pager
```

Causas comunes:

| Síntoma en el log | Causa probable | Solución |
|-------------------|----------------|----------|
| `DISCORD_TOKEN` inválido / `LoginFailure` | Token incorrecto o expirado | Editar `.env` y `sudo systemctl restart mangus-tracker` |
| `ModuleNotFoundError` | Dependencia no instalada | `sudo -E bash install.sh` |
| `PermissionError` en SQLite | El directorio no tiene permisos de escritura | `sudo chown -R $USER .` |
| `network-online.target` no resuelto | Sin conexión a Internet al arrancar | Verificar red; el bot reintentará automáticamente |

### Verificar que el token es correcto

```bash
grep DISCORD_TOKEN .env
```

### El servicio queda en estado `failed`

```bash
sudo systemctl reset-failed mangus-tracker
sudo systemctl start mangus-tracker
```

---

## Notas adicionales

- **Base de datos:** `tracking_data.db` se crea automáticamente en el directorio del proyecto al primer arranque. Está en `.gitignore` para no comprometerse por error.
- **Zona horaria por defecto:** `Atlantic/Canary` (configurable por usuario desde Discord con `/config_global`).
- **Optimizado para hardware embebido:** El modo WAL de SQLite reduce escrituras en la tarjeta SD (Raspberry Pi / NanoPi).
