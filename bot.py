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

class ItemViewLevel1(View):
    def __init__(self):
        super().__init__(timeout=60)

        options = []
        for key, data in DATA.items():
            options.append(
                discord.SelectOption(
                    label=data.get("name", key),
                    value=key
                )
            )

        if options:
            self.add_item(ItemSelectLevel1(options))


class ItemSelectLevel1(Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Pilih Item",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        item_key = self.values[0]

        if not DATA.get(item_key, {}).get("items"):
            await interaction.response.edit_message(
                content="❌ Produk untuk item ini belum tersedia.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Pilih produk:",
            view=ItemViewLevel2(item_key)
        )


class ItemViewLevel2(View):
    def __init__(self, item_key):
        super().__init__(timeout=60)

        options = []
        for product_key, product_name in DATA[item_key]["items"].items():
            options.append(
                discord.SelectOption(
                    label=product_name,
                    value=f"{item_key}|{product_key}"
                )
            )

        if options:
            self.add_item(ItemSelectLevel2(options))


class ItemSelectLevel2(Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Pilih produk",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        item_key, product_key = self.values[0].split("|")

        folder = os.path.join(BASE_FOLDER, "game", item_key, product_key)

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

async def item_autocomplete(interaction: discord.Interaction, current: str):
    result = []
    for k, v in DATA.items():
        if current.lower() in v.get("name", "").lower():
            result.append(app_commands.Choice(name=v.get("name", k), value=k))
    return result[:25]


async def product_autocomplete(interaction: discord.Interaction, current: str):
    result = []
    for item_key, item_data in DATA.items():
        for product_key, product_name in item_data.get("items", {}).items():
            label = f"{item_data.get('name', item_key)} - {product_name}"
            value = f"{item_key}|{product_key}"
            if current.lower() in label.lower():
                result.append(app_commands.Choice(name=label, value=value))
    return result[:25]


# =========================
# SLASH BUYER
# =========================

@bot.tree.command(name="cekpricelist", description="Cek pricelist item")
async def cekpricelist(interaction: discord.Interaction):
    if not DATA:
        await interaction.response.send_message(
            "Belum ada item yang tersedia.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Pilih Item:",
        view=ItemViewLevel1(),
        ephemeral=True
    )


# =====================================================
# GROUP COMMANDS
# /add
# /rename
# /hapus
# =====================================================

add_group = app_commands.Group(name="add", description="Tambah data")
rename_group = app_commands.Group(name="rename", description="Ubah nama data")
hapus_group = app_commands.Group(name="hapus", description="Hapus data")


# =========================
# /add item
# =========================

@add_group.command(name="item", description="Tambah item baru")
async def add_item(
    interaction: discord.Interaction,
    item_key: str,
    item_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    key = item_key.lower().replace(" ", "")

    if key in DATA:
        await interaction.response.send_message("❌ Item key sudah ada.", ephemeral=True)
        return

    DATA[key] = {
        "name": item_name,
        "items": {}
    }

    save_data(DATA)

    await interaction.response.send_message(
        f"✅ Item **{item_name}** berhasil ditambahkan.",
        ephemeral=True
    )


# =========================
# /add produk
# =========================

@add_group.command(name="produk", description="Tambah produk")
@app_commands.autocomplete(item=item_autocomplete)
async def add_produk(
    interaction: discord.Interaction,
    item: str,
    product_key: str,
    product_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if item not in DATA:
        await interaction.response.send_message("❌ Item tidak ditemukan.", ephemeral=True)
        return

    pkey = product_key.lower().replace(" ", "")

    DATA[item]["items"][pkey] = product_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Produk berhasil ditambahkan.",
        ephemeral=True
    )


# =========================
# /rename item
# =========================

@rename_group.command(name="item", description="Ganti nama item")
@app_commands.autocomplete(item=item_autocomplete)
async def rename_item(
    interaction: discord.Interaction,
    item: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if item not in DATA:
        await interaction.response.send_message("❌ Item tidak ditemukan.", ephemeral=True)
        return

    DATA[item]["name"] = new_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Nama item berhasil diubah.",
        ephemeral=True
    )


# =========================
# /rename produk
# =========================

@rename_group.command(name="produk", description="Ganti nama produk")
@app_commands.autocomplete(product=product_autocomplete)
async def rename_produk(
    interaction: discord.Interaction,
    product: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    item_key, product_key = product.split("|")

    if item_key not in DATA or product_key not in DATA[item_key]["items"]:
        await interaction.response.send_message("❌ Produk tidak ditemukan.", ephemeral=True)
        return

    DATA[item_key]["items"][product_key] = new_name
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Nama produk berhasil diubah.",
        ephemeral=True
    )


# =========================
# /hapus item
# =========================

@hapus_group.command(name="item", description="Hapus item")
@app_commands.autocomplete(item=item_autocomplete)
async def hapus_item(
    interaction: discord.Interaction,
    item: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    if item not in DATA:
        await interaction.response.send_message("❌ Item tidak ditemukan.", ephemeral=True)
        return

    base_folder = os.path.join(BASE_FOLDER, "game", item)
    if os.path.exists(base_folder):
        for root, dirs, files in os.walk(base_folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(base_folder)

    del DATA[item]
    save_data(DATA)

    await interaction.response.send_message(
        "✅ Item berhasil dihapus.",
        ephemeral=True
    )


# =========================
# /hapus produk
# =========================

@hapus_group.command(name="produk", description="Hapus produk")
@app_commands.autocomplete(product=product_autocomplete)
async def hapus_produk(
    interaction: discord.Interaction,
    product: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    item_key, product_key = product.split("|")

    if item_key not in DATA or product_key not in DATA[item_key]["items"]:
        await interaction.response.send_message("❌ Produk tidak ditemukan.", ephemeral=True)
        return

    del DATA[item_key]["items"][product_key]
    save_data(DATA)

    folder = os.path.join(BASE_FOLDER, "game", item_key, product_key)
    if os.path.exists(folder):
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))
        os.rmdir(folder)

    await interaction.response.send_message(
        "✅ Produk berhasil dihapus.",
        ephemeral=True
    )


# =========================
# UPDATE PRICELIST
# =========================

@bot.tree.command(name="update_pricelist", description="Admin - update gambar pricelist")
@app_commands.autocomplete(product=product_autocomplete)
async def update_pricelist(
    interaction: discord.Interaction,
    product: str,
    image1: discord.Attachment,
    image2: discord.Attachment | None = None,
    image3: discord.Attachment | None = None,
    image4: discord.Attachment | None = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Khusus admin.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    item_key, product_key = product.split("|")

    folder = os.path.join(BASE_FOLDER, "game", item_key, product_key)
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

    bot.tree.add_command(add_group)
    bot.tree.add_command(rename_group)
    bot.tree.add_command(hapus_group)

    await bot.tree.sync()
    print(f"Bot siap sebagai {bot.user}")


bot.run(TOKEN)
