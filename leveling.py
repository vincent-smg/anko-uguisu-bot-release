import json
import discord
import asyncio
import io
import aiohttp
import time
import os
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import random
from marriage import get_active_deco
import sqlite3

 # import here to avoid circular imports

# ══════════════════════════════════════════════════════════════════════════════
#  WEBSITE PREMIUM SYNC
#  The website (bot-siter) is the source of truth for who currently has an
#  active premium subscription. Every PREMIUM_SYNC_INTERVAL seconds we ask it
#  "who has premium right now?" and mirror that list into self.premium_users -
#  the exact same set /setpremium edits by hand. This is just /setpremium
#  running itself automatically based on what was bought on the website.
# ══════════════════════════════════════════════════════════════════════════════
SITE_URL = os.getenv("SITE_URL", "https://bot-siter.onrender.com")
STATUS_API_KEY = os.getenv("STATUS_API_KEY", "7bA9xM2pQ4vK9rT1wZ5nE8bC3mX6pQ")
PREMIUM_SYNC_INTERVAL = 30  # seconds


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

TEAM_SERVER_ID = 1511528060783169596
AUTHORIZED_USER_IDS = {1184473288626413598}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_PATH = os.path.join(BASE_DIR, "assets", "8405380.jpg")
DECO_PATH       = os.path.join(BASE_DIR, "assets", "decos")   # folder with deco_001.png etc.

FONT_PATH = "Exo_2/Exo2-Italic-VariableFont_wght.ttf"
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

COINS_PER_LEVEL = 1000
XP_PER_MESSAGE = 5
XP_COOLDOWN_SECONDS = 10

DIVORCE_COOLDOWN_SECONDS = 3600  # 1 hour
UGUISUCOIN = "<:uguisucoinno:1513628345156370523>"

# ══════════════════════════════════════════════════════════════════════════════
#  SHOP CATALOGUE
# ══════════════════════════════════════════════════════════════════════════════

RINGS = {
    "common":     {"name": "Common Ring",     "emoji": "💍", "tier": "Common",     "color": 0xAAAAAA, "price": 1_000},
    "uncommon":   {"name": "Uncommon Ring",   "emoji": "💚", "tier": "Uncommon",   "color": 0x2ECC71, "price": 10_000},
    "rare":       {"name": "Rare Ring",       "emoji": "💙", "tier": "Rare",       "color": 0x3498DB, "price": 100_000},
    "epic":       {"name": "Epic Ring",       "emoji": "💜", "tier": "Epic",       "color": 0x9B59B6, "price": 1_000_000},
    "legendary":  {"name": "Legendary Ring",  "emoji": "🧡", "tier": "Legendary",  "color": 0xE67E22, "price": 10_000_000},
    "divine":     {"name": "Divine Ring",     "emoji": "✨", "tier": "Divine",     "color": 0xF1C40F, "price": 100_000_000},
}

# ══════════════════════════════════════════════════════════════════════════════
#  COG IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════════════

class LevelingSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.registered_users: set = set()
        self.user_levels: dict = {}
        self.user_coins: dict = {}
        self.user_premium_backgrounds: dict = {}
        self.premium_users: set = set()
        self.role_xp_boosts: dict = {}
        self.leveling_channel: dict = {}
        self.marriage_rings: dict = {}
        self.manual_overrides = set()
        self._xp_cooldown: dict = {}
        self.user_accent_colors: dict = {}
        self.manual_overrides = set()
        self.user_rings: dict = {}
        self.marriages: dict = {}
        self.divorce_cooldowns: dict = {}

        self.user_data_file = "leveling_data.json"
        self.load_data()
        self.save_task = self.bot.loop.create_task(self._auto_save())
        self.premium_sync_task = self.bot.loop.create_task(self._auto_sync_premium())

    async def _auto_save(self):
        while True:
         await asyncio.sleep(300)
         self.save_data()

    async def _auto_sync_premium(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{SITE_URL}/api/premium-sync",
                        headers={"X-Status-Key": STATUS_API_KEY},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            payload = await resp.json()
                            website_premium_ids = set(int(x) for x in payload.get("premium_discord_ids", []))
                        
                        # ONLY sync if we successfully got data
                            self._sync_premium_set(website_premium_ids)
                        else:
                            print(f"Premium sync failed: HTTP {resp.status}")
            except Exception as e:
            # If the website is offline, we just log it and do nothing.
            # Because we DON'T call _sync_premium_set here, 
            # your local database/set remains exactly as it was.
                print(f"Premium sync error: {type(e).__name__}: {e}. Keeping current local premium state.")
            
            await asyncio.sleep(PREMIUM_SYNC_INTERVAL)

    def _sync_premium_set(self, website_premium_ids: set):
    
    
    # 1. Who is newly on the website?
        newly_premium = website_premium_ids - self.premium_users
    
    # 2. Who is gone from the website? 
    # CRITICAL: We subtract manual_overrides so they can NEVER be put in this list
        potential_removals = self.premium_users - website_premium_ids
        no_longer_premium = potential_removals - self.manual_overrides 

        if not newly_premium and not no_longer_premium:
            return

    # Granting logic...
        for uid in newly_premium:
            self.premium_users.add(uid)
        # ... (your existing grant item code) ...

    # Removing logic
        for uid in no_longer_premium:
            self.premium_users.discard(uid)
            print(f"⛔ Premium expired for {uid}")

        self.save_data()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load_data(self):
        try:
            with open(self.user_data_file, "r") as f:
                data = json.load(f)

            self.user_levels              = {int(k): v for k, v in data.get("user_levels", {}).items()}
            self.user_coins               = {int(k): v for k, v in data.get("user_coins", {}).items()}
            self.user_premium_backgrounds = {int(k): v for k, v in data.get("user_premium_backgrounds", {}).items()}
            self.leveling_channel         = {int(k): v for k, v in data.get("leveling_channel", {}).items()}
            self.premium_users            = set(int(x) for x in data.get("premium_users", []))
            self.user_rings               = {int(k): v for k, v in data.get("user_rings", {}).items()}
            self.marriages                = {int(k): int(v) for k, v in data.get("marriages", {}).items()}
            self.divorce_cooldowns        = {int(k): v for k, v in data.get("divorce_cooldowns", {}).items()}
            self.manual_overrides = set(int(x) for x in data.get("manual_overrides", []))
            self.daily_cooldowns          = {int(k): v for k, v in data.get("daily_cooldowns", {}).items()}
            self.registered_users = set(int(x) for x in data.get("registered_users", []))
            self.user_boxes = {int(k): v for k, v in data.get("user_boxes", {}).items()}
            self.marriage_rings = {int(k): v for k, v in data.get("marriage_rings", {}).items()}
            raw_boosts = data.get("role_xp_boosts", {})
            self.user_accent_colors = {int(k): v for k, v in data.get("user_accent_colors", {}).items()}
            self.role_xp_boosts = {
                int(guild_id): {int(role_id): boost for role_id, boost in roles.items()}
                for guild_id, roles in raw_boosts.items()
            }

            print("✅ All leveling, economy, marriage, and boost history successfully loaded!")
        except (FileNotFoundError, json.JSONDecodeError):
            print("📁 No database file found. Starting fresh...")
            self.save_data()

    def save_data(self):
        data = {
            "user_levels":               {str(k): v for k, v in self.user_levels.items()},
            "user_coins":                {str(k): v for k, v in self.user_coins.items()},
            "user_premium_backgrounds":  {str(k): v for k, v in self.user_premium_backgrounds.items()},
            "leveling_channel":          {str(k): v for k, v in self.leveling_channel.items()},
            "premium_users":             list(self.premium_users),
            "user_rings":                {str(k): v for k, v in self.user_rings.items()},
            "marriages":                 {str(k): v for k, v in self.marriages.items()},
            "divorce_cooldowns":         {str(k): v for k, v in self.divorce_cooldowns.items()},
            "daily_cooldowns": {str(k): v for k, v in getattr(self, "daily_cooldowns", {}).items()},
            "registered_users": list(self.registered_users),
            "user_boxes": {str(k): v for k, v in getattr(self, "user_boxes", {}).items()},
            "marriage_rings": {str(k): v for k, v in self.marriage_rings.items()},
            "user_accent_colors": {str(k): v for k, v in self.user_accent_colors.items()},
            "manual_overrides": list(self.manual_overrides),
            "role_xp_boosts": {
                str(guild_id): {str(role_id): boost for role_id, boost in roles.items()}
                
                for guild_id, roles in self.role_xp_boosts.items()
                
            },
        }
        with open(self.user_data_file, "w") as f:
            json.dump(data, f, indent=4)
            
    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_xp_needed(self, level: int) -> int:
        return 100 * level

    def _ensure_user(self, user_id: int):
        if user_id not in self.user_levels:
            self.user_levels[user_id] = {"xp": 0, "level": 1}
        if user_id not in self.user_coins:
            self.user_coins[user_id] = 0

    def _is_authorized(self, user_id: int) -> bool:
        return user_id in AUTHORIZED_USER_IDS

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            return ImageFont.truetype(FALLBACK_FONT, size)

    def _is_married(self, uid: int) -> bool:
        return uid in self.marriages

    def _get_partner(self, uid: int) -> Optional[int]:
        return self.marriages.get(uid)

    def _on_divorce_cooldown(self, uid: int) -> bool:
        cooldown_until = self.divorce_cooldowns.get(uid, 0)
        return time.time() < cooldown_until

    def _cooldown_remaining(self, uid: int) -> int:
        return max(0, int(self.divorce_cooldowns.get(uid, 0) - time.time()))

    async def _check_registered(self, ctx: commands.Context) -> bool:
        if ctx.author.id not in self.registered_users:
            try:
                await ctx.author.send(
                    embed=discord.Embed(
                        title="⚠️ Not Registered",
                        description=(
                            "You need to register before using bot commands!\n\n"
                            "Head to the server and type `.register` to get started."
                        ),
                        color=discord.Color.orange()
                    )
                )
            except discord.Forbidden:
                pass
            return False
        return True
    async def _check_registered_interaction(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.registered_users:
            try:
                await interaction.user.send(
                    embed=discord.Embed(
                        title="⚠️ Not Registered",
                        description=(
                            "You need to register before using bot commands!\n\n"
                            "Head to the server and type `.register` to get started."
                        ),
                        color=discord.Color.orange()
                    )
                )
            except discord.Forbidden:
                pass
            return False
        return True
    
    def is_user_premium(user_id):
        conn = sqlite3.connect("premium_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT is_premium FROM premiums WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
    
        # Return True if they exist and is_premium is 1, otherwise False
        return result is not None and result[0] == 1

    def _get_deco_image(self, item_id: str) -> Optional[Image.Image]:
        """Load and return a deco PNG (144x144 RGBA) by item_id, or None if not found."""
        path = os.path.join(DECO_PATH, f"{item_id}.png")
        if not os.path.exists(path):
            return None
        try:
            return Image.open(path).convert("RGBA").resize((144, 144), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"[Leveling] Failed to load deco {item_id}: {e}")
            return None
        
    def _get_accent(self, uid: int) -> tuple:
   
        hex_color = self.user_accent_colors.get(uid, "#9B37FF")
        hex_color = hex_color.lstrip("#")
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return (155, 55, 255)

    # ── Image helpers ─────────────────────────────────────────────────────────

    async def _fetch_avatar(self, session: aiohttp.ClientSession, url: str, size: int = 128) -> Image.Image:
        async with session.get(url) as resp:
            data = await resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(img, (0, 0), mask)
        return result

    async def load_background(self, session: aiohttp.ClientSession, path_or_url: str, w: int, h: int) -> Image.Image:
        def cover_crop(img: Image.Image) -> Image.Image:
            img = img.convert("RGBA")
            img_w, img_h = img.size
            scale = max(w / img_w, h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - w) // 2
            top  = (new_h - h) // 2
            return img.crop((left, top, left + w, top + h))

        try:
            if path_or_url.startswith(("http://", "https://")):
                async with session.get(path_or_url) as resp:
                    data = await resp.read()
                bg = Image.open(io.BytesIO(data))
            else:
                bg = Image.open(path_or_url)
            return cover_crop(bg)
        except Exception as e:
            print(f"[Leveling] Background load error ({path_or_url}): {e}")
            return cover_crop(Image.open(BACKGROUND_PATH))

     # ── Card Builders ─────────────────────────────────────────────────────────
    async def build_rank_card(self, member: discord.Member) -> discord.File:
        uid = member.id
        self._ensure_user(uid)
        data   = self.user_levels[uid]
        level  = data["level"]
        xp     = data["xp"]
        needed = self.get_xp_needed(level)
        coins  = self.user_coins.get(uid, 0)

        guild_members = [(mid, self.user_levels[mid]["level"], self.user_levels[mid]["xp"]) for mid in self.user_levels]
        guild_members.sort(key=lambda x: (x[1], x[2]), reverse=True)
        rank = next((i + 1 for i, (mid, *_) in enumerate(guild_members) if mid == uid), "?")

        async with aiohttp.ClientSession() as session:
            bg_path = self.user_premium_backgrounds.get(uid, BACKGROUND_PATH) if uid in self.premium_users else BACKGROUND_PATH
            bg      = await self.load_background(session, bg_path, 900, 280)
            av_url  = member.display_avatar.replace(size=256).url
            avatar  = await self._fetch_avatar(session, av_url, 136)

        active_deco    = get_active_deco(uid)
        is_premium     = uid in self.premium_users
        accent         = self._get_accent(uid) if is_premium else (155, 55, 255)
        display_name   = member.display_name
        load_font      = self._load_font
        get_deco_image = self._get_deco_image

        def draw_card():
            W, H = 900, 280
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            for x in range(W):
                if x < 350:
                    alpha = 165
                elif x < 700:
                    alpha = int(165 * (1 - (x - 350) / (700 - 350)))
                else:
                    alpha = 0
                overlay_draw.line([(x, 0), (x, H)], fill=(8, 4, 18, alpha))
            canvas = Image.alpha_composite(bg, overlay)

            draw    = ImageDraw.Draw(canvas)
            f_name  = load_font(40)
            f_level = load_font(20)
            f_xp    = load_font(19)
            f_rank  = load_font(18)
            f_coins = load_font(17)

            AV_X, AV_Y = 85, H // 2
            canvas.paste(avatar, (AV_X - 68, AV_Y - 68), avatar)

            PREMIUM_DEFAULT_DECO = "deco_premium"
            if not active_deco and is_premium:
                premium_img = get_deco_image(PREMIUM_DEFAULT_DECO)
                if premium_img:
                    canvas.paste(premium_img, (AV_X - 72, AV_Y - 72), premium_img)
                else:
                    draw.ellipse([AV_X - 72, AV_Y - 72, AV_X + 72, AV_Y + 72],
                                 outline=(*accent, 255), width=4)
            elif active_deco:
                deco_img = get_deco_image(active_deco["item_id"])
                if deco_img:
                    canvas.paste(deco_img, (AV_X - 72, AV_Y - 72), deco_img)
                else:
                    draw.ellipse([AV_X - 72, AV_Y - 72, AV_X + 72, AV_Y + 72],
                                 outline=(*accent, 255), width=3)
            else:
                draw.ellipse([AV_X - 72, AV_Y - 72, AV_X + 72, AV_Y + 72],
                             outline=(*accent, 255), width=3)

            TEXT_X = 180
            draw.text((TEXT_X, 42), display_name, font=f_name, fill=(255, 255, 255, 255))
            draw.rounded_rectangle([TEXT_X, 96, TEXT_X + 120, 124], radius=12, fill=(*accent, 210))
            draw.text((TEXT_X + 10, 99), f"LEVEL  {level}", font=f_level, fill=(255, 255, 255, 255))
            draw.rounded_rectangle([TEXT_X + 130, 96, TEXT_X + 250, 124], radius=12, fill=(40, 20, 70, 200))
            draw.text((TEXT_X + 140, 99), f"#{rank}  RANK", font=f_rank, fill=(*accent, 255))

            BAR_X, BAR_Y, BAR_W, BAR_H = TEXT_X, 142, 370, 13
            draw.rounded_rectangle([BAR_X, BAR_Y, BAR_X + BAR_W, BAR_Y + BAR_H], radius=6, fill=(25, 12, 45, 210))
            fill_w = max(8, int(BAR_W * (xp / needed))) if needed > 0 else 8
            draw.rounded_rectangle([BAR_X, BAR_Y, BAR_X + fill_w, BAR_Y + BAR_H], radius=6, fill=(*accent, 255))

            draw.text((BAR_X, BAR_Y + 17), f"{xp:,} / {needed:,} XP", font=f_xp, fill=(*accent, 220))
            draw.text((TEXT_X, 184), f"   {coins:,} coins", font=f_coins, fill=(200, 255, 180, 210))

            if is_premium:
                draw.text((TEXT_X, 210), "PREMIUM", font=f_rank, fill=(255, 210, 80, 230))

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf

        buf = await asyncio.to_thread(draw_card)
        return discord.File(buf, filename="rank.png")
    
    async def build_levelup_card(self, member: discord.Member, new_level: int, coins_earned: int) -> discord.File:
        W, H = 900, 300
        uid  = member.id

        async with aiohttp.ClientSession() as session:
            bg_path = self.user_premium_backgrounds.get(uid, BACKGROUND_PATH) if uid in self.premium_users else BACKGROUND_PATH
            bg      = await self.load_background(session, bg_path, W, H)
            av_url  = member.display_avatar.replace(size=256).url
            avatar  = await self._fetch_avatar(session, av_url, 104)

        active_deco    = get_active_deco(uid)
        is_premium     = uid in self.premium_users
        accent         = self._get_accent(uid) if is_premium else (150, 50, 255)
        display_name   = member.display_name
        load_font      = self._load_font
        get_deco_image = self._get_deco_image

        def draw_levelup():
            canvas = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 15, 150)))
            glow   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd     = ImageDraw.Draw(glow)
            for r in range(200, 0, -8):
                alpha = int(90 * (1 - r / 200))
                gd.ellipse([W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r], fill=(*accent, alpha))
            canvas2 = Image.alpha_composite(canvas, glow)

            draw        = ImageDraw.Draw(canvas2)
            AV_X, AV_Y = W // 2, 75
            canvas2.paste(avatar, (AV_X - 52, AV_Y - 52), avatar)

            if active_deco:
                deco_img = get_deco_image(active_deco["item_id"])
                if deco_img:
                    deco_img = deco_img.resize((110, 110), Image.Resampling.LANCZOS)
                    canvas2.paste(deco_img, (AV_X - 55, AV_Y - 55), deco_img)
                else:
                    draw.ellipse([AV_X - 55, AV_Y - 55, AV_X + 55, AV_Y + 55], outline=(*accent, 255), width=3)
            elif is_premium:
                premium_img = get_deco_image("deco_premium")
                if premium_img:
                    premium_img = premium_img.resize((110, 110), Image.Resampling.LANCZOS)
                    canvas2.paste(premium_img, (AV_X - 55, AV_Y - 55), premium_img)
                else:
                    draw.ellipse([AV_X - 55, AV_Y - 55, AV_X + 55, AV_Y + 55], outline=(*accent, 255), width=3)
            else:
                draw.ellipse([AV_X - 55, AV_Y - 55, AV_X + 55, AV_Y + 55], outline=(*accent, 255), width=3)

            def center_text(text, font, y, color):
                bb = draw.textbbox((0, 0), text, font=font)
                x  = (W - (bb[2] - bb[0])) // 2
                draw.text((x, y), text, font=font, fill=color)

            center_text(f"{display_name} leveled up!", load_font(50), 143, (255, 255, 255, 255))
            center_text(f"★   LEVEL {new_level}   ★",  load_font(32), 203, (*accent, 255))
            center_text(f"+ {coins_earned:,}  coins earned", load_font(22), 256, (180, 255, 180, 230))

            buf = io.BytesIO()
            canvas2.save(buf, format="PNG")
            buf.seek(0)
            return buf

        buf = await asyncio.to_thread(draw_levelup)
        return discord.File(buf, filename="levelup.png")
     # ── XP Logic ─────────────────────────────────────────────────────────────

    async def process_xp(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        uid = message.author.id
        if uid not in self.registered_users:
            return

        uid = message.author.id
        now = time.time()

        if now - self._xp_cooldown.get(uid, 0) < XP_COOLDOWN_SECONDS:
            return
        self._xp_cooldown[uid] = now

        self._ensure_user(uid)
        xp_gain  = XP_PER_MESSAGE
        guild_id = message.guild.id

        if guild_id in self.role_xp_boosts:
            best = max((self.role_xp_boosts[guild_id].get(r.id, 0) for r in message.author.roles), default=0)
            if best > 0:
                xp_gain = int(XP_PER_MESSAGE * (1 + best / 100))

        self.user_levels[uid]["xp"] += xp_gain

        while self.user_levels[uid]["xp"] >= self.get_xp_needed(self.user_levels[uid]["level"]):
            self.user_levels[uid]["xp"]   -= self.get_xp_needed(self.user_levels[uid]["level"])
            self.user_levels[uid]["level"] += 1

            if self.user_levels[uid]["level"] > 999:
                self.user_levels[uid]["level"] = 999
                self.user_levels[uid]["xp"]    = 0

            new_level    = self.user_levels[uid]["level"]
            coins_earned = new_level * COINS_PER_LEVEL
            self.user_coins[uid] = self.user_coins.get(uid, 0) + coins_earned

            channel_id  = self.leveling_channel.get(guild_id)
            ann_channel = message.guild.get_channel(channel_id) if channel_id else message.channel

            try:
                card = await self.build_levelup_card(message.author, new_level, coins_earned)
                await ann_channel.send(file=card)
            except Exception as e:
                print(f"[Leveling] Level-up card failed: {e}")
                await ann_channel.send(f"🎉 **{message.author.mention}** reached **Level {new_level}**! +{coins_earned:,} 🪙")

        self.save_data()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_xp(message)

    # ── Command Guards ────────────────────────────────────────────────────────

    async def team_only(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != TEAM_SERVER_ID:
            await interaction.response.send_message("❌ Team server only.", ephemeral=True)
            return False
        if not self._is_authorized(interaction.user.id):
            await interaction.response.send_message("❌ Not authorized.", ephemeral=True)
            return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  SLASH COMMANDS
    # ══════════════════════════════════════════════════════════════════════════
    @commands.command(name="register")
    async def register(self, ctx: commands.Context):
        uid = ctx.author.id
        if uid in self.registered_users:
            await ctx.send(
                embed=discord.Embed(
                    description="✅ You're already registered! You can use all bot commands.",
                    color=discord.Color(0x9B37FF)
                )
            )
            return

        self.registered_users.add(uid)
        self._ensure_user(uid)
        self.save_data()

        embed = discord.Embed(
            title="🎉 Welcome!",
            description=(
                f"You're now registered, **{ctx.author.display_name}**!\n\n"
                "You now have access to:\n"
                "— 📈 XP & leveling\n"
                "— 🪙 Coins & daily rewards\n"
                "— 💍 Marriage system\n"
                "— 🎁 Boxes & items\n\n"
                "Use `.daily` to claim your first reward!"
            ),
            color=discord.Color(0x9B37FF)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    @app_commands.command(name="leaderboard", description="View the top 10 players by level")
    async def cmd_leaderboard(self, interaction: discord.Interaction):
        if not await self._check_registered_interaction(interaction):
            return

        await interaction.response.defer()

    # Find top 10 VALID members
        valid_users = []

        sorted_users = sorted(
            self.user_levels.items(),
            key=lambda x: (x[1]["level"], x[1]["xp"]),
            reverse=True
        )

        for uid, data in sorted_users:
            member = interaction.guild.get_member(uid)

            if member is None:
                try:
                    member = await interaction.guild.fetch_member(uid)
                except Exception:
                    continue

            valid_users.append((uid, data, member))

            if len(valid_users) >= 10:
                break

        if not valid_users:
            await interaction.followup.send("No leaderboard data yet!")
            return
        entries = []

        async with aiohttp.ClientSession() as session:
            for rank, (uid, data, member) in enumerate(valid_users, start=1):

                try:
                    av_url = member.display_avatar.replace(size=64).url
                    avatar = await self._fetch_avatar(session, av_url, 48)

                    if avatar is None:
                        raise ValueError("Avatar fetch returned None")

                except Exception as e:
                    print(f"[leaderboard] Avatar failed for {member}: {e}")

                    avatar = Image.new("RGBA", (48, 48), (60, 60, 60, 255))

                entries.append({
                    "rank": rank,
                    "member": member,
                    "avatar": avatar,
                    "level": data["level"],
                    "xp": data["xp"],
                    "coins": self.user_coins.get(uid, 0),
                    "is_premium": uid in self.premium_users,
                    "accent": (
                        self._get_accent(uid)
                        if uid in self.premium_users
                       else (155, 55, 255)
                    ),
                })

        load_font = self._load_font
        get_xp_needed = self.get_xp_needed

        def draw_leaderboard():
            ROW_H = 64
            PADDING = 20
            W = 700
            H = PADDING + len(entries) * ROW_H + PADDING

            canvas = Image.new("RGBA", (W, H), (14, 8, 26, 255))
            draw = ImageDraw.Draw(canvas)

            for i in range(len(entries) + 1):
                y = PADDING + i * ROW_H
                draw.line(
                    [(0, y), (W, y)],
                    fill=(40, 25, 60, 180),
                    width=1
                )

            f_rank = load_font(17)
            f_name = load_font(19)
            f_detail = load_font(15)

            RANK_COLORS = {
                1: (255, 215, 80),
                2: (192, 192, 192),
                3: (205, 127, 50),
            }

            for entry in entries:
                rank = entry["rank"]

                row_top = PADDING + (rank - 1) * ROW_H
                y_mid = row_top + ROW_H // 2

                accent = entry["accent"]
                r_color = RANK_COLORS.get(rank, (180, 160, 210))

                if rank <= 3:
                    draw.rounded_rectangle(
                        [6, row_top + 3, W - 6, row_top + ROW_H - 3],
                        radius=8,
                        fill=(30, 15, 50, 200)
                    )

                draw.text(
                    (18, y_mid - 10),
                    f"#{rank}",
                    font=f_rank,
                    fill=r_color
                )

                AV_X = 65
                canvas.paste(
                    entry["avatar"],
                    (AV_X, y_mid - 24),
                    entry["avatar"]
                 )

                name = entry["member"].display_name

                if len(name) > 20:
                    name = name[:18] + "…"

                draw.text(
                    (AV_X + 58, y_mid - 20),
                    name,
                    font=f_name,
                    fill=(255, 255, 255)
                )

                needed = get_xp_needed(entry["level"])

                draw.text(
                    (AV_X + 58, y_mid + 4),
                    f"Level {entry['level']} • {entry['xp']:,}/{needed:,} XP",
                    font=f_detail,
                    fill=(180, 160, 210, 210)
                 )

                coins_text = f"{entry['coins']:,} coins"

                bbox = draw.textbbox(
                    (0, 0),
                    coins_text,
                    font=f_detail
                )

                tw = bbox[2] - bbox[0]

                draw.text(
                    (W - tw - 18, y_mid - 8),
                    coins_text,
                    font=f_detail,
                    fill=(*accent, 220)
                )

                if entry["is_premium"]:
                    draw.ellipse(
                        [W - 14, y_mid - 4, W - 6, y_mid + 4],
                        fill=(255, 210, 80)
                    )

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf

        buf = await asyncio.to_thread(draw_leaderboard)

        file = discord.File(
            buf,
            filename="leaderboard.png"
        )

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description=f"Top {len(entries)} players in **{interaction.guild.name}**",
            color=discord.Color(0x9B37FF)
        )

        embed.set_image(
            url="attachment://leaderboard.png"
        )

        await interaction.followup.send(
            embed=embed,
            file=file
        )



    @app_commands.command(name="level", description="Check your (or someone else's) rank card")
    @app_commands.describe(member="The user to check (leave blank for yourself)")
    async def cmd_level(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not await self._check_registered_interaction(interaction): return
        await interaction.response.defer()
         
        target = member or interaction.user
        try:
            card = await self.build_rank_card(target)
            await interaction.followup.send(file=card)
        except Exception as e:
            print(f"[Leveling] Card UI error: {e}")
            uid = target.id
            self._ensure_user(uid)
            d = self.user_levels[uid]
            await interaction.followup.send(f"**{target.display_name}** — Level {d['level']} | {d['xp']}/{self.get_xp_needed(d['level'])} XP")

    @app_commands.command(name="setlevelchannel", description="Set the channel for level-up announcements")
    @app_commands.describe(channel="The channel to send level-up messages to")
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_setlevelchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self._check_registered_interaction(interaction): return
        self.leveling_channel[interaction.guild.id] = channel.id
        self.save_data()
        await interaction.response.send_message(f"✅ Level-up announcements → {channel.mention}", ephemeral=True)

    @app_commands.command(name="addxp", description="[TEAM] Give XP to a user by username")
    @app_commands.guilds(discord.Object(id=TEAM_SERVER_ID))
    @app_commands.describe(username="Discord username of the target user", amount="Amount of XP to add")
    async def cmd_addxp(self, interaction: discord.Interaction, username: str, amount: int):
        if not await self.team_only(interaction): return
        await interaction.response.defer(ephemeral=True)
        target_user = discord.utils.find(lambda u: u.name.lower() == username.lower(), self.bot.users)
        if not target_user:
            await interaction.followup.send(f"❌ Could not find user `{username}`.", ephemeral=True)
            return
        uid = target_user.id
        self._ensure_user(uid)
        self.user_levels[uid]["xp"] += amount
        leveled_up = False
        while self.user_levels[uid]["xp"] >= self.get_xp_needed(self.user_levels[uid]["level"]):
            self.user_levels[uid]["xp"]   -= self.get_xp_needed(self.user_levels[uid]["level"])
            self.user_levels[uid]["level"] += 1
            self.user_coins[uid]           += (self.user_levels[uid]["level"] * COINS_PER_LEVEL)
            leveled_up = True
        self.save_data()
        msg = f"✅ Added **{amount} XP** to **{target_user.name}**."
        if leveled_up:
            msg += f" They leveled up to **Level {self.user_levels[uid]['level']}**!"
        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="setlevel", description="[TEAM] Set a user's level by username")
    @app_commands.guilds(discord.Object(id=TEAM_SERVER_ID))
    async def cmd_setlevel(self, interaction: discord.Interaction, username: str, level: int):
        if not await self.team_only(interaction): return
        if not 1 <= level <= 999:
            await interaction.response.send_message("❌ Level must be between 1 and 999.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        target_user = discord.utils.find(lambda u: u.name.lower() == username.lower(), self.bot.users)
        if not target_user:
            await interaction.followup.send(f"❌ Could not find user `{username}`.", ephemeral=True)
            return
        self._ensure_user(target_user.id)
        self.user_levels[target_user.id]["level"] = level
        self.user_levels[target_user.id]["xp"]    = 0
        self.save_data()
        await interaction.followup.send(f"✅ Set **{target_user.name}**'s level to **{level}**.", ephemeral=True)

    @app_commands.command(name="addcoins", description="[TEAM] Give coins to a user by username")
    @app_commands.guilds(discord.Object(id=TEAM_SERVER_ID))
    async def cmd_addcoins(self, interaction: discord.Interaction, username: str, amount: int):
        if not await self.team_only(interaction): return
        await interaction.response.defer(ephemeral=True)
        target_user = discord.utils.find(lambda u: u.name.lower() == username.lower(), self.bot.users)
        if not target_user:
            await interaction.followup.send(f"❌ Could not find user `{username}`.", ephemeral=True)
            return
        self._ensure_user(target_user.id)
        self.user_coins[target_user.id] += amount
        self.save_data()
        await interaction.followup.send(f"✅ Added **{amount:,} {UGUISUCOIN}** to **{target_user.name}**.", ephemeral=True)

    @app_commands.command(name="assignxpboost", description="[TEAM] Assign XP boost % to a role")
    @app_commands.guilds(discord.Object(id=TEAM_SERVER_ID))
    async def cmd_assignxpboost(self, interaction: discord.Interaction, role: discord.Role, xp_boost: int, target_guild_id: Optional[str] = None):
        if not await self.team_only(interaction): return
        if not 1 <= xp_boost <= 300:
            await interaction.response.send_message("❌ Boost must be 1–300.", ephemeral=True)
            return
        gid = int(target_guild_id) if target_guild_id else interaction.guild_id
        if not gid:
            await interaction.response.send_message("❌ Could not resolve target guild ID.", ephemeral=True)
            return
        self.role_xp_boosts.setdefault(gid, {})[role.id] = xp_boost
        self.save_data()
        await interaction.response.send_message(f"✅ **{role.name}** → **{xp_boost}%** XP boost (guild {gid}).", ephemeral=True)

    @app_commands.command(name="setpremium", description="[TEAM] Grant or revoke premium status for a user")
    @app_commands.guilds(discord.Object(id=TEAM_SERVER_ID))
    async def cmd_setpremium(self, interaction: discord.Interaction, username: str, grant: bool):
        if not await self.team_only(interaction): return
        await interaction.response.defer(ephemeral=True)
        target_user = discord.utils.find(lambda u: u.name.lower() == username.lower(), self.bot.users)
        if not target_user:
            await interaction.followup.send(f"❌ Could not find user `{username}`.", ephemeral=True)
            return
        if grant:
            self.premium_users.add(target_user.id)
            self.manual_overrides.add(target_user.id)
            # 1. Fixed the import line (removed trailing comma)
            from marriage import give_item, get_user_items, MYSTERY_ITEM_POOL, CLASSIC_ITEM_POOL
            
            # 2. Fixed the loop line (removed trailing comma after the pool)
            premium_item = next((i for i in MYSTERY_ITEM_POOL if i["id"] == "deco_premium"), None)
            
            existing = get_user_items(target_user.id)
            already_has = any(i["item_id"] == "deco_premium" for i in existing)
            if premium_item and not already_has:
                give_item(target_user.id, premium_item)
            await interaction.followup.send(f"✅ **{target_user.name}** now has **Premium**.", ephemeral=True)
       


    @app_commands.command(name="setbg", description="[Premium] Set your custom rank card background")
    async def cmd_setbg(self, interaction: discord.Interaction, url: str):
        if not await self._check_registered_interaction(interaction):
            return
        if interaction.user.id not in self.premium_users:
            await interaction.response.send_message("❌ This is a **Premium** feature.", ephemeral=True)
            return
        self.user_premium_backgrounds[interaction.user.id] = url
        self.save_data()
        await interaction.response.send_message("✅ Your custom background has been set!", ephemeral=True)
    @app_commands.command(name="changecolor", description="[Premium] Change your rank card accent color")
    @app_commands.describe(hex_code="A hex color code, e.g. #FF5733 or FF5733")
    async def cmd_changecolor(self, interaction: discord.Interaction, hex_code: str):
        if not await self._check_registered_interaction(interaction):
            return
        if interaction.user.id not in self.premium_users:
            await interaction.response.send_message("❌ This is a **Premium** feature.", ephemeral=True)
            return

        # Validate the hex code
        cleaned = hex_code.lstrip("#").strip()
        if len(cleaned) not in (3, 6) or not all(c in "0123456789abcdefABCDEF" for c in cleaned):
            await interaction.response.send_message(
                "❌ Invalid hex code. Please use a format like `#9B37FF` or `FF5733`.", ephemeral=True
            )
            return

        # Normalize to 6-char form
        if len(cleaned) == 3:
            cleaned = "".join(c * 2 for c in cleaned)
        normalized = f"#{cleaned.upper()}"

        self.user_accent_colors[interaction.user.id] = normalized
        self.save_data()

        r, g, b = int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)
        embed = discord.Embed(
            description=f"✅ Your rank card accent color has been set to **{normalized}**!",
            color=discord.Color.from_rgb(r, g, b)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)



    @app_commands.command(name="balance", description="Check your coin balance")
    async def cmd_balance(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not await self._check_registered_interaction(interaction):
            return
            
        target = member or interaction.user
        self._ensure_user(target.id)
        coins = self.user_coins.get(target.id, 0)
        embed = discord.Embed(description=f"{UGUISUCOIN}  **{coins:,} coins**", color=discord.Color(0x9B37FF))
        embed.set_author(name=f"{target.display_name}'s balance", icon_url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="debugsync")
    async def debug_sync(self, ctx):
        guild = discord.Object(id=TEAM_SERVER_ID)
        global_cmds = self.bot.tree.get_commands()
        guild_cmds  = self.bot.tree.get_commands(guild=guild)
        print(f"Global commands: {[c.name for c in global_cmds]}")
        print(f"Guild commands:  {[c.name for c in guild_cmds]}")
        g_synced  = await self.bot.tree.sync()
        gu_synced = await self.bot.tree.sync(guild=guild)
        print(f"Synced global: {[c.name for c in g_synced]}")
        print(f"Synced guild:  {[c.name for c in gu_synced]}")
        await ctx.send("✅ Check your console!")
        
    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        if not await self._check_registered(ctx): return
        uid = ctx.author.id
        self._ensure_user(uid)

        now = time.time()
        last_claimed = self.daily_cooldowns.get(uid, 0)
        if now - last_claimed < 86400:
            remaining = int(86400 - (now - last_claimed))
            hours, rem = divmod(remaining, 3600)
            mins, secs = divmod(rem, 60)
            await ctx.send(f"⏳ You already claimed today! Come back in **{hours}h {mins}m {secs}s**.")
            return

        self.daily_cooldowns[uid] = now

        coins = random.randint(1000, 3000)
        self.user_coins[uid] = self.user_coins.get(uid, 0) + coins

        got_box = random.random() < 0.10
        if got_box:
            if not hasattr(self, "user_boxes"):
                self.user_boxes = {}
            self.user_boxes[uid] = self.user_boxes.get(uid, 0) + 1

        self.save_data()

        embed = discord.Embed(title="🎁 Daily Reward!", color=discord.Color(0x9B37FF))
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Coins", value=f"{UGUISUCOIN} **+{coins:,}**", inline=True)
        if got_box:
            embed.add_field(name="Bonus!", value="<:boxclose:1513969806376829191> **+1 Mystery Box!**", inline=True)
            embed.set_footer(text="Lucky! You got a bonus box 🎉 | Come back in 24h")
        else:
            embed.set_footer(text="Come back in 24h for your next reward!")
        embed.add_field(name="New Balance", value=f"{UGUISUCOIN} **{self.user_coins[uid]:,}**", inline=False)
        await ctx.send(embed=embed)





# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingSystem(bot))
    print("[leveling] Leveling system loaded ✓")