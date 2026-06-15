import discord
import time
import json
import os
import uuid
import asyncio
from discord import app_commands
from discord.ext import commands
from typing import Optional

DIVORCE_COOLDOWN_SECONDS = 3600

COMMON_RING = "<:common_ring:1513976685081657444>"
UNCOMMON_RING = "<:uncommon_ring:1513977443499642930>"
RARE_RING = "<:rare_ring:1513977524911214773>"
EPIC_RING = "<:epic_ring:1513977666594934874>"
LEGENDARY_RING = "<:legendary_ring:1513977751596695723>"
DIVINE_RING = "<:divine_ring:1513977840620540067>"
UGUISUCOIN = "<:uguisucoinno:1513628345156370523>"

RINGS = {
    "common":    {"name": "Common Ring",    "emoji": COMMON_RING, "tier": "Common",    "color": 0xAAAAAA, "price": 1_000},
    "uncommon":  {"name": "Uncommon Ring",  "emoji": UNCOMMON_RING, "tier": "Uncommon",  "color": 0x2ECC71, "price": 10_000},
    "rare":      {"name": "Rare Ring",      "emoji": RARE_RING, "tier": "Rare",      "color": 0x3498DB, "price": 100_000},
    "epic":      {"name": "Epic Ring",      "emoji": EPIC_RING, "tier": "Epic",      "color": 0x9B59B6, "price": 1_000_000},
    "legendary": {"name": "Legendary Ring", "emoji": LEGENDARY_RING, "tier": "Legendary", "color": 0xE67E22, "price": 10_000_000},
    "divine":    {"name": "Divine Ring",   "emoji": DIVINE_RING, "tier": "Divine",    "color": 0xF1C40F,"price": 100_000_000},
}

# ── Box config ────────────────────────────────────────────────────────────────
BOX_PRICE = 50_000
BOX_EMOJI = "<:openbox:1513969866397188166>"
BOX_OPEN_EMOJI = "<a:boxopenanimation:1513969466814370022>"
BOX_CLOSE = "<:boxclose:1513969806376829191>"

ITEM_POOL = [
    {
        "id": "deco_001",
        "name": "Starlight Ring Frame",
        "emoji": "⭐",
        "type": "decoration",
        "rarity": "rare",
        "weight": 8,
        "color": 0x3498DB,
        "description": "A sparkling star border around your avatar circle.",
    },
    {
        "id": "deco_002",
        "name": "Divine Halo Frame",
        "emoji": "✨",
        "type": "decoration",
        "rarity": "divine",
        "weight": 1,
        "color": 0xF1C40F,
        "description": "A radiant golden halo — extremely rare.",
    },
    {
        "id": "deco_003",
        "name": "Neon Pulse Frame",
        "emoji": "💜",
        "type": "decoration",
        "rarity": "epic",
        "weight": 4,
        "color": 0x9B59B6,
        "description": "A glowing purple neon ring around your avatar.",
    },
    {
        "id": "deco_premium",
        "name": "Premium Deco frame",
        "emoji": "👑",
        "type": "decoration",
        "rarity": "Premium",
        "weight": 1,
        "color": 0xF1C40F,
        "description": "Premium users deco",
    },
]

RARITY_COLORS = {
    "common":    0xAAAAAA,
    "uncommon":  0x2ECC71,
    "rare":      0x3498DB,
    "epic":      0x9B59B6,
    "legendary": 0xE67E22,
    "divine":    0xF1C40F,
}

ITEMS_PATH = "users.items.json"


def load_items() -> dict:
    if os.path.exists(ITEMS_PATH):
        with open(ITEMS_PATH, "r") as f:
            return json.load(f)
    return {}


def save_items(data: dict):
    with open(ITEMS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def give_item(uid: int, item: dict) -> str | tuple:
    data = load_items()
    key  = str(uid)
    if key not in data:
        data[key] = []

    if item["type"] == "decoration":
        already_has = any(i["item_id"] == item["id"] for i in data[key])
        if already_has:
            return ("duplicate", 30000)

    code = str(len(data[key]) + 1).zfill(3)
    data[key].append({
        "code":        code,
        "item_id":     item["id"],
        "name":        item["name"],
        "emoji":       item["emoji"],
        "type":        item["type"],
        "rarity":      item["rarity"],
        "color":       item["color"],
        "description": item["description"],
        "uuid":        str(uuid.uuid4()),
    })
    save_items(data)
    return code


def get_user_items(uid: int) -> list:
    data = load_items()
    return data.get(str(uid), [])


def get_active_deco(uid: int) -> Optional[dict]:
    data = load_items()
    key  = str(uid)
    if key not in data:
        return None
    for item in data[key]:
        if item.get("active_deco"):
            return item
    return None


def set_active_deco(uid: int, code: str) -> bool:
    data = load_items()
    key  = str(uid)
    if key not in data:
        return False
    found = False
    for item in data[key]:
        item["active_deco"] = (item["code"] == code and item["type"] == "decoration")
        if item["code"] == code and item["type"] == "decoration":
            found = True
    save_items(data)
    return found


def roll_item() -> dict:
    import random
    pool    = [i for i in ITEM_POOL if i["id"] != "deco_premium"]
    weights = [i["weight"] for i in pool]
    return random.choices(pool, weights=weights, k=1)[0]


# ── Shop pages ────────────────────────────────────────────────────────────────

def build_shop_page1() -> discord.Embed:
    embed = discord.Embed(
        title="💍 Ring Shop  —  Page 1 / 2",
        description="Buy a ring before you propose with `/marry`!\nUse `.buy <tier>` to purchase.\n\u200b",
        color=discord.Color(0x9B37FF)
    )
    for key in ["common", "uncommon", "rare", "epic", "legendary", "divine"]:
        ring = RINGS[key]
        embed.add_field(
            name=f"{ring['emoji']} {ring['name']}",
            value=f"**Tier:** {ring['tier']}\n**Price:** {UGUISUCOIN} {ring['price']:,}",
            inline=True
        )
    embed.set_footer(text="◀ Page 1 of 2  |  ▶ to see Boxes")
    return embed


def build_shop_page2() -> discord.Embed:
    embed = discord.Embed(
        title=f"{BOX_CLOSE} Box Shop  —  Page 2 / 2",
        description=(
            f"Open boxes to get random items — decorations, rings, and more!\n\n"
            f"**Price:** {UGUISUCOIN} {BOX_PRICE:,} per box\n"
            f"**Command:** `.buybox <amount>` to buy boxes\n"
            f"**Command:** `.openbox <amount | all>` to open them\n\u200b"
        ),
        color=discord.Color(0x9B37FF)
    )
    embed.add_field(
        name=f"{BOX_CLOSE} Mystery Box",
        value=(
            "Contains a random item from the pool.\n"
            "Possible drops:\n"
            + "\n".join(
                f"{i['emoji']} **{i['name']}** — `{i['rarity'].capitalize()}`"
                for i in ITEM_POOL if i["id"] != "deco_premium"
            )
        ),
        inline=False
    )
    embed.set_footer(text="◀ back to Rings  |  Page 2 of 2")
    return embed


class ShopView(discord.ui.View):
    def __init__(self, page: int = 1, author: discord.User = None):
        super().__init__(timeout=60)
        self.page = page
        self.author = author
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        if self.page == 2:
            prev = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, custom_id="prev")
            prev.callback = self.go_prev
            self.add_item(prev)
        if self.page == 1:
            nxt = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, custom_id="next")
            nxt.callback = self.go_next
            self.add_item(nxt)

    async def go_next(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't your shop!", ephemeral=True)
            return
        self.page = 2
        self._update_buttons()
        await interaction.response.edit_message(embed=build_shop_page2(), view=self)

    async def go_prev(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't your shop!", ephemeral=True)
            return
        self.page = 1
        self._update_buttons()
        await interaction.response.edit_message(embed=build_shop_page1(), view=self)


class MarriageSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _leveling(self):
        return self.bot.cogs.get("LevelingSystem")

    # ── Shop ──────────────────────────────────────────────────────────────────

    @commands.command(name="shop")
    async def cmd_shop(self, ctx: commands.Context):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        await ctx.send(embed=build_shop_page1(), view=ShopView(page=1, author=ctx.author))

    @commands.command(name="buy")
    async def cmd_buy(self, ctx: commands.Context, tier: str):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        if not leveling:
            await ctx.send("❌ Leveling system not loaded!")
            return

        tier = tier.lower().strip()
        if tier not in RINGS:
            await ctx.send(f"❌ Unknown ring tier. Valid tiers: `{', '.join(RINGS.keys())}`")
            return

        uid = ctx.author.id
        leveling._ensure_user(uid)

        if leveling.user_rings.get(uid):
            await ctx.send("❌ You already own a ring! Use it with `/marry` or you'll lose it on `/divorce`.")
            return

        cooldown_until = leveling.divorce_cooldowns.get(uid, 0)
        if time.time() < cooldown_until:
            remaining  = int(cooldown_until - time.time())
            mins, secs = remaining // 60, remaining % 60
            await ctx.send(f"❌ You're on a divorce cooldown. You can buy a new ring in **{mins}m {secs}s**.")
            return

        ring  = RINGS[tier]
        price = ring["price"]

        if leveling.user_coins[uid] < price:
            shortage = price - leveling.user_coins[uid]
            await ctx.send(
                f"❌ Not enough coins! You need **{UGUISUCOIN} {price:,}** but only have **{UGUISUCOIN} {leveling.user_coins[uid]:,}**.\n"
                f"You're short by **{UGUISUCOIN} {shortage:,}**."
            )
            return

        embed = discord.Embed(
            title=f"{ring['emoji']} Confirm Purchase",
            description=(
                f"Are you sure you want to buy the **{ring['name']}**?\n\n"
                f"**Cost:** {UGUISUCOIN} {price:,}\n"
                f"**Your balance:** {UGUISUCOIN} {leveling.user_coins[uid]:,}\n"
                f"**After purchase:** {UGUISUCOIN} {leveling.user_coins[uid] - price:,}"
            ),
            color=discord.Color(ring["color"])
        )

        yes_btn = discord.ui.Button(label="Buy", style=discord.ButtonStyle.success, emoji="✅")
        no_btn  = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")

        async def yes_callback(inter: discord.Interaction):
            if inter.user != ctx.author:
                await inter.response.send_message("This isn't your purchase!", ephemeral=True)
                return
            leveling.user_coins[uid] -= price
            leveling.user_rings[uid]  = tier
            leveling.save_data()
            await inter.response.edit_message(
                embed=discord.Embed(
                    title=f"{ring['emoji']} Purchase Successful!",
                    description=(
                        f"You bought the **{ring['name']}**!\n"
                        f"Use `/marry @user` to propose with it.\n\n"
                        f"**New balance:** {UGUISUCOIN} {leveling.user_coins[uid]:,}"
                    ),
                    color=discord.Color(ring["color"])
                ),
                view=None
            )

        async def no_callback(inter: discord.Interaction):
            if inter.user != ctx.author:
                await inter.response.send_message("This isn't your purchase!", ephemeral=True)
                return
            await inter.response.edit_message(
                embed=discord.Embed(description="❌ Purchase cancelled.", color=discord.Color.red()),
                view=None
            )

        yes_btn.callback = yes_callback
        no_btn.callback  = no_callback
        view = discord.ui.View(timeout=30)
        view.add_item(yes_btn)
        view.add_item(no_btn)
        await ctx.send(embed=embed, view=view)

    # ── Boxes ─────────────────────────────────────────────────────────────────

    @commands.command(name="buybox")
    async def cmd_buybox(self, ctx: commands.Context, amount: int = 1):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        if not leveling:
            await ctx.send("❌ Leveling system not loaded!")
            return

        if amount < 1:
            await ctx.send("❌ Amount must be at least 1.")
            return

        uid   = ctx.author.id
        leveling._ensure_user(uid)
        total = BOX_PRICE * amount

        if leveling.user_coins[uid] < total:
            await ctx.send(
                f"❌ Not enough coins! **{amount}x {BOX_CLOSE} Box** costs **{UGUISUCOIN} {total:,}** "
                f"but you only have **{UGUISUCOIN} {leveling.user_coins[uid]:,}**."
            )
            return

        leveling.user_coins[uid] -= total

        if not hasattr(leveling, "user_boxes"):
            leveling.user_boxes = {}
        leveling.user_boxes[uid] = leveling.user_boxes.get(uid, 0) + amount
        leveling.save_data()

        await ctx.send(
            embed=discord.Embed(
                title=f"{BOX_CLOSE} Boxes Purchased!",
                description=(
                    f"You bought **{amount}x {BOX_CLOSE} Mystery Box**!\n"
                    f"Use `.openbox <amount>` or `.openbox all` to open them.\n\n"
                    f"**You now have:** {leveling.user_boxes[uid]}x {BOX_CLOSE}\n"
                    f"**New balance:** {UGUISUCOIN} {leveling.user_coins[uid]:,}"
                ),
                color=discord.Color(0x9B37FF)
            )
        )

    @commands.command(name="openbox")
    async def cmd_openbox(self, ctx: commands.Context, amount: str = "1"):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        if not leveling:
            await ctx.send("❌ Leveling system not loaded!")
            return

        uid = ctx.author.id
        leveling._ensure_user(uid)

        if not hasattr(leveling, "user_boxes"):
            leveling.user_boxes = {}

        owned = leveling.user_boxes.get(uid, 0)
        if owned == 0:
            await ctx.send(f"❌ You don't have any boxes! Buy some with `.buybox <amount>`.")
            return

        if amount.lower() == "all":
            count = owned
        else:
            try:
                count = int(amount)
            except ValueError:
                await ctx.send("❌ Use `.openbox <number>` or `.openbox all`.")
                return

        count = max(1, min(count, owned))

        if count > 50:
            await ctx.send("⚠️ To prevent lag and errors, you can only open up to **50 boxes** at a time!")
            return

        data = load_items()
        key = str(uid)
        if key not in data:
            data[key] = []

        results = []
        total_refund = 0

        for _ in range(count):
            item = roll_item()

            if item["type"] == "decoration":
                already_has = any(i["item_id"] == item["id"] for i in data[key])
                if already_has:
                    total_refund += 30000
                    results.append((item, None, 30000))
                    continue

            code = str(len(data[key]) + 1).zfill(3)
            data[key].append({
                "code":        code,
                "item_id":     item["id"],
                "name":        item["name"],
                "emoji":       item["emoji"],
                "type":        item["type"],
                "rarity":      item["rarity"],
                "color":       item["color"],
                "description": item["description"],
                "uuid":        str(uuid.uuid4()),
            })

            if item["type"] == "ring" and not leveling.user_rings.get(uid):
                ring_map = {"ring_common_box": "common", "ring_rare_box": "rare"}
                ring_key = ring_map.get(item["id"])
                if ring_key:
                    leveling.user_rings[uid] = ring_key

            results.append((item, code, None))

        if total_refund:
            leveling.user_coins[uid] = leveling.user_coins.get(uid, 0) + total_refund

        save_items(data)
        leveling.user_boxes[uid] = owned - count
        leveling.save_data()

        name = ctx.author.display_name

        if count == 1:
            item, code, refund = results[0]
            opening_embed = discord.Embed(
                title=f"{BOX_EMOJI} Opening a Box...",
                description=f"**{name}** is opening **1 box**...\n\nand they get... {BOX_OPEN_EMOJI}",
                color=discord.Color(0x9B37FF)
            )
            msg = await ctx.send(embed=opening_embed)
            await asyncio.sleep(2.5)

            if refund:
                result_embed = discord.Embed(
                    title=f"{BOX_EMOJI} Duplicate!",
                    description=f"You already own **{item['emoji']} {item['name']}**!\nAuto-sold for {UGUISUCOIN} **30,000**.",
                    color=discord.Color(0xAAAAAA)
                )
            else:
                result_embed = discord.Embed(
                    title=f"{BOX_EMOJI} {name} opened a box!",
                    description=f"They got **{item['emoji']} {item['name']}**! `[{code}]`",
                    color=discord.Color(item["color"])
                )
                result_embed.add_field(name="Rarity", value=item["rarity"].capitalize(), inline=True)
                result_embed.add_field(name="Type",   value=item["type"].capitalize(),   inline=True)
                result_embed.add_field(name="Code",   value=f"`{code}`",                 inline=True)
            result_embed.set_footer(text=f"Boxes remaining: {leveling.user_boxes[uid]}")
            await msg.edit(embed=result_embed)

        else:
            opening_embed = discord.Embed(
                title=f"{BOX_EMOJI} Opening {count} Boxes...",
                description=f"**{name}** is opening **{count} boxes**...\n\nand they get... {BOX_OPEN_EMOJI}",
                color=discord.Color(0x9B37FF)
            )
            msg = await ctx.send(embed=opening_embed)
            await asyncio.sleep(2.5)

            lines = "\n".join(
                f"{item['emoji']} **{item['name']}** ~~duplicate~~ → {UGUISUCOIN} **30,000**" if refund
                else f"{item['emoji']} **{item['name']}** `[{code}]` — *{item['rarity'].capitalize()}*"
                for item, code, refund in results
            )
            result_embed = discord.Embed(
                title=f"{BOX_EMOJI} {name} opened {count} boxes!",
                description=lines,
                color=discord.Color(0x9B37FF)
            )
            if total_refund:
                result_embed.add_field(name="Duplicate Refunds", value=f"{UGUISUCOIN} **+{total_refund:,}**", inline=False)
            result_embed.set_footer(text=f"Boxes remaining: {leveling.user_boxes[uid]}")
            await msg.edit(embed=result_embed)

    # ── Decorations ───────────────────────────────────────────────────────────

    @commands.command(name="choosedeco")
    async def cmd_choosedeco(self, ctx: commands.Context):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        uid   = ctx.author.id
        items = [i for i in get_user_items(uid) if i["type"] == "decoration"]

        if not items:
            await ctx.send("❌ You don't own any decorations! Open boxes with `.openbox` to get some.")
            return

        active = get_active_deco(uid)
        desc   = "Your decorations — click a button to equip one.\n\u200b\n"
        for i in items:
            equipped = " ✅ **equipped**" if (active and active["code"] == i["code"]) else ""
            desc += f"{i['emoji']} **{i['name']}** `[{i['code']}]` — *{i['rarity'].capitalize()}*{equipped}\n"

        embed = discord.Embed(
            title="🎨 Your Decorations",
            description=desc,
            color=discord.Color(0x9B37FF)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        view = discord.ui.View(timeout=60)
        for item in items[:25]:
            btn = discord.ui.Button(
                label=f"{item['name']} [{item['code']}]",
                style=discord.ButtonStyle.primary if (active and active["code"] == item["code"]) else discord.ButtonStyle.secondary,
                custom_id=item["code"]
            )
            def make_callback(code=item["code"], item_data=item):
                async def callback(inter: discord.Interaction):
                    if inter.user != ctx.author:
                        await inter.response.send_message("These aren't your decorations!", ephemeral=True)
                        return
                    set_active_deco(uid, code)
                    await inter.response.send_message(
                        embed=discord.Embed(
                            title=f"{item_data['emoji']} Decoration Equipped!",
                            description=f"**{item_data['name']}** `[{code}]` is now active on your rank card.",
                            color=discord.Color(item_data["color"])
                        ),
                        ephemeral=True
                    )
                return callback
            btn.callback = make_callback()
            view.add_item(btn)

        await ctx.send(embed=embed, view=view)

    @commands.command(name="myring")
    async def cmd_myring(self, ctx: commands.Context):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        if not leveling:
            await ctx.send("❌ Leveling system not loaded!")
            return
        ring_key = leveling.user_rings.get(ctx.author.id)
        if not ring_key:
            await ctx.send("💍 You don't own a ring. Buy one with `.shop` then `.buy <tier>`!")
            return
        ring  = RINGS[ring_key]
        embed = discord.Embed(
            title=f"{ring['emoji']} Your Ring",
            description=f"**{ring['name']}** ({ring['tier']} tier)",
            color=discord.Color(ring["color"])
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ── Marriage ──────────────────────────────────────────────────────────────

    @app_commands.command(name="marry", description="Propose to someone with your ring!")
    @app_commands.describe(member="The person you want to propose to")
    async def cmd_marry(self, interaction: discord.Interaction, member: discord.Member):
        leveling = self._leveling()
        if not await leveling._check_registered_interaction(interaction): return
        if not leveling:
            await interaction.response.send_message("❌ Leveling system not loaded!", ephemeral=True)
            return

        uid        = interaction.user.id
        target_uid = member.id

        if uid == target_uid:
            await interaction.response.send_message("❌ You can't marry yourself!", ephemeral=True)
            return
        if leveling._is_married(uid):
            await interaction.response.send_message("❌ You're already married! Use `/divorce` first.", ephemeral=True)
            return
        if leveling._is_married(target_uid):
            await interaction.response.send_message(f"❌ **{member.display_name}** is already married!", ephemeral=True)
            return

        ring_key = leveling.user_rings.get(uid)
        if not ring_key:
            await interaction.response.send_message(
                "❌ You need a ring to propose! Buy one with `.shop` then `.buy <tier>`.", ephemeral=True
            )
            return

        cooldown_until = leveling.divorce_cooldowns.get(uid, 0)
        if time.time() < cooldown_until:
            remaining  = int(cooldown_until - time.time())
            mins, secs = remaining // 60, remaining % 60
            await interaction.response.send_message(
                f"❌ You're on a divorce cooldown. You can remarry in **{mins}m {secs}s**.", ephemeral=True
            )
            return

        ring        = RINGS[ring_key]
        accept_btn  = discord.ui.Button(label="Accept 💍", style=discord.ButtonStyle.success)
        decline_btn = discord.ui.Button(label="Decline 💔", style=discord.ButtonStyle.danger)

        proposal_embed = discord.Embed(
            title="💍 Marriage Proposal!",
            description=(
                f"{interaction.user.mention} is proposing to {member.mention}!\n\n"
                f"They're offering a **{ring['emoji']} {ring['name']}** ({ring['tier']} tier)\n\n"
                f"{member.mention}, do you accept?"
            ),
            color=discord.Color(ring["color"])
        )
        proposal_embed.set_footer(text="This proposal expires in 60 seconds.")

        async def accept_callback(inter: discord.Interaction):
            if inter.user != member:
                await inter.response.send_message("This proposal isn't for you!", ephemeral=True)
                return
            if leveling._is_married(uid) or leveling._is_married(target_uid):
                await inter.response.edit_message(
                    embed=discord.Embed(description="❌ One of you is already married!", color=discord.Color.red()),
                    view=None
                )
                return
            leveling.marriages[uid]        = target_uid
            leveling.marriages[target_uid] = uid
            leveling.user_rings.pop(uid, None)
            leveling.marriage_rings[uid]   = ring_key
            leveling.save_data()
            await inter.response.edit_message(
                embed=discord.Embed(
                    title="💒 You're Married!",
                    description=(
                        f"🎉 {interaction.user.mention} and {member.mention} are now married!\n\n"
                        f"Sealed with a **{ring['emoji']} {ring['name']}**.\n"
                        f"Use `/divorce` if things go south — but you'll lose the ring forever."
                    ),
                    color=discord.Color(ring["color"])
                ),
                view=None
            )

        async def decline_callback(inter: discord.Interaction):
            if inter.user != member:
                await inter.response.send_message("This proposal isn't for you!", ephemeral=True)
                return
            await inter.response.edit_message(
                embed=discord.Embed(
                    title="💔 Proposal Declined",
                    description=f"{member.mention} declined the proposal. The ring has been returned.",
                    color=discord.Color.red()
                ),
                view=None
            )

        accept_btn.callback  = accept_callback
        decline_btn.callback = decline_callback
        view = discord.ui.View(timeout=60)
        view.add_item(accept_btn)
        view.add_item(decline_btn)
        await interaction.response.send_message(embed=proposal_embed, view=view)

    @app_commands.command(name="divorce", description="Divorce your partner.")
    async def cmd_divorce(self, interaction: discord.Interaction):
        leveling = self._leveling()
        if not await leveling._check_registered_interaction(interaction): return
        if not leveling:
            await interaction.response.send_message("❌ Leveling system not loaded!", ephemeral=True)
            return

        uid = interaction.user.id
        if not leveling._is_married(uid):
            await interaction.response.send_message("❌ You're not married!", ephemeral=True)
            return

        partner_id  = leveling._get_partner(uid)
        partner_obj = self.bot.get_user(partner_id)
        partner_name = partner_obj.display_name if partner_obj else f"User {partner_id}"

        confirm_btn = discord.ui.Button(label="Accept Divorce 💔", style=discord.ButtonStyle.danger)
        cancel_btn  = discord.ui.Button(label="Reject ❌", style=discord.ButtonStyle.secondary)

        async def confirm_callback(inter: discord.Interaction):
            if inter.user.id != partner_id:
                await inter.response.send_message("This isn't for you!", ephemeral=True)
                return
            cooldown_until = time.time() + DIVORCE_COOLDOWN_SECONDS
            leveling.marriages.pop(uid, None)
            leveling.marriages.pop(partner_id, None)
            leveling.user_rings.pop(uid, None)
            leveling.user_rings.pop(partner_id, None)
            leveling.divorce_cooldowns[uid]        = cooldown_until
            leveling.divorce_cooldowns[partner_id] = cooldown_until
            leveling.marriage_rings.pop(uid, None)
            leveling.marriage_rings.pop(partner_id, None)
            leveling.save_data()
            await inter.response.edit_message(
                embed=discord.Embed(
                    title="💔 Divorced",
                    description=(
                        f"{interaction.user.mention} and **{partner_name}** are now divorced.\n\n"
                        "Both rings have been destroyed. You can buy a new ring in **1 hour**."
                    ),
                    color=discord.Color.red()
                ),
                view=None
            )

        async def cancel_callback(inter: discord.Interaction):
            if inter.user.id != partner_id:
                await inter.response.send_message("This isn't for you!", ephemeral=True)
                return
            await inter.response.edit_message(
                embed=discord.Embed(
                    description=f"❌ **{partner_name}** rejected the divorce. You're still married!",
                    color=discord.Color.green()
                ),
                view=None
            )

        confirm_btn.callback = confirm_callback
        cancel_btn.callback  = cancel_callback
        view = discord.ui.View(timeout=60)
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        await interaction.response.send_message(
            embed=discord.Embed(
                title="💔 Divorce Request",
                description=(
                    f"{interaction.user.mention} wants to divorce **{partner_name}**!\n\n"
                    f"{partner_obj.mention if partner_obj else partner_name}, do you accept?\n\n"
                    "⚠️ **If accepted, both of you will:**\n"
                    "— Lose your rings permanently\n"
                    "— Have a **1-hour cooldown** before buying a new ring"
                ),
                color=discord.Color.red()
            ),
            view=view
        )

    @app_commands.command(name="forcedivorce", description="Force a divorce for 10,000 coins. No partner confirmation needed.")
    async def cmd_forcedivorce(self, interaction: discord.Interaction):
        leveling = self._leveling()
        if not await leveling._check_registered_interaction(interaction): return
        if not leveling:
            await interaction.response.send_message("❌ Leveling system not loaded!", ephemeral=True)
            return

        uid = interaction.user.id
        if not leveling._is_married(uid):
            await interaction.response.send_message("❌ You're not married!", ephemeral=True)
            return

        leveling._ensure_user(uid)
        if leveling.user_coins.get(uid, 0) < 10000:
            await interaction.response.send_message(
                f"❌ You need **{UGUISUCOIN} 10,000** to force divorce but only have **{UGUISUCOIN} {leveling.user_coins.get(uid, 0):,}**.",
                ephemeral=True
            )
            return

        partner_id   = leveling._get_partner(uid)
        partner_obj  = self.bot.get_user(partner_id)
        partner_name = partner_obj.display_name if partner_obj else f"User {partner_id}"

        confirm_btn = discord.ui.Button(label="Confirm Force Divorce", style=discord.ButtonStyle.danger, emoji="💔")
        cancel_btn  = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")

        async def confirm_callback(inter: discord.Interaction):
            if inter.user.id != uid:
                await inter.response.send_message("This isn't yours!", ephemeral=True)
                return
            if leveling.user_coins.get(uid, 0) < 10000:
                await inter.response.edit_message(
                    embed=discord.Embed(description="❌ You no longer have enough coins!", color=discord.Color.red()),
                    view=None
                )
                return
            cooldown_until = time.time() + DIVORCE_COOLDOWN_SECONDS
            leveling.user_coins[uid] -= 10000
            leveling.marriages.pop(uid, None)
            leveling.marriages.pop(partner_id, None)
            leveling.user_rings.pop(uid, None)
            leveling.user_rings.pop(partner_id, None)
            leveling.divorce_cooldowns[uid]        = cooldown_until
            leveling.divorce_cooldowns[partner_id] = cooldown_until
            leveling.marriage_rings.pop(uid, None)
            leveling.marriage_rings.pop(partner_id, None)
            leveling.save_data()
            await inter.response.edit_message(
                embed=discord.Embed(
                    title="💔 Force Divorced",
                    description=(
                        f"{interaction.user.mention} force divorced **{partner_name}**!\n\n"
                        f"**Cost:** {UGUISUCOIN} 10,000\n"
                        "Both rings have been destroyed. You can buy a new ring in **1 hour**."
                    ),
                    color=discord.Color.red()
                ),
                view=None
            )

        async def cancel_callback(inter: discord.Interaction):
            if inter.user.id != uid:
                await inter.response.send_message("This isn't yours!", ephemeral=True)
                return
            await inter.response.edit_message(
                embed=discord.Embed(description="✅ Force divorce cancelled.", color=discord.Color.green()),
                view=None
            )

        confirm_btn.callback = confirm_callback
        cancel_btn.callback  = cancel_callback
        view = discord.ui.View(timeout=30)
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        await interaction.response.send_message(
            embed=discord.Embed(
                title="💔 Force Divorce",
                description=(
                    f"Are you sure you want to force divorce **{partner_name}**?\n\n"
                    f"**Cost:** {UGUISUCOIN} **10,000**\n"
                    f"**Your balance:** {UGUISUCOIN} {leveling.user_coins.get(uid, 0):,}\n\n"
                    "⚠️ No confirmation needed from your partner.\n"
                    "Both rings destroyed. 1 hour cooldown for both."
                ),
                color=discord.Color.red()
            ),
            view=view
        )

    @app_commands.command(name="partner", description="Check who you or someone else is married to")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="Leave blank to check yourself")
    async def cmd_partner(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        leveling = self._leveling()
        if not await leveling._check_registered_interaction(interaction): return
        if not leveling:
            await interaction.response.send_message("❌ Leveling system not loaded!", ephemeral=True)
            return

        target     = member or interaction.user
        target_uid = target.id

        if not leveling._is_married(target_uid):
            await interaction.response.send_message(
                f"💍 **{target.display_name}** is not married to anyone.", ephemeral=True
            )
            return

        partner_id   = leveling._get_partner(target_uid)
        partner_obj  = self.bot.get_user(partner_id)
        partner_name = partner_obj.mention if partner_obj else f"User ID {partner_id}"
        ring_key = leveling.marriage_rings.get(target_uid)
        ring_text = f"{RINGS[ring_key]['emoji']} **{RINGS[ring_key]['name']}**" if ring_key else "Unknown"

        embed = discord.Embed(
            title="💍 Married",
            description=f"**{target.display_name}** is married to {partner_name}!",
            color=discord.Color(0xFF69B4)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Ring Used", value=ring_text, inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="removedeco")
    async def cmd_removedeco(self, ctx: commands.Context):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        uid = ctx.author.id
        active = get_active_deco(uid)

        if not active:
            await ctx.send("❌ You don't have an active decoration equipped.")
            return

        data = load_items()
        for item in data.get(str(uid), []):
            item["active_deco"] = False
        save_items(data)

        await ctx.send(
            embed=discord.Embed(
                title="🎨 Decoration Removed",
                description=f"{active['emoji']} **{active['name']}** `[{active['code']}]` has been unequipped.\nYour rank card is back to the default ring.",
                color=discord.Color(0x9B37FF)
            )
        )

    @commands.command(name="inventory", aliases=["inv"])
    async def cmd_inventory(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        target = member or ctx.author
        uid = target.id
        items = get_user_items(uid)

        if not items:
            await ctx.send(f"❌ **{target.display_name}** has no items in their inventory.")
            return

        active = get_active_deco(uid)

        decos = [i for i in items if i["type"] == "decoration"]
        rings = [i for i in items if i["type"] == "ring"]
        misc  = [i for i in items if i["type"] == "misc"]

        embed = discord.Embed(
            title=f"🎒 {target.display_name}'s Inventory",
            color=discord.Color(0x9B37FF)
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if decos:
            deco_lines = ""
            for i in decos:
                equipped = " ✅" if (active and active["code"] == i["code"]) else ""
                deco_lines += f"{i['emoji']} **{i['name']}** `[{i['code']}]` — *{i['rarity'].capitalize()}*{equipped}\n"
            embed.add_field(name="🎨 Decorations", value=deco_lines, inline=False)

        if rings:
            ring_lines = ""
            for i in rings:
                ring_lines += f"{i['emoji']} **{i['name']}** `[{i['code']}]` — *{i['rarity'].capitalize()}*\n"
            embed.add_field(name="💍 Rings", value=ring_lines, inline=False)

        if misc:
            misc_lines = ""
            for i in misc:
                misc_lines += f"{i['emoji']} **{i['name']}** `[{i['code']}]` — *{i['rarity'].capitalize()}*\n"
            embed.add_field(name="🎴 Misc", value=misc_lines, inline=False)

        embed.set_footer(text=f"{len(items)} total items")
        await ctx.send(embed=embed)

    @commands.command(name="sell")
    async def cmd_sell(self, ctx: commands.Context, *codes: str):
        leveling = self._leveling()
        if not await leveling._check_registered(ctx): return
        if not leveling:
            await ctx.send("❌ Leveling system not loaded!")
            return

        if not codes:
            await ctx.send("❌ Please specify at least one item code to sell! Example: `.sell 001 002`")
            return

        uid = ctx.author.id
        data = load_items()
        key = str(uid)

        if key not in data or not data[key]:
            await ctx.send("❌ You have no items in your inventory.")
            return

        sell_prices = {
            "common":     500,
            "uncommon":  2500,
            "rare":      25_000,
            "epic":      250_000,
            "legendary": 2_500_000,
            "divine":    25_000_000,
        }

        items_to_sell = []
        codes_not_found = []
        total_payout = 0
        temp_inventory = data[key].copy()

        for code in codes:
            matched_item = next((item for item in temp_inventory if item["code"] == code), None)
            if matched_item:
                if matched_item["item_id"] == "deco_premium":
                    await ctx.send(f"❌ **{matched_item['name']}** is a Premium item and cannot be sold!")
                    return
                price = sell_prices.get(matched_item["rarity"], 500)
                total_payout += price
                items_to_sell.append(matched_item)
                temp_inventory.remove(matched_item)
            else:
                codes_not_found.append(code)

        if codes_not_found:
            missing_str = ", ".join(f"`{c}`" for c in codes_not_found)
            await ctx.send(f"❌ Transaction aborted. You do not own or have enough copies of: {missing_str}")
            return

        item_summary_lines = []
        for item in items_to_sell:
            item_summary_lines.append(f"{item['emoji']} **{item['name']}** `[{item['code']}]` — 🪙 {sell_prices.get(item['rarity'], 500):,}")

        summary_text = "\n".join(item_summary_lines)

        confirm_btn = discord.ui.Button(label="Confirm Batch Sell", style=discord.ButtonStyle.success, emoji="🪙")
        cancel_btn  = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")

        embed = discord.Embed(
            title=f"{UGUISUCOIN} Confirm Batch Sale",
            description=(
                f"Are you sure you want to sell these **{len(items_to_sell)}** items?\n\n"
                f"{summary_text}\n\n"
                f"**Total Payout:** {UGUISUCOIN} **{total_payout:,}**"
            ),
            color=discord.Color.gold()
        )

        async def confirm_callback(inter: discord.Interaction):
            if inter.user != ctx.author:
                await inter.response.send_message("This isn't your sale!", ephemeral=True)
                return
            current_data = load_items()
            inventory = current_data.get(key, [])
            for item in items_to_sell:
                for inv_item in inventory:
                    if inv_item["code"] == item["code"]:
                        inventory.remove(inv_item)
                        break
            current_data[key] = inventory
            save_items(current_data)
            leveling._ensure_user(uid)
            leveling.user_coins[uid] = leveling.user_coins.get(uid, 0) + total_payout
            leveling.save_data()
            await inter.response.edit_message(
                embed=discord.Embed(
                    title=f"{UGUISUCOIN} Items Sold Successfully!",
                    description=(
                        f"Successfully sold **{len(items_to_sell)}** items for **{UGUISUCOIN} {total_payout:,}**!\n\n"
                        f"**New balance:** {UGUISUCOIN} {leveling.user_coins[uid]:,}"
                    ),
                    color=discord.Color(0x9B37FF)
                ),
                view=None
            )

        async def cancel_callback(inter: discord.Interaction):
            if inter.user != ctx.author:
                await inter.response.send_message("This isn't yours!", ephemeral=True)
                return
            await inter.response.edit_message(
                embed=discord.Embed(description="❌ Sale cancelled.", color=discord.Color.red()),
                view=None
            )

        confirm_btn.callback = confirm_callback
        cancel_btn.callback  = cancel_callback
        view = discord.ui.View(timeout=30)
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(MarriageSystem(bot))
    print("[marriage] Marriage system loaded ✓")
