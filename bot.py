import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os
import time

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

last_notification = {}  # {(notifier_id, tracked_user_id, guild_id): timestamp}
COOLDOWN_SECONDS = 60

# ==========================================
# region CONFIG
# ==========================================
DB_FILE = 'tracking_data.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True          # Necesario para obtener información de los miembros
intents.voice_states = True     # Necesario para rastrear cambios en canales de voz
intents.guilds = True           # Necesario para interactuar con los servidores

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print(f'✅ Bot iniciado como {bot.user.name}')

# endregion

# ==========================================
# region COMANDOS DE RASTREO
# ==========================================
@bot.tree.command(name="tracker", description="Empieza a rastrear a un usuario")
@app_commands.describe(usuario="Usuario a rastrear")
async def tracker(interaction: discord.Interaction, usuario: discord.Member):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
            "INSERT OR IGNORE INTO tracker (notifier_id, guild_id, target_id, enabled) VALUES (?, ?, ?, ?)", 
            (str(interaction.user.id), str(interaction.guild.id), str(usuario.id), 1)
        )

    conn.commit()
    conn.close()
    await interaction.response.send_message(
        f"✅ Ahora rastreas a **{usuario.name}** en **{interaction.guild.name}**.",
        ephemeral=True
    )

# --- UNTRACKER (SLASH) ---
@bot.tree.command(name="untracker", description="Dejar de rastrear a un usuario")
@app_commands.describe(usuario="Usuario a dejar de rastrear")
async def untracker(interaction: discord.Interaction, usuario: discord.Member):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracker WHERE notifier_id = ? AND guild_id = ? AND target_id = ?", 
                    (str(interaction.user.id), str(interaction.guild.id), str(usuario.id)))
    conn.commit()
    count = cursor.rowcount
    conn.close()

    if count > 0:
        await interaction.response.send_message(
            f"✅ Has dejado de rastrear a **{usuario.name}**.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ No estabas rastreando a este usuario.",
            ephemeral=True
        )

@bot.tree.command(name="tracker_list", description="Ver a quién estás rastreando")
async def tracker_list(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id FROM tracker WHERE notifier_id = ? AND guild_id = ?", 
                    (str(interaction.user.id), str(interaction.guild.id)))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("ℹ️ No estás rastreando a nadie en este servidor.", ephemeral=True)
        return

    nombres = []
    for (target_id,) in rows:
        member = interaction.guild.get_member(int(target_id))
        nombres.append(f"• {member.name if member else 'Usuario desconocido (' + target_id + ')'}")

    await interaction.response.send_message(
        f"📋 **Usuarios que estás rastreando:**\n" + "\n".join(nombres),
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

    await interaction.response.send_message(
        "🧹 Has eliminado todos los usuarios que estabas rastreando en este servidor.",
        ephemeral=True
    )

@bot.tree.command(name="tracker_off", description="Silenciar temporalmente las notificaciones de este servidor")
async def tracker_off(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tracker SET enabled = 0 WHERE notifier_id = ? AND guild_id = ?", 
                (str(interaction.user.id), str(interaction.guild.id)))
    conn.commit()
    conn.close()
    await interaction.response.send_message("🔕 Notificaciones silenciadas para este servidor.", ephemeral=True)

@bot.tree.command(name="tracker_on", description="Reactivar las notificaciones de este servidor")
async def tracker_on(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tracker SET enabled = 1 WHERE notifier_id = ? AND guild_id = ?", 
                (str(interaction.user.id), str(interaction.guild.id)))
    conn.commit()
    conn.close()
    await interaction.response.send_message("🔔 Notificaciones reactivadas para este servidor.", ephemeral=True)

@bot.tree.command(name="tracker_help", description="Ver todos los comandos disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Comandos disponibles",
        description="Lista de comandos del bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="🔎 /tracker @usuario", value="Empieza a rastrear a un usuario.", inline=False)
    embed.add_field(name="❌ /untracker @usuario", value="Deja de rastrear a un usuario.", inline=False)
    embed.add_field(name="📋 /tracker_list", value="Muestra a quién estás rastreando.", inline=False)
    embed.add_field(name="🧹 /tracker_clear", value="Elimina todos los rastreos.", inline=False)
    embed.set_footer(text="Las respuestas son privadas | Notificaciones por MD")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# endregion

# --- NOTIFICACIÓN POR MD ---
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT notifier_id FROM tracker WHERE guild_id = ? AND target_id = ? AND enabled = 1", 
                        (str(member.guild.id), str(member.id)))
        notifiers = cursor.fetchall()
        conn.close()

        for (notifier_id,) in notifiers:
            key = (notifier_id, str(member.id), str(member.guild.id))
            now = time.time()
            if key in last_notification and (now - last_notification[key] < COOLDOWN_SECONDS):
                continue

            try:
                user = await bot.fetch_user(int(notifier_id))
                canal_url = f"https://discord.com/channels/{member.guild.id}/{after.channel.id}"
                mensaje = (
                    f"🔔 **Aviso de conexión**\n"
                    f"**{member.name}** entró a [{after.channel.name}]({canal_url}) en **{member.guild.name}**"
                )
                await user.send(mensaje)
                last_notification[key] = now
            except:
                continue

bot.run(TOKEN)