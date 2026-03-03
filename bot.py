import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select
import os
import json

# =========================
# ENV
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN belum diset di environment variable")

BASE_FOLDER = "pricelist"
DATA_FILE = "data.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# LOAD / SAVE DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        data = {}
        save_data(data)
        return data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


DATA = load_data()

# =========================
# VIEW BUYER
# =========================

class GameView(View):
    def __init__(self):
        super().__init__(timeout=60)

        options = []
        for key, data in DATA.items():
            options.append(
                discord.SelectOption(
                    label=data["name"],
                    value=key
                )
            )

        self.add_item(GameSelect(options))


class GameSelect(Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Pilih game",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        game_key = self.values[0]

        await interaction.response.edit_message(
            content="Pilih produk:",
            view=ItemView(game_key)
        )


class ItemView(View):
    def __init__(self, game_key):
        super().__init__(timeout=60)

        options = []
        for item_key, item_name in DATA[game_key]["items"].items():
            options.append(
                discord.SelectOption(
                    label=item_name,
                    value=f"{game_key}|{item_key}"
                )
            )

        self.add_item(ItemSelect(options))


class ItemSelect(Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Pilih pricelist",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        game_key, item_key = self.values[0].split("|")

        folder = os.path.join(BASE_FOLDER, "game", game_key, item_key)

        if not os.path.exists(folder):
            await interaction.response.send_message(
                "❌ Pricelist belum tersedia.",
                ephemeral=True
            )
            return

        files = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".png"):
                files.append(discord.File(os.path.join(folder, name)))

        if not files:
            await interaction.response.send_message(
                "❌ Pricelist belum tersedia.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(files=files, ephemeral=True)


# =========================
# AUTOCOMPLETE
# =========================

async def game_autocomplete(interaction: discord.Interaction, current: str):
    result = []
    for k, v in DATA.items():
        if current.lower() in v["name"].lower():
            result.append(app_commands.Choice(name=v["name"], value=k))
    return result[:25]


async def produk_autocomplete(interaction: discord.Interaction, current: str):
    result = []
    for gk, gv in DATA.items():
        for ik, iv in gv["items"].items():
            label = f"{gv['name']} - {iv}"
            value = f"{gk}|{ik}"
            if current.lower() in label.lower():
                result.append(app_commands.Choice(name=label, value=value))
    return result[:25]


# =========================
# SLASH BUYER
# =========================

@bot.tree.command(name="cekpricelist", description="Cek pricelist game")
async def cekpricelist(interaction: discord.Interaction):
    if not DATA:
        await interaction.response.send_message(
            "Belum ada game yang tersedia.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Pilih game:",
        view=GameView(),
        ephemeral=True
    )


# =========================
# ADMIN - ADD GAME
# =========================

@bot.tree.command(name="admin_add_game", description="Admin - tambah game baru")
async def admin_add_game(
    interaction: discord.Interaction,
    game_key: str,
    game_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    key = game_key.lower().replace(" ", "")

    if key in DATA:
        await interaction.response.send_message("❌ Game key sudah ada.", ephemeral=True)
        return

    DATA[key] = {
        "name": game_name,
        "items": {}
    }

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Game **{game_name}** berhasil ditambahkan.",
        ephemeral=True
    )


# =========================
# ADMIN - RENAME GAME
# =========================

@bot.tree.command(name="admin_rename_game", description="Admin - ganti nama game")
@app_commands.autocomplete(game=game_autocomplete)
async def admin_rename_game(
    interaction: discord.Interaction,
    game: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if game not in DATA:
        await interaction.response.send_message("❌ Game tidak ditemukan.", ephemeral=True)
        return

    DATA[game]["name"] = new_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Nama game berhasil diubah.",
        ephemeral=True
    )


# =========================
# ADMIN - DELETE GAME
# =========================

@bot.tree.command(name="admin_delete_game", description="Admin - hapus game")
@app_commands.autocomplete(game=game_autocomplete)
async def admin_delete_game(
    interaction: discord.Interaction,
    game: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if game not in DATA:
        await interaction.response.send_message("❌ Game tidak ditemukan.", ephemeral=True)
        return

    base_game_folder = os.path.join(BASE_FOLDER, "game", game)
    if os.path.exists(base_game_folder):
        for root, dirs, files in os.walk(base_game_folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(base_game_folder)

    del DATA[game]
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Game berhasil dihapus.",
        ephemeral=True
    )


# =========================
# ADMIN - ADD ITEM
# =========================

@bot.tree.command(name="admin_add_item", description="Admin - tambah produk / kategori")
@app_commands.autocomplete(game=game_autocomplete)
async def admin_add_item(
    interaction: discord.Interaction,
    game: str,
    item_key: str,
    item_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if game not in DATA:
        await interaction.response.send_message("❌ Game tidak ada.", ephemeral=True)
        return

    ikey = item_key.lower().replace(" ", "")

    DATA[game]["items"][ikey] = item_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Produk berhasil ditambahkan.",
        ephemeral=True
    )


# =========================
# ADMIN - RENAME ITEM
# =========================

@bot.tree.command(name="admin_rename_item", description="Admin - ganti nama produk")
@app_commands.autocomplete(produk=produk_autocomplete)
async def admin_rename_item(
    interaction: discord.Interaction,
    produk: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    game_key, item_key = produk.split("|")

    if game_key not in DATA or item_key not in DATA[game_key]["items"]:
        await interaction.response.send_message("❌ Produk tidak ditemukan.", ephemeral=True)
        return

    DATA[game_key]["items"][item_key] = new_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Nama produk berhasil diubah.",
        ephemeral=True
    )


# =========================
# ADMIN - DELETE ITEM
# =========================

@bot.tree.command(name="admin_delete_item", description="Admin - hapus produk / kategori")
@app_commands.autocomplete(produk=produk_autocomplete)
async def admin_delete_item(
    interaction: discord.Interaction,
    produk: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    game_key, item_key = produk.split("|")

    if game_key not in DATA or item_key not in DATA[game_key]["items"]:
        await interaction.response.send_message("❌ Produk tidak ditemukan.", ephemeral=True)
        return

    del DATA[game_key]["items"][item_key]
    save_data(DATA)

    folder = os.path.join(BASE_FOLDER, "game", game_key, item_key)
    if os.path.exists(folder):
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))
        os.rmdir(folder)

    await interaction.response.send_message(
        "✅ Produk berhasil dihapus.",
        ephemeral=True
    )


# =========================
# ADMIN - UPDATE IMAGE
# =========================

@bot.tree.command(name="update_pricelist", description="Admin - update gambar pricelist")
@app_commands.autocomplete(produk=produk_autocomplete)
async def update_pricelist(
    interaction: discord.Interaction,
    produk: str,
    image1: discord.Attachment,
    image2: discord.Attachment | None = None,
    image3: discord.Attachment | None = None,
    image4: discord.Attachment | None = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    game_key, item_key = produk.split("|")

    folder = os.path.join(BASE_FOLDER, "game", game_key, item_key)
    os.makedirs(folder, exist_ok=True)

    for f in os.listdir(folder):
        if f.lower().endswith(".png"):
            os.remove(os.path.join(folder, f))

    images = [image1, image2, image3, image4]

    i = 1
    for img in images:
        if img:
            await img.save(os.path.join(folder, f"{i}.png"))
            i += 1

    await interaction.followup.send(
        "✅ Pricelist berhasil diperbarui.",
        ephemeral=True
    )


# =========================
# READY
# =========================

@bot.event
async def on_ready():
    global DATA
    DATA = load_data()
    await bot.tree.sync()
    print(f"Bot siap sebagai {bot.user}")


bot.run(TOKEN)
