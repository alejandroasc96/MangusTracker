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

# endregion

bot.run('TU_TOKEN')
