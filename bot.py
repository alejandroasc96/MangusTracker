import discord
from discord.ext import commands
import json
import os

# ==========================================
# region CONFIG
# ==========================================

DATA_FILE = 'tracking_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True          # Necesario para obtener información de los miembros
intents.voice_states = True     # Necesario para rastrear cambios en canales de voz
intents.guilds = True           # Necesario para interactuar con los servidores

bot = commands.Bot(command_prefix='!', intents=intents)
tracker_db = load_data()        # Carga la base de datos de usuarios rastreados al iniciar

@bot.event
async def on_ready():
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
        save_data(tracker_db)

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
        save_data(tracker_db)

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

    save_data(tracker_db)

    await interaction.response.send_message(
        "🧹 Has eliminado todos los usuarios que estabas rastreando en este servidor.",
        ephemeral=True
    )

# endregion

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import nest_asyncio
import time
last_notification = {}  # {(notifier_id, tracked_user_id, guild_id): timestamp}
COOLDOWN_SECONDS = 60

nest_asyncio.apply()

# --- CONFIG ---
DATA_FILE = 'tracking_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
tracker_db = load_data()

# --- READY ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ Bot iniciado como {bot.user.name}')

# --- TRACKER (SLASH) ---
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
        save_data(tracker_db)

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
        save_data(tracker_db)

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

    # Comprobar si tiene datos
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

    # Verificamos primero si existe el usuario
    if user_id not in tracker_db or guild_id not in tracker_db.get(user_id, {}):
        await interaction.response.send_message(
            "ℹ️ No tienes datos de rastreo para este servidor.",
            ephemeral=True
        )
        return

    # Realizamos la eliminación de forma segura
    del tracker_db[user_id][guild_id]

    # Limpieza si el usuario no tiene más rastreos en otros servidores
    if not tracker_db[user_id]:
        del tracker_db[user_id]

    save_data(tracker_db)

    await interaction.response.send_message(
        "🧹 Has eliminado todos los usuarios que estabas rastreando en este servidor.",
        ephemeral=True
    )

@bot.tree.command(name="untracker_user", description="Dejar de rastrear a un usuario concreto")
@app_commands.describe(usuario="Usuario a dejar de rastrear")
async def untracker_user(interaction: discord.Interaction, usuario: discord.Member):

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    target_id = str(usuario.id)

    # Validación directa (más segura)
    if guild_id not in tracker_db.get(user_id, {}):
        await interaction.response.send_message(
            "❌ No estás rastreando a nadie en este servidor.",
            ephemeral=True
        )
        return

    user_guild_data = tracker_db[user_id][guild_id]

    if target_id not in user_guild_data:
        await interaction.response.send_message(
            f"❌ No estás rastreando a **{usuario.name}**.",
            ephemeral=True
        )
        return

    # Eliminación
    user_guild_data.remove(target_id)

    # Limpieza en cascada
    if not user_guild_data:
        del tracker_db[user_id][guild_id]
        if not tracker_db[user_id]:
            del tracker_db[user_id]

    save_data(tracker_db)

    await interaction.response.send_message(
        f"✅ Has dejado de rastrear a **{usuario.name}**.",
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

# --- EVENTO CANAL DE VOZ ---
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        member_id = str(member.id)
        guild_id = str(member.guild.id)

        canal_url = f"https://discord.com/channels/{member.guild.id}/{after.channel.id}"

        for notifier_id, servers in tracker_db.items():
            if guild_id in servers and member_id in servers[guild_id]:
                try:
                    user = await bot.fetch_user(int(notifier_id))

                    mensaje = (
                        f"🔔 **Aviso de conexión**\n"
                        f"**{member.name}** se ha conectado a "
                        f"[{after.channel.name}]({canal_url}) en **{member.guild.name}**"
                    )

                    key = (notifier_id, member_id, guild_id)
                    now = time.time()

                    if key in last_notification:
                        if now - last_notification[key] < COOLDOWN_SECONDS:
                            continue

                    last_notification[key] = now

                    await user.send(mensaje)

                except discord.Forbidden:
                    print(f"No se pudo enviar DM a {notifier_id}")
                except Exception as e:
                    print(f"Error: {e}")


bot.run('TU_TOKEN')
