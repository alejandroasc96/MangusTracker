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


bot.run('TU_TOKEN')
