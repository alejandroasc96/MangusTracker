import discord
from discord import app_commands
from discord.ext import commands
import aiofiles
from dotenv import load_dotenv
import json
import os
import time

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

last_notification = {}  # {(notifier_id, tracked_user_id, guild_id): timestamp}
COOLDOWN_SECONDS = 60

# ==========================================
# region CONFIG
# ==========================================
DATA_FILE = 'tracking_data.json'

async def load_data():
    if os.path.exists(DATA_FILE):
        try:
            async with aiofiles.open(DATA_FILE, mode='r') as f:
                content = await f.read()

                return json.loads(content)
        except Exception as e:
            print(f"Error al cargar: {e}")

            return {}
    return {}

async def save_data(data):
    async with aiofiles.open(DATA_FILE, mode='w') as f:
        await f.write(json.dumps(data, indent=4))

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True          # Necesario para obtener información de los miembros
intents.voice_states = True     # Necesario para rastrear cambios en canales de voz
intents.guilds = True           # Necesario para interactuar con los servidores

bot = commands.Bot(command_prefix='!', intents=intents)
tracker_db = {}

@bot.event
async def on_ready():
    global tracker_db
    tracker_db = await load_data()
    await bot.tree.sync()
    print(f'✅ Bot iniciado como {bot.user.name}')

# endregion

# ==========================================
# region COMANDOS DE RASTREO
# ==========================================
@bot.tree.command(name="tracker", description="Empieza a rastrear a un usuario")
@app_commands.describe(usuario="Usuario a rastrear")
async def tracker(interaction: discord.Interaction, usuario: discord.Member):

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    target_id = str(usuario.id)

    if user_id not in tracker_db:
        tracker_db[user_id] = {}
    if guild_id not in tracker_db[user_id]:
        tracker_db[user_id][guild_id] = []

    if target_id not in tracker_db[user_id][guild_id]:
        tracker_db[user_id][guild_id].append(target_id)
        await save_data(tracker_db)

        await interaction.response.send_message(
            f"✅ Ahora rastreas a **{usuario.name}** en **{interaction.guild.name}**.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "ℹ️ Ya estabas rastreando a este usuario.",
            ephemeral=True
        )

# --- UNTRACKER (SLASH) ---
@bot.tree.command(name="untracker", description="Dejar de rastrear a un usuario")
@app_commands.describe(usuario="Usuario a dejar de rastrear")
async def untracker(interaction: discord.Interaction, usuario: discord.Member):

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    target_id = str(usuario.id)

    try:
        tracker_db[user_id][guild_id].remove(target_id)
        await save_data(tracker_db)

        await interaction.response.send_message(
            f"✅ Has dejado de rastrear a **{usuario.name}**.",
            ephemeral=True
        )
    except (KeyError, ValueError):
        await interaction.response.send_message(
            "❌ No estabas rastreando a este usuario.",
            ephemeral=True
        )


@bot.tree.command(name="tracker_list", description="Ver a quién estás rastreando")
async def tracker_list(interaction: discord.Interaction):

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    if user_id not in tracker_db or guild_id not in tracker_db[user_id]:
        await interaction.response.send_message(
            "ℹ️ No estás rastreando a nadie en este servidor.",
            ephemeral=True
        )
        return

    tracked_ids = tracker_db[user_id][guild_id]

    if not tracked_ids:
        await interaction.response.send_message(
            "ℹ️ No estás rastreando a nadie.",
            ephemeral=True
        )
        return

    nombres = []

    for user_id_tracked in tracked_ids:
        member = interaction.guild.get_member(int(user_id_tracked))

        if member:
            nombres.append(f"• {member.name}")
        else:
            nombres.append(f"• Usuario desconocido ({user_id_tracked})")

    lista = "\n".join(nombres)

    await interaction.response.send_message(
        f"📋 **Usuarios que estás rastreando:**\n{lista}",
        ephemeral=True
    )

@bot.tree.command(name="tracker_clear", description="Eliminar todos los usuarios que estás rastreando")
async def tracker_clear(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    if user_id not in tracker_db or guild_id not in tracker_db.get(user_id, {}):
        await interaction.response.send_message(
            "ℹ️ No tienes datos de rastreo para este servidor.",
            ephemeral=True
        )
        return

    del tracker_db[user_id][guild_id]

    if not tracker_db[user_id]:
        del tracker_db[user_id]

    await save_data(tracker_db)

    await interaction.response.send_message(
        "🧹 Has eliminado todos los usuarios que estabas rastreando en este servidor.",
        ephemeral=True
    )

@bot.tree.command(name="tracker_help", description="Ver todos los comandos disponibles")
async def help_command(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📖 Comandos disponibles",
        description="Lista de comandos del bot",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🔎 /tracker @usuario",
        value="Empieza a rastrear a un usuario.",
        inline=False
    )

    embed.add_field(
        name="❌ /untracker_user @usuario",
        value="Deja de rastrear a un usuario.",
        inline=False
    )

    embed.add_field(
        name="📋 /tracker_list",
        value="Muestra a quién estás rastreando.",
        inline=False
    )

    embed.add_field(
        name="🧹 /tracker_clear",
        value="Elimina todos los rastreos.",
        inline=False
    )

    embed.set_footer(text="Las respuestas son privadas | Notificaciones por MD")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# endregion

# --- NOTIFICACIÓN POR MD ---
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        member_id = str(member.id)
        guild_id = str(member.guild.id)

        for notifier_id, servers in tracker_db.items():
            if guild_id in servers and member_id in servers[guild_id]:
                
                user = bot.get_user(int(notifier_id))
                if user is None:
                    try:
                        user = await bot.fetch_user(int(notifier_id))
                    except:
                        continue 

                key = (notifier_id, member_id, guild_id)
                now = time.time()
                if key in last_notification and (now - last_notification[key] < COOLDOWN_SECONDS):
                    continue

                try:
                    canal_url = f"https://discord.com/channels/{member.guild.id}/{after.channel.id}"
                    mensaje = (
                        f"🔔 **Aviso de conexión**\n"
                        f"**{member.name}** entró a [{after.channel.name}]({canal_url}) en **{member.guild.name}**"
                    )
                    await user.send(mensaje)
                    last_notification[key] = now
                except discord.Forbidden:
                    pass

bot.run('TOKEN')
