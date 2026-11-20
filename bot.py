import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
from dotenv import load_dotenv
import os
import time
from datetime import datetime
import pytz

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

last_notification = {}  # {(notifier_id, tracked_user_id, guild_id): timestamp}
COOLDOWN_SECONDS = 60
DEFAULT_TZ = 'Atlantic/Canary'

# ==============
# region CONFIG
# ==============
DB_FILE = 'tracking_data.db'

class DatabaseManager:
    """Gestiona la conexión persistente y optimizaciones de SQLite"""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self._setup_db()

    def _setup_db(self):
        # Optimizaciones para Raspberry Pi / NanoPi (Protección de SD)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_configs (
                user_id TEXT PRIMARY KEY,
                start_hour INTEGER,
                end_hour INTEGER,
                timezone TEXT DEFAULT 'Atlantic/Canary'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracker (
                notifier_id TEXT,
                guild_id TEXT,
                target_id TEXT,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY (notifier_id, guild_id, target_id)
            )
        ''')
        self.conn.commit()

    def execute(self, query, params=()):
        """Ejecuta una operación de escritura (INSERT, UPDATE, DELETE)"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetch(self, query, params=()):
        """Ejecuta una operación de lectura (SELECT)"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

# Inicializamos el gestor de base de datos una sola vez
db = DatabaseManager(DB_FILE)

# endregion

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True          # Necesario para obtener información de los miembros
intents.voice_states = True     # Necesario para rastrear cambios en canales de voz
intents.guilds = True           # Necesario para interactuar con los servidores

# C5 — Subclase para mover tree.sync() a setup_hook y que no se re-ejecute
#        en cada reconexión de Discord (on_ready se dispara en cada reconnect).
class MangusBot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Slash commands sincronizados con Discord.")

bot = MangusBot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot iniciado como {bot.user.name}')

# ==========================================
# region COMANDOS DE RASTREO
# ==========================================

# Helper: guard reutilizable para comandos que solo funcionan en servidores.
# C4 — Evita AttributeError cuando un usuario invoca un comando desde DM.
async def _require_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Este comando solo funciona dentro de un servidor.", ephemeral=True
        )
        return False
    return True

@bot.tree.command(name="config_global", description="Configura tu horario de notificaciones general")
@app_commands.describe(inicio="Hora inicio (0-23)", fin="Hora fin (0-23)")
async def config_global(interaction: discord.Interaction, inicio: int, fin: int):
    if not (0 <= inicio <= 23 and 0 <= fin <= 23):
        await interaction.response.send_message("Las horas deben estar entre 0 y 23.", ephemeral=True)
        return

    # M4 — El DO UPDATE incluye ahora timezone para no bloquear la feature de
    #        zona horaria personalizable en el futuro.
    db.execute('''
        INSERT INTO user_configs (user_id, start_hour, end_hour, timezone)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            start_hour=excluded.start_hour,
            end_hour=excluded.end_hour,
            timezone=excluded.timezone
    ''', (str(interaction.user.id), inicio, fin, DEFAULT_TZ))

    await interaction.response.send_message(
        f"**Configuracion Global Aplicada**\n"
        f"Horario: `{inicio}:00` a `{fin}:00` (Canarias).\n\n"
        f"*Este horario se usara para tus rastreos en **todos** los servidores donde este el bot.*",
        ephemeral=True
    )

@bot.tree.command(name="tracker", description="Empieza a rastrear a un usuario")
@app_commands.describe(usuario="Usuario a rastrear")
async def tracker(interaction: discord.Interaction, usuario: discord.Member):
    if not await _require_guild(interaction):  # C4
        return

    res = db.fetch("SELECT start_hour, end_hour, timezone FROM user_configs WHERE user_id = ?", (str(interaction.user.id),))

    if not res:
        await interaction.response.send_message(
            "No tienes un horario configurado. Usa `/config_global` antes de añadir rastreos.",
            ephemeral=True
        )
        return

    start, end, _ = res[0]
    db.execute(
        "INSERT OR IGNORE INTO tracker (notifier_id, guild_id, target_id, enabled) VALUES (?, ?, ?, ?)",
        (str(interaction.user.id), str(interaction.guild.id), str(usuario.id), 1)
    )

    await interaction.response.send_message(
        f"Ahora rastreas a **{usuario.name}**. Se usara tu horario global: {start}:00 a {end}:00.",
        ephemeral=True
    )

@bot.tree.command(name="tracker_remove", description="Dejar de rastrear a un usuario")
@app_commands.describe(usuario="Usuario a dejar de rastrear")
async def tracker_remove(interaction: discord.Interaction, usuario: discord.Member):
    if not await _require_guild(interaction):  # C4
        return

    cursor = db.execute("DELETE FROM tracker WHERE notifier_id = ? AND guild_id = ? AND target_id = ?",
                        (str(interaction.user.id), str(interaction.guild.id), str(usuario.id)))
    count = cursor.rowcount

    if count > 0:
        await interaction.response.send_message(f"Has dejado de rastrear a **{usuario.name}**.", ephemeral=True)
    else:
        await interaction.response.send_message("No estabas rastreando a este usuario.", ephemeral=True)

@bot.tree.command(name="tracker_list", description="Ver a quien estas rastreando")
async def tracker_list(interaction: discord.Interaction):
    if not await _require_guild(interaction):  # C4
        return

    config = db.fetch("SELECT start_hour, end_hour, timezone FROM user_configs WHERE user_id = ?", (str(interaction.user.id),))
    if not config:
        await interaction.response.send_message("No tienes configuracion global establecida.", ephemeral=True)
        return

    start, end, _ = config[0]
    rows = db.fetch("SELECT target_id FROM tracker WHERE notifier_id = ? AND guild_id = ?",
                    (str(interaction.user.id), str(interaction.guild.id)))

    if not rows:
        await interaction.response.send_message(f"No rastreas a nadie. Horario: {start}:00-{end}:00.", ephemeral=True)
        return

    nombres = []
    for (target_id,) in rows:
        member = interaction.guild.get_member(int(target_id))
        name = member.name if member else f"Desconocido ({target_id})"
        nombres.append(f"- **{name}**")

    await interaction.response.send_message(
        f"**Configuracion Global:** {start}:00 - {end}:00 (Canarias)\n"
        f"**Usuarios rastreados:**\n" + "\n".join(nombres),
        ephemeral=True
    )

@bot.tree.command(name="tracker_clear", description="Eliminar todos los usuarios que estas rastreando")
async def tracker_clear(interaction: discord.Interaction):
    if not await _require_guild(interaction):  # C4
        return

    db.execute("DELETE FROM tracker WHERE notifier_id = ? AND guild_id = ?",
               (str(interaction.user.id), str(interaction.guild.id)))

    await interaction.response.send_message("Has eliminado todos tus rastreos en este servidor.", ephemeral=True)

@bot.tree.command(name="tracker_off", description="Silenciar temporalmente las notificaciones de este servidor")
async def tracker_off(interaction: discord.Interaction):
    if not await _require_guild(interaction):  # C4
        return

    db.execute("UPDATE tracker SET enabled = 0 WHERE notifier_id = ? AND guild_id = ?",
               (str(interaction.user.id), str(interaction.guild.id)))
    await interaction.response.send_message("Notificaciones silenciadas.", ephemeral=True)

@bot.tree.command(name="tracker_on", description="Reactivar las notificaciones de este servidor")
async def tracker_on(interaction: discord.Interaction):
    if not await _require_guild(interaction):  # C4
        return

    db.execute("UPDATE tracker SET enabled = 1 WHERE notifier_id = ? AND guild_id = ?",
               (str(interaction.user.id), str(interaction.guild.id)))
    await interaction.response.send_message("Notificaciones reactivadas.", ephemeral=True)


@bot.tree.command(name="tracker_help", description="Ver todos los comandos disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Comandos disponibles",
        description="Lista de comandos del bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="/config_global [inicio] [fin]",
                    value="Establece tu horario de avisos global (0-23).", inline=False)
    embed.add_field(name="/tracker @usuario",
                    value="Empieza a rastrear a un usuario.", inline=False)
    embed.add_field(name="/tracker_remove @usuario",
                    value="Deja de rastrear a un usuario.", inline=False)
    embed.add_field(name="/tracker_list",
                    value="Muestra tus ajustes y rastreos.", inline=False)
    embed.add_field(name="/tracker_clear",
                    value="Elimina todos los rastreos.", inline=False)
    embed.add_field(name="/tracker_off",
                    value="Pausa todas tus notificaciones en este servidor.", inline=False)
    embed.add_field(name="/tracker_on",
                    value="Reanuda tus notificaciones en este servidor.", inline=False)
    embed.set_footer(text="Las respuestas son privadas | Notificaciones por MD")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# endregion

# --- LOGICA DE TIEMPO ---
def is_in_schedule(start, end, tz_name):
    # C3 — Captura excepciones especificas en lugar de bare except.
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        current_hour = now.hour

        if start <= end:
            return start <= current_hour < end
        else:
            return current_hour >= start or current_hour < end
    except pytz.UnknownTimeZoneError:
        logger.warning(f"Zona horaria desconocida: '{tz_name}'. Se permite la notificacion por defecto.")
        return True
    except Exception as e:
        logger.error(f"Error inesperado en is_in_schedule (tz={tz_name}): {e}")
        return True

# M3 — Tarea periodica para purgar entradas antiguas de last_notification.
#       Evita que el dict crezca indefinidamente en un proceso 24/7.
@tasks.loop(hours=1)
async def cleanup_cooldown_cache():
    cutoff = time.time() - COOLDOWN_SECONDS * 2
    stale_keys = [k for k, v in last_notification.items() if v < cutoff]
    if stale_keys:
        for k in stale_keys:
            del last_notification[k]
        logger.info(f"Cooldown cache: {len(stale_keys)} entradas antiguas eliminadas.")

# --- NOTIFICACION POR MD ---
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        notifiers = db.fetch('''
            SELECT t.notifier_id, c.start_hour, c.end_hour, c.timezone
            FROM tracker t
            JOIN user_configs c ON t.notifier_id = c.user_id
            WHERE t.guild_id = ? AND t.target_id = ? AND t.enabled = 1
        ''', (str(member.guild.id), str(member.id)))

        for notifier_id, start, end, tz_name in notifiers:
            if not is_in_schedule(start, end, tz_name):
                continue

            key = (notifier_id, str(member.id), str(member.guild.id))
            now = time.time()
            if key in last_notification and (now - last_notification[key] < COOLDOWN_SECONDS):
                continue

            # C3 — Captura excepciones especificas para diagnosticar fallos reales
            #       en produccion. El cooldown se registra solo si el envio fue exitoso.
            try:
                user = await bot.fetch_user(int(notifier_id))
                canal_url = f"https://discord.com/channels/{member.guild.id}/{after.channel.id}"
                mensaje = (
                    f"Aviso de conexion\n"
                    f"**{member.name}** entro a [{after.channel.name}]({canal_url}) en **{member.guild.name}**"
                )
                await user.send(mensaje)
                last_notification[key] = now  # Solo se registra si el envio fue exitoso
            except discord.Forbidden:
                logger.warning(
                    f"No se pudo enviar DM a notifier_id={notifier_id}: DMs cerrados o bot bloqueado."
                )
            except discord.HTTPException as e:
                logger.error(
                    f"Error HTTP enviando DM a notifier_id={notifier_id}: "
                    f"status={e.status} text='{e.text}'"
                )
            except Exception as e:
                logger.error(
                    f"Error inesperado en notificacion a notifier_id={notifier_id}: {e}"
                )

@bot.event
async def on_connect():
    # Arrancamos la tarea de limpieza solo cuando el bot se conecte.
    if not cleanup_cooldown_cache.is_running():
        cleanup_cooldown_cache.start()

bot.run(TOKEN)
