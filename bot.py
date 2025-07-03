import discord
from discord.ext import commands
import json
import random
from datetime import datetime, timedelta, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

CURRENCY_NAME = "dOLLARIANAS"
DATA_FILE = "balances.json"
XP_FILE = "xp.json"

balances = {}
user_xp = {}

beg_cooldowns = {}
work_cooldowns = {}
daily_cooldowns = {}

OWNER_ID = 755846396208218174
MOD_ROLE_NAME = "mODIANA"
ADMIN_ROLE_NAME = "kAREN"

ROLE_MESSAGE_ID = None
EMOJI_TO_ROLE = {
    "💙": "mALE",
    "💗": "fEMALE",
    "🤍": "oTHER (AKS)"
}

# --- Helper functions ---
def load_balances():
    global balances
    try:
        with open(DATA_FILE, "r") as f:
            balances = json.load(f)
    except FileNotFoundError:
        balances = {}

def save_balances():
    with open(DATA_FILE, "w") as f:
        json.dump(balances, f)

def get_balance(user_id):
    return balances.get(str(user_id), 0)

def change_balance(user_id, amount):
    user_id = str(user_id)
    balances[user_id] = balances.get(user_id, 0) + amount
    if balances[user_id] < 0:
        balances[user_id] = 0
    save_balances()

def load_xp():
    global user_xp
    try:
        with open(XP_FILE, "r") as f:
            user_xp = json.load(f)
    except FileNotFoundError:
        user_xp = {}

def save_xp():
    with open(XP_FILE, "w") as f:
        json.dump(user_xp, f)

def add_xp(user_id, amount):
    user_id = str(user_id)
    xp_data = user_xp.get(user_id, {"xp": 0, "level": 1})
    xp_data["xp"] += amount
    # Level up every 100 XP
    if xp_data["xp"] >= xp_data["level"] * 100:
        xp_data["xp"] = 0
        xp_data["level"] += 1
    user_xp[user_id] = xp_data
    save_xp()

def get_level(user_id):
    return user_xp.get(str(user_id), {"xp": 0, "level": 1})

def has_mod_or_admin(ctx):
    roles = [role.name for role in ctx.author.roles]
    return MOD_ROLE_NAME in roles or ADMIN_ROLE_NAME in roles or ctx.author.id == OWNER_ID

# --- Events ---
@bot.event
async def on_ready():
    load_balances()
    load_xp()
    print(f"{bot.user} is online and ready!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    add_xp(message.author.id, random.randint(5, 15))
    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != ROLE_MESSAGE_ID:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    role_name = EMOJI_TO_ROLE.get(str(payload.emoji))
    if not role_name:
        return
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(payload.user_id)
    if role and member and not member.bot:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            print(f"Missing permission to add role {role_name} to {member}")

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id != ROLE_MESSAGE_ID:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    role_name = EMOJI_TO_ROLE.get(str(payload.emoji))
    if not role_name:
        return
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(payload.user_id)
    if role and member:
        try:
            await member.remove_roles(role)
        except discord.Forbidden:
            print(f"Missing permission to remove role {role_name} from {member}")

# --- Commands ---

@bot.command()
async def help(ctx):
    help_text = """
commands available:

?balance - check your dOLLARIANAS balance
?beg - beg for money (10 min cooldown)
?daily - claim daily reward (24h cooldown)
?work - work a job to earn money (20 min cooldown)

?impregnate @user - impregnate someone, child support paid randomly
?nuke - delete all messages in channel (mods only)
?kick @user [reason] - kick a member (mods only)
?ban @user [reason] - ban a member (mods only)
?clear [amount] - delete messages (mods only)

?reactionroles - post gender role selection message
?nicki - get a random Nicki Minaj lyric
?level - show your level and XP
?leaderboard - show top 5 users by level

?spotify - spotify integration placeholder
"""
    await ctx.send(help_text)

@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"{ctx.author.mention}, you have {bal} {CURRENCY_NAME}.")

@bot.command()
async def beg(ctx):
    now = datetime.now(timezone.utc)
    user_id = ctx.author.id
    last = beg_cooldowns.get(user_id)
    if last and now - last < timedelta(minutes=10):
        rem = timedelta(minutes=10) - (now - last)
        await ctx.send(f"{ctx.author.mention}, you can beg again in {str(rem).split('.')[0]}.")
        return
    beg_cooldowns[user_id] = now
    if random.random() < 0.5:
        await ctx.send(f"{ctx.author.mention}, no one gave you anything this time.")
    else:
        amount = random.randint(1, 20)
        change_balance(user_id, amount)
        await ctx.send(f"{ctx.author.mention}, you begged and got {amount} {CURRENCY_NAME}!")

@bot.command()
async def daily(ctx):
    now = datetime.now(timezone.utc)
    user_id = ctx.author.id
    last = daily_cooldowns.get(user_id)
    if last and now - last < timedelta(hours=24):
        rem = timedelta(hours=24) - (now - last)
        await ctx.send(f"{ctx.author.mention}, you can claim your daily reward in {str(rem).split('.')[0]}.")
        return
    change_balance(user_id, 100)
    daily_cooldowns[user_id] = now
    await ctx.send(f"{ctx.author.mention}, you claimed your daily 100 {CURRENCY_NAME}!")

@bot.command()
async def work(ctx):
    now = datetime.now(timezone.utc)
    user_id = ctx.author.id
    last = work_cooldowns.get(user_id)
    if last and now - last < timedelta(minutes=20):
        rem = timedelta(minutes=20) - (now - last)
        await ctx.send(f"{ctx.author.mention}, you can work again in {str(rem).split('.')[0]}.")
        return
    work_cooldowns[user_id] = now
    jobs = ["chef", "barista", "programmer", "driver", "artist", "bjs"]
    job = random.choice(jobs)
    amount = random.randint(10, 50)
    change_balance(user_id, amount)
    await ctx.send(f"{ctx.author.mention}, you worked as a {job} and earned {amount} {CURRENCY_NAME}!")

@bot.command()
async def impregnate(ctx, partner: discord.Member):
    if partner.bot:
        await ctx.send("You cannot impregnate a bot!")
        return
    if partner.id == ctx.author.id:
        await ctx.send("You cannot impregnate yourself!")
        return
    payer_is_author = random.choice([True, False])
    child_support = 50
    payer = ctx.author if payer_is_author else partner
    receiver = partner if payer_is_author else ctx.author
    if get_balance(payer.id) < child_support:
        await ctx.send(f"{payer.mention} does not have enough {CURRENCY_NAME} to pay child support!")
        return
    change_balance(payer.id, -child_support)
    change_balance(receiver.id, child_support)
    await ctx.send(f"{ctx.author.mention} impregnated {partner.mention}!\n{payer.mention} pays {child_support} {CURRENCY_NAME} as child support to {receiver.mention}.")

@bot.command()
async def nuke(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    await ctx.channel.purge(limit=1000)
    await ctx.send("boom")

@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member} for: {reason}")
    except Exception as e:
        await ctx.send(f"Failed to kick: {e}")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    try:
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member} for: {reason}")
    except Exception as e:
        await ctx.send(f"Failed to ban: {e}")

@bot.command()
async def clear(ctx, amount: int = 5):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Cleared {len(deleted)} messages", delete_after=3)

@bot.command()
async def reactionroles(ctx):
    embed = discord.Embed(title="Choose your gender role by reacting", color=0x00ff00)
    embed.description = (
        "React with the emoji to get the role:\n"
        "💙 for mALE\n"
        "💗 for fEMALE\n"
        "🤍 for oTHER (AKS)\n"
        "Remove your reaction to remove the role."
    )
    msg = await ctx.send(embed=embed)
    global ROLE_MESSAGE_ID
    ROLE_MESSAGE_ID = msg.id
    for emoji in EMOJI_TO_ROLE:
        await msg.add_reaction(emoji)

@bot.command()
async def nicki(ctx):
    lyrics = [
        "lIKE mJ dOCTOR, tHEY kILLIN mE. pROPOFOl, i kNOW tHEY hOPE i fALL.bUT tELL eM wINNIN iS mY mUTHUFUCKIN pROTOCOL..",
        "mE, nICKI m, i gOT tOO mANY m'S!!!",
        "aYO tONIGHT iS tHE nIGHT tHAT iMMMA gET tWISTED, mYX mOSCATO n vODKA iMA mIX iT.",
        "yOUR fLOW iS sUCH a bORE...",
        "aND i wILL rETIRE wITH tHE cROWN... yES!",
        "bE wHO yOU iS nEVER bE wHO yOU aRENT nEVA."
    ]
    await ctx.send(random.choice(lyrics))

@bot.command()
async def level(ctx):
    data = get_level(ctx.author.id)
    await ctx.send(f"{ctx.author.mention}, you are level {data['level']} with {data['xp']} XP.")

@bot.command()
async def leaderboard(ctx):
    sorted_users = sorted(user_xp.items(), key=lambda x: x[1]['level'] * 100 + x[1]['xp'], reverse=True)
    top = "Top 5 users:\n"
    for i, (user_id, data) in enumerate(sorted_users[:5]):
        member = ctx.guild.get_member(int(user_id))
        if member:
            top += f"{i+1}. {member.display_name} - Level {data['level']}\n"
    await ctx.send(top)

@bot.command()
async def spotify(ctx, member: discord.Member = None):
    member = member or ctx.author
    for activity in member.activities:
        if isinstance(activity, discord.Spotify):
            embed = discord.Embed(
                title=f"{member.display_name} is listening to Spotify!",
                description=f"**{activity.title}** by {activity.artist}\nAlbum: {activity.album}",
                color=0x1DB954
            )
            embed.set_thumbnail(url=activity.album_cover_url)
            embed.add_field(name="Track URL", value=f"[Open in Spotify](https://open.spotify.com/track/{activity.track_id})")
            await ctx.send(embed=embed)
            return
    await ctx.send(f"{member.display_name} is not listening to Spotify right now.")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is online and commands synced!")
# THis is a test comment

    

bot.run("TOKEN")
