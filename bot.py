import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os
import time
from datetime import datetime
import pytz

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

last_notification = {}  # {(notifier_id, tracked_user_id, guild_id): timestamp}
COOLDOWN_SECONDS = 60
DEFAULT_TZ = 'Atlantic/Canary'

# ==========================================
# region CONFIG Y CACHÉ EN MEMORIA
# ==========================================
DB_FILE = 'tracking_data.db'

# Diccionario global para acceso ultrarrápido en RAM
# Estructura: { target_id: [ {"notifier_id": ..., "guild_id": ..., "start_hour": ..., "end_hour": ..., "timezone": ...}, ... ] }
TRACKER_CACHE = {}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

def update_cache():
    """Carga todos los rastreos activos de la BD a la memoria RAM de golpe."""
    global TRACKER_CACHE
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Obtenemos solo los rastreos activos junto con los horarios de sus notificadores
    cursor.execute('''
        SELECT t.target_id, t.notifier_id, t.guild_id, c.start_hour, c.end_hour, c.timezone 
        FROM tracker t
        JOIN user_configs c ON t.notifier_id = c.user_id
        WHERE t.enabled = 1
    ''')
    rows = cursor.fetchall()
    conn.close()

    new_cache = {}
    for target_id, notifier_id, guild_id, start, end, tz in rows:
        if target_id not in new_cache:
            new_cache[target_id] = []
        new_cache[target_id].append({
            'notifier_id': notifier_id,
            'guild_id': guild_id,
            'start_hour': start,
            'end_hour': end,
            'timezone': tz
        })
    
    TRACKER_CACHE = new_cache
    print(f"🔄 Caché sincronizada. {sum(len(v) for v in TRACKER_CACHE.values())} rastreos activos en memoria.")

def get_user_config(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT start_hour, end_hour, timezone FROM user_configs WHERE user_id = ?", (str(user_id),))
    res = cursor.fetchone()
    conn.close()
    return res

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True          # Necesario para obtener información de los miembros
intents.voice_states = True     # Necesario para rastrear cambios en canales de voz
intents.guilds = True           # Necesario para interactuar con los servidores

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    init_db()
    update_cache()  # Primera carga de la caché al arrancar el bot
    await bot.tree.sync()
    print(f'✅ Bot iniciado como {bot.user.name}')

# endregion

# ==========================================
# region COMANDOS DE RASTREO
# ==========================================
@bot.tree.command(name="config_global", description="Configura tu horario de notificaciones general")
@app_commands.describe(inicio="Hora inicio (0-23)", fin="Hora fin (0-23)")
async def config_global(interaction: discord.Interaction, inicio: int, fin: int):
    if not (0 <= inicio <= 23 and 0 <= fin <= 23):
        await interaction.response.send_message("❌ Las horas deben estar entre 0 y 23.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_configs (user_id, start_hour, end_hour, timezone) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET start_hour=excluded.start_hour, end_hour=excluded.end_hour
    ''', (str(interaction.user.id), inicio, fin, DEFAULT_TZ))
    conn.commit()
    conn.close()

    update_cache()  # Actualizamos RAM para aplicar cambios de horario inmediatamente

    await interaction.response.send_message(
        f"✅ **Configuración Global Aplicada**\n"
        f"⏰ Horario: `{inicio}:00` a `{fin}:00` (Canarias).\n\n"
        f"ℹ️ *Este horario se usará para tus rastreos en **todos** los servidores donde esté el bot.*",
        ephemeral=True
    )

@bot.tree.command(name="tracker", description="Empieza a rastrear a un usuario")
@app_commands.describe(usuario="Usuario a rastrear")
async def tracker(interaction: discord.Interaction, usuario: discord.Member):
    config = get_user_config(interaction.user.id)
    
    if not config:
        await interaction.response.send_message(
            "⚠️ No tienes un horario configurado. Usa `/config_global` antes de añadir rastreos.",
            ephemeral=True
        )
        return

    start, end, _ = config
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO tracker (notifier_id, guild_id, target_id, enabled) VALUES (?, ?, ?, ?)", 
        (str(interaction.user.id), str(interaction.guild.id), str(usuario.id), 1)
    )
    conn.commit()
    conn.close()

    update_cache()  # Refrescamos la RAM con el nuevo rastreo añadido

    await interaction.response.send_message(
        f"✅ Ahora rastreas a **{usuario.name}**. Se usará tu horario global: {start}:00 a {end}:00.",
        ephemeral=True
    )

# --- tracker_remove (SLASH) ---
@bot.tree.command(name="tracker_remove", description="Dejar de rastrear a un usuario")
@app_commands.describe(usuario="Usuario a dejar de rastrear")
async def tracker_remove(interaction: discord.Interaction, usuario: discord.Member):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracker WHERE notifier_id = ? AND guild_id = ? AND target_id = ?", 
                    (str(interaction.user.id), str(interaction.guild.id), str(usuario.id)))
    conn.commit()
    count = cursor.rowcount
    conn.close()

    if count > 0:
        update_cache()  # Refrescamos la RAM al eliminar un elemento
        await interaction.response.send_message(f"✅ Has dejado de rastrear a **{usuario.name}**.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No estabas rastreando a este usuario.", ephemeral=True)

@bot.tree.command(name="tracker_list", description="Ver a quién estás rastreando")
async def tracker_list(interaction: discord.Interaction):
    config = get_user_config(interaction.user.id)
    if not config:
        await interaction.response.send_message("❌ No tienes configuración global establecida.", ephemeral=True)
        return

    start, end, _ = config
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id FROM tracker WHERE notifier_id = ? AND guild_id = ?", 
                    (str(interaction.user.id), str(interaction.guild.id)))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(f"ℹ️ No rastreas a nadie. Horario: {start}:00-{end}:00.", ephemeral=True)
        return

    nombres = []
    for (target_id,) in rows:
        member = interaction.guild.get_member(int(target_id))
        name = member.name if member else f"Desconocido ({target_id})"
        nombres.append(f"• **{name}**")

    await interaction.response.send_message(
        f"📋 **Configuración Global:** {start}:00 - {end}:00 (Canarias) \n"
        f"**Usuarios rastreados:**\n" + "\n".join(nombres),
        ephemeral=True
    )

@bot.tree.command(name="tracker_clear", description="Eliminar todos los usuarios que estás rastreando")
async def tracker_clear(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracker WHERE notifier_id = ? AND guild_id = ?", 
                    (str(interaction.user.id), str(interaction.guild.id)))
    conn.commit()
    conn.close()

    update_cache()  # Refrescamos la RAM tras limpiar la lista

    await interaction.response.send_message("🧹 Has eliminado todos tus rastreos en este servidor.", ephemeral=True)

@bot.tree.command(name="tracker_off", description="Silenciar temporalmente las notificaciones de este servidor")
async def tracker_off(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tracker SET enabled = 0 WHERE notifier_id = ? AND guild_id = ?", 
                (str(interaction.user.id), str(interaction.guild.id)))
    conn.commit()
    conn.close()
    
    update_cache()  # Refrescamos RAM ya que 'enabled' cambió a 0 y debe salir de la caché rápida
    
    await interaction.response.send_message("🔕 Notificaciones silenciadas.", ephemeral=True)

@bot.tree.command(name="tracker_on", description="Reactivar las notificaciones de este servidor")
async def tracker_on(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tracker SET enabled = 1 WHERE notifier_id = ? AND guild_id = ?", 
                (str(interaction.user.id), str(interaction.guild.id)))
    conn.commit()
    conn.close()
    
    update_cache()  # Refrescamos RAM para meter de nuevo los rastreos activos en la caché rápida
    
    await interaction.response.send_message("🔔 Notificaciones reactivadas.", ephemeral=True)


@bot.tree.command(name="tracker_help", description="Ver todos los comandos disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Comandos disponibles",
        description="Lista de comandos del bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="⚙️ /config_global [inicio] [fin]",
                    value="Establece tu horario de avisos global (0-23).", inline=False)
    embed.add_field(name="🔎 /tracker @usuario",
                    value="Empieza a rastrear a un usuario.", inline=False)
    embed.add_field(name="❌ /tracker_remove @usuario",
                    value="Deja de rastrear a un usuario.", inline=False)
    embed.add_field(name="📋 /tracker_list",
                    value="Muestra tus ajustes y rastreos.", inline=False)
    embed.add_field(name="🧹 /tracker_clear",
                    value="Elimina todos los rastreos.", inline=False)
    embed.add_field(name="🔕 /tracker_off",
                    value="Pausa todas tus notificaciones en este servidor.", inline=False)
    embed.add_field(name="🔔 /tracker_on",
                    value="Reanuda tus notificaciones en este servidor.", inline=False)
    embed.set_footer(
        text="Las respuestas son privadas | Notificaciones por MD")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# endregion

# --- LÓGICA DE TIEMPO ---
def is_in_schedule(start, end, tz_name):
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        current_hour = now.hour

        if start <= end:
            return start <= current_hour < end
        else:
            return current_hour >= start or current_hour < end
    except:
        return True
    
# --- NOTIFICACIÓN POR MD (OPTIMIZADA USANDO RAM) ---
@bot.event
async def on_voice_state_update(member, before, after):
    # Condición de disparo: Entrar a un canal desde un estado desconectado
    if before.channel is None and after.channel is not None:
        target_id = str(member.id)
        guild_id = str(member.guild.id)

        # Si el usuario que entró no está siendo seguido por nadie activo, terminamos de inmediato.
        # ¡Cero consultas a la MicroSD!
        if target_id not in TRACKER_CACHE:
            return

        # Iteramos sobre los notificadores guardados en la RAM para este usuario
        for entry in TRACKER_CACHE[target_id]:
            # Filtrar que corresponda al mismo servidor
            if entry['guild_id'] != guild_id:
                continue

            notifier_id = entry['notifier_id']
            start = entry['start_hour']
            end = entry['end_hour']
            tz_name = entry['timezone']

            # Comprobar la zona horaria
            if not is_in_schedule(start, end, tz_name):
                continue

            # Anti-Spam Cooldown
            key = (notifier_id, target_id, guild_id)
            now = time.time()
            if key in last_notification and (now - last_notification[key] < COOLDOWN_SECONDS):
                continue

            # Enviar la alerta por mensaje privado
            try:
                user = await bot.fetch_user(int(notifier_id))
                canal_url = f"https://discord.com/channels/{guild_id}/{after.channel.id}"
                mensaje = (
                    f"🔔 **Aviso de conexión**\n"
                    f"**{member.name}** entró a [{after.channel.name}]({canal_url}) en **{member.guild.name}**"
                )
                await user.send(mensaje)
                last_notification[key] = now
            except:
                continue

bot.run(TOKEN)