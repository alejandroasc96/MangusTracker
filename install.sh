#!/usr/bin/env bash
# =============================================================================
#  install.sh — MangusTracker Bot
#  Instalación y configuración automática del servicio systemd
#
#  Uso:
#    sudo -E bash install.sh           (desde cualquier ruta)
#    sudo -E ./install.sh              (desde dentro del directorio del proyecto)
#
#  Requisitos previos:
#    - python3 instalado y disponible en PATH
#    - systemd activo (distribuciones Linux modernas)
#    - Archivo .env con DISCORD_TOKEN= en el directorio del proyecto
#
#  Supuestos explícitos:
#    - El servicio se ejecuta con el usuario que lanza el script (SUDO_USER).
#    - El entorno virtual se crea en <proyecto>/venv/
#    - La base de datos SQLite se genera en <proyecto>/tracking_data.db
# =============================================================================

set -euo pipefail

# --- Colores para la salida ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}==> $*${NC}"; }

# =============================================================================
# 1. RESOLUCIÓN DINÁMICA DE LA RUTA DEL PROYECTO
# =============================================================================
header "Detectando ruta del proyecto..."

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
info "Directorio del proyecto: ${SCRIPT_DIR}"

# Determinar el usuario real del bot (preservado con sudo -E)
if [[ -n "${SUDO_USER:-}" ]]; then
    BOT_USER="${SUDO_USER}"
else
    BOT_USER="$(whoami)"
fi
info "El servicio se ejecutará como usuario: ${BOT_USER}"

SERVICE_NAME="mangus-tracker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${SCRIPT_DIR}/venv"
ENTRY_POINT="${SCRIPT_DIR}/bot.py"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

# =============================================================================
# 2. VALIDACIONES PREVIAS
# =============================================================================
header "Validando requisitos del sistema..."

if [[ "$(id -u)" -ne 0 ]]; then
    error "Este script necesita permisos de root.\nEjecútalo con:\n  sudo -E bash install.sh\n\n  El flag -E preserva las variables de entorno del usuario actual."
fi

if ! command -v python3 &>/dev/null; then
    error "python3 no encontrado. Instálalo con:\n  sudo apt install python3 python3-venv python3-pip"
fi
PYTHON_VERSION="$(python3 --version)"
success "Python encontrado: ${PYTHON_VERSION}"

if ! python3 -c "import venv" &>/dev/null; then
    error "Módulo 'venv' no disponible. Instálalo con:\n  sudo apt install python3-venv"
fi
success "Módulo venv disponible"

if ! command -v systemctl &>/dev/null; then
    error "systemctl no encontrado. Este script requiere systemd."
fi
success "systemd disponible"

if [[ ! -f "${ENTRY_POINT}" ]]; then
    error "Archivo principal no encontrado: ${ENTRY_POINT}"
fi
success "Punto de entrada encontrado: bot.py"

if [[ ! -f "${REQUIREMENTS}" ]]; then
    error "Archivo de dependencias no encontrado: ${REQUIREMENTS}"
fi
success "requirements.txt encontrado"

# =============================================================================
# 3. PREPARACIÓN DEL ARCHIVO .env
# =============================================================================
header "Verificando archivo de variables de entorno..."

if [[ -f "${ENV_FILE}" ]]; then
    success ".env ya existe — se conserva sin modificar"
else
    warn ".env no encontrado en: ${SCRIPT_DIR}"

    if [[ -f "${ENV_EXAMPLE}" ]]; then
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
        chown "${BOT_USER}:${BOT_USER}" "${ENV_FILE}" 2>/dev/null || true
        chmod 600 "${ENV_FILE}"
        warn "Se ha creado .env a partir de .env.example"
    else
        printf '# Variables de entorno de MangusTracker\n# Reemplaza el valor con el token real de tu bot de Discord\nDISCORD_TOKEN=your_discord_bot_token_here\n' > "${ENV_FILE}"
        chown "${BOT_USER}:${BOT_USER}" "${ENV_FILE}" 2>/dev/null || true
        chmod 600 "${ENV_FILE}"
        warn "Se ha creado una plantilla mínima en: ${ENV_FILE}"
    fi

    echo ""
    echo -e "${YELLOW}Acción requerida: edita el archivo .env antes de continuar:${NC}"
    echo -e "  nano ${ENV_FILE}"
    echo ""
    read -r -p "¿Has configurado el DISCORD_TOKEN en el .env? [s/N]: " CONFIRM
    CONFIRM="${CONFIRM,,}"
    if [[ "${CONFIRM}" != "s" && "${CONFIRM}" != "si" && "${CONFIRM}" != "y" && "${CONFIRM}" != "yes" ]]; then
        warn "Instalación pausada. Vuelve a ejecutar cuando hayas configurado el .env"
        exit 0
    fi
fi

chmod 600 "${ENV_FILE}"
chown "${BOT_USER}:${BOT_USER}" "${ENV_FILE}" 2>/dev/null || true

# Validar DISCORD_TOKEN con awk (evita problemas de quoting con tr/cut)
DISCORD_TOKEN_VALUE="$(awk -F= '/^DISCORD_TOKEN=/{val=$2; gsub(/[[:space:]]|"/,"",val); print val}' "${ENV_FILE}")" || true
if [[ -z "${DISCORD_TOKEN_VALUE}" || "${DISCORD_TOKEN_VALUE}" == "your_discord_bot_token_here" ]]; then
    error "DISCORD_TOKEN está vacío o no ha sido configurado en ${ENV_FILE}"
fi
success "DISCORD_TOKEN configurado correctamente"

# =============================================================================
# 4. ENTORNO VIRTUAL Y DEPENDENCIAS
# =============================================================================
header "Configurando entorno virtual de Python..."

if [[ -d "${VENV_DIR}" ]]; then
    info "Entorno virtual ya existe en: ${VENV_DIR} — actualizando dependencias..."
else
    info "Creando entorno virtual en: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
    chown -R "${BOT_USER}:${BOT_USER}" "${VENV_DIR}" 2>/dev/null || true
    success "Entorno virtual creado"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip --quiet
success "pip actualizado"

info "Instalando dependencias desde requirements.txt..."
"${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS}" --quiet
success "Dependencias instaladas correctamente"

# =============================================================================
# 5. GENERACIÓN Y ACTIVACIÓN DEL SERVICIO SYSTEMD
# =============================================================================
header "Configurando servicio systemd: ${SERVICE_NAME}"

PYTHON_EXEC="${VENV_DIR}/bin/python3"

info "Escribiendo ${SERVICE_FILE}..."
cat > "${SERVICE_FILE}" <<UNIT
[Unit]
Description=MangusTracker Discord Bot
Documentation=https://github.com/alejandroasc96/MangusTracker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USER}
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_EXEC} ${ENTRY_POINT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
UNIT

success "Archivo de servicio generado: ${SERVICE_FILE}"

info "Recargando configuración de systemd (daemon-reload)..."
systemctl daemon-reload
success "daemon-reload completado"

info "Habilitando ${SERVICE_NAME} para el arranque del sistema..."
systemctl enable "${SERVICE_NAME}"
success "Servicio habilitado en el arranque"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    info "El servicio ya estaba corriendo — reiniciando para aplicar cambios..."
    systemctl restart "${SERVICE_NAME}"
    success "Servicio reiniciado correctamente"
else
    info "Iniciando el servicio por primera vez..."
    systemctl start "${SERVICE_NAME}"
    success "Servicio iniciado correctamente"
fi

# =============================================================================
# 6. VERIFICACIÓN FINAL
# =============================================================================
header "Verificación del estado del servicio..."
sleep 2

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo ""
    echo -e "${GREEN}${BOLD}✅  MangusTracker está corriendo correctamente.${NC}"
else
    echo ""
    echo -e "${RED}${BOLD}❌  El servicio no arrancó correctamente.${NC}"
    echo -e "    Revisa los logs con:\n"
    echo -e "    ${BOLD}journalctl -u ${SERVICE_NAME} -n 50 --no-pager${NC}"
    exit 1
fi

echo ""
echo -e "${BOLD}Comandos útiles:${NC}"
echo -e "  Estado del servicio  : ${BLUE}sudo systemctl status ${SERVICE_NAME}${NC}"
echo -e "  Logs en tiempo real  : ${BLUE}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  Parar el servicio    : ${BLUE}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo -e "  Reiniciar el servicio: ${BLUE}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  Deshabilitar arranque : ${BLUE}sudo systemctl disable ${SERVICE_NAME}${NC}"
echo ""
echo -e "${GREEN}${BOLD}Instalación completada. 🥭${NC}"
