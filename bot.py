# =========================
# Imports and Setup
# =========================
import discord
from discord.ext import commands, tasks
import json
import random
from datetime import datetime, timedelta, timezone as dt_timezone
import pytz
import os
from dotenv import load_dotenv
from discord import app_commands
import time
import requests
import re
import asyncio
import io
from discord.ui import View, Button
import functools

# =========================
# Intents and Bot Instance
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True

# Load config first to get the prefix
load_dotenv()

# We need to initialize the bot early to avoid decorator issues
# We'll set the proper prefix after loading config
bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

# =========================
# Constants and Globals
# =========================
CURRENCY_NAME = "dOLLARIANAS"
DATA_FILE = "balances.json"
XP_FILE = "xp.json"
CONFIG_FILE = "config.json"
BIRTHDAY_FILE = "birthdays.json"
RELATIONSHIPS_FILE = "relationships.json"
REMINDERS_FILE = "reminders.json"
THRIFT_FILE = "thrift.json"
AFK_FILE = "afk.json"
PROFILES_FILE = "profiles.json"
MESSAGE_ACTIVITY_FILE = "message_activity.json"
BCA_NOMINATIONS_FILE = "bca_nominations.json"
BCA_VOTES_FILE = "bca_votes.json"
BCA_CATEGORIES_FILE = "bca_categories.json"
BCA_CHANGES_FILE = "bca_changes.json"
BCA_COUNTDOWNS_FILE = "bca_countdowns.json"
SERVER_CONFIGS_FILE = "server_configs.json"

balances = {}  # guild_id: {user_id: balance}
user_xp = {}  # guild_id: {user_id: xp_data}
config = {}

# Per-server prefixes - loaded from config, defaults to "?"
SERVER_PREFIXES = {}  # guild_id: prefix
DEFAULT_PREFIX = "?"

# Dynamic prefix function
def get_prefix(bot, message):
    """Get the prefix for the current server."""
    if message.guild is None:
        # DMs use default prefix
        return DEFAULT_PREFIX
    
    # Return server-specific prefix or default
    return SERVER_PREFIXES.get(message.guild.id, DEFAULT_PREFIX)

beg_cooldowns = {}
work_cooldowns = {}
daily_cooldowns = {}

# Live countdown message tracking
active_countdown_messages = {}  # message_id: {guild_id, channel_id, event_name, message_obj}

# Background task for live countdown updates
async def countdown_update_loop():
    """Continuously update countdown messages every second"""
    global active_countdown_messages, BCA_COUNTDOWNS
    
    print("🔴 COUNTDOWN UPDATE LOOP STARTED - RUNNING EVERY SECOND")
    
    while True:
        try:
            if active_countdown_messages:
                print(f"DEBUG: Updating {len(active_countdown_messages)} countdown messages...")
                
                messages_to_remove = []
                
                for message_id, data in list(active_countdown_messages.items()):
                    try:
                        guild_id = data['guild_id']
                        event_name = data['event_name']
                        message = data['message_obj']
                        
                        # Get current countdown data
                        server_countdowns = BCA_COUNTDOWNS.get(guild_id, {})
                        if event_name not in server_countdowns:
                            messages_to_remove.append(message_id)
                            continue
                        
                        event_data = server_countdowns[event_name]
                        est = pytz.timezone('US/Eastern')
                        now = datetime.now(est)
                        time_diff = event_data["end_time"] - now
                        
                        if time_diff.total_seconds() <= 0:
                            time_str = "eVENT hAS eNDED!"
                            messages_to_remove.append(message_id)
                        else:
                            days = time_diff.days
                            hours, remainder = divmod(time_diff.seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            time_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
                        
                        # Update the embed
                        description = f"{event_data['description']}\n\n⏱️ **tIME rEMAINING:** **{time_str}**"
                        embed = nova_embed(f"⏰ {event_name}", description)
                        
                        # Edit the message
                        await message.edit(embed=embed)
                        print(f"✅ Updated countdown for {event_name}")
                        
                    except Exception as e:
                        print(f"❌ Error updating countdown message {message_id}: {e}")
                        messages_to_remove.append(message_id)
                
                # Remove failed/ended messages
                for message_id in messages_to_remove:
                    if message_id in active_countdown_messages:
                        del active_countdown_messages[message_id]
                        print(f"🗑️ Removed countdown message {message_id} from tracking")
            
            # Wait 1 second before next update
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Error in countdown update loop: {e}")
            await asyncio.sleep(1)

OWNER_ID = 755846396208218174

# Server restriction - Set to your server ID
ALLOWED_SERVER_ID = None  # Allow bot to work in any server

ROLE_MESSAGE_ID = None
EMOJI_TO_ROLE = {
    "💙": "mALE",
    "💗": "fEMALE",
    "🤍": "oTHER (AKS)"
}

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# AFK system
AFK_STATUS = {}  # user_id: {"reason": str, "since": datetime, "mentions": set(user_id)}

# Auto-reaction system
AUTO_REACTIONS = {}  # trigger_word: emoji

# Command disabling system
DISABLED_COMMANDS = set()  # Set of disabled command names

# Message activity tracking system
MESSAGE_ACTIVITY = {}  # guild_id: {user_id: [{"timestamp": datetime, "count": int}]}

# Runway system
RUNWAY_CHANNEL_ID = None  # Set this to your runway channel ID

# Centralized server logging system
CENTRAL_LOG_GUILD_ID = None  # Set to your logging server ID
CENTRAL_OVERVIEW_CHANNEL_ID = None  # Master overview channel for joins/leaves
CENTRAL_ARCHIVE_CATEGORY_ID = None  # Category for archived server logs

# Chat logs system
CHAT_LOGS_CHANNEL_ID = None  # Set by ?setchatlogs

# Rules channel system
RULES_CHANNEL_ID = None  # Set by ?setruleschannel

# New logging systems
JOIN_LEAVE_LOGS_CHANNEL_ID = None  # Set by ?setjoinleavelogs
SERVER_LOGS_CHANNEL_ID = None  # Set by ?setserverlogs
MOD_LOGS_CHANNEL_ID = None  # Set by ?setmodlogs

# BCA (Brabz Choice Awards) system
BCA_NOMINATIONS_CHANNEL_ID = None  # Set by ?setbcanominations
BCA_NOMINATIONS_LOGS_CHANNEL_ID = None  # Set by ?setbcanominationslogs
BCA_VOTING_CHANNEL_ID = None  # Set by ?setbcavoting
BCA_VOTING_LOGS_CHANNEL_ID = None  # Set by ?setbcavotinglogs
BCA_CATEGORIES = {}  # guild_id: {category_name: {"allow_self_nomination": bool}}
BCA_NOMINATIONS = {}  # guild_id: {category: {user_id: {"nominee": user_id, "nominator": user_id}}}
BCA_VOTES = {}  # guild_id: {category: {user_id: nominee_id}}
BCA_CHANGES = {}  # guild_id: {user_id: {"nomination_changed": bool, "vote_changed": bool}}
BCA_COUNTDOWNS = {}  # guild_id: {event_name: {"end_time": datetime, "description": str}}
SERVER_CONFIGS = {}  # guild_id: {"chat_logs": channel_id, "server_logs": channel_id, etc.}
BCA_NOMINATION_DEADLINE = None  # datetime when nominations close
BCA_VOTING_DEADLINE = None  # datetime when voting closes

# International days dictionary (all 365 days, placeholder names)
INTERNATIONAL_DAYS = {
    "04-01": "wORLD bRAILLE dAY",
    "24-01": "iNTERNATIONAL dAY oF eDUCATION",
    "26-01": "iNTERNATIONAL dAY oF cLEAN eNERGY",
    "27-01": "iNTERNATIONAL dAY oF cOMMEMORATION iN mEMORY oF tHE vICTIMS oF tHE hOLOCAUST",
    "28-01": "iNTERNATIONAL dAY oF pEACEFUL cOEXISTENCE",
    "01-02": "wORLD iNTERFAITH hARMONY wEEK (1-7 fEBRUARY)",
    "02-02": "wORLD wETLANDS dAY",
    "04-02": "iNTERNATIONAL dAY oF hUMAN fRATERNITY",
    "06-02": "iNTERNATIONAL dAY oF zERO tOLERANCE tO fEMALE gENITAL mUTILATION",
    "10-02": "wORLD pULSES dAY",
    "11-02": "iNTERNATIONAL dAY oF wOMEN aND gIRLS iN sCIENCE",
    "12-02": "iNTERNATIONAL dAY fOR tHE pREVENTION oF vIOLENT eXTREMISM aS aND wHEN cONDUCIVE tO tERRORISM",
    "13-02": "wORLD rADIO dAY",
    "17-02": "gLOBAL tOURISM rESILIENCE dAY",
    "20-02": "wORLD dAY oF sOCIAL jUSTICE",
    "21-02": "iNTERNATIONAL mOTHER lANGUAGE dAY",
    "01-03": "zERO dISCRIMINATION dAY",
    "03-03": "wORLD wILDLIFE dAY",
    "05-03": "iNTERNATIONAL dAY fOR dISARMAMENT aND nON-pROLIFERATION aWARENESS",
    "08-03": "iNTERNATIONAL wOMEN'S dAY",
    "10-03": "iNTERNATIONAL dAY oF wOMEN jUDGES",
    "15-03": "iNTERNATIONAL dAY tO cOMBAT iSLAMOPHOBIA",
    "20-03": "iNTERNATIONAL dAY oF hAPPINESS",
    "21-03": "wORLD dAY fOR gLACIERS",
    "22-03": "wORLD wATER dAY",
    "23-03": "wORLD mETEOROLOGICAL dAY",
    "24-03": "wORLD tUBERCULOSIS dAY",
    "25-03": "iNTERNATIONAL dAY oF rEMEMBRANCE oF tHE vICTIMS oF sLAVERY aND tHE tRANSATLANTIC sLAVE tRADE",
    "30-03": "iNTERNATIONAL dAY oF zERO wASTE",
    "02-04": "wORLD aUTISM aWARENESS dAY",
    "04-04": "iNTERNATIONAL dAY fOR mINE aWARENESS aND aSSISTANCE iN mINE aCTION",
    "05-04": "iNTERNATIONAL dAY oF cONSCIENCE",
    "06-04": "iNTERNATIONAL dAY oF sPORT fOR dEVELOPMENT aND pEACE",
    "07-04": "wORLD hEALTH dAY",
    "12-04": "iNTERNATIONAL dAY oF hUMAN sPACE fLIGHT",
    "14-04": "wORLD cHAGAS dISEASE dAY",
    "20-04": "cHINESE lANGUAGE dAY",
    "21-04": "wORLD cREATIVITY aND iNNOVATION dAY",
    "22-04": "iNTERNATIONAL mOTHER eARTH dAY",
    "23-04": "wORLD bOOK aND cOPYRIGHT dAY",
    "24-04": "iNTERNATIONAL gIRLS iN iCT dAY",
    "25-04": "wORLD mALARIA dAY",
    "26-04": "iNTERNATIONAL cHERNOBYL dISASTER rEMEMBRANCE dAY",
    "28-04": "wORLD dAY fOR sAFETY aND hEALTH aT wORK",
    "29-04": "iNTERNATIONAL dAY iN mEMORY oF tHE vICTIMS oF eARTHQUAKES",
    "30-04": "iNTERNATIONAL jAZZ dAY",
    "02-05": "wORLD tUNA dAY",
    "03-05": "wORLD pRESS fREEDOM dAY",
    "05-05": "wORLD pORTUGUESE lANGUAGE dAY",
    "08-05": "tIME oF rEMEMBRANCE aND rECONCILIATION fOR tHOSE wHO lOST tHEIR lIVES dURING tHE sECOND wORLD wAR",
    "10-05": "iNTERNATIONAL dAY oF aRGANIA",
    "12-05": "uN gLOBAL rOAD sAFETY wEEK",
    "15-05": "iNTERNATIONAL dAY oF lIVING tOGETHER iN pEACE",
    "16-05": "iNTERNATIONAL dAY oF lIGHT",
    "17-05": "wORLD fAIR pLAY dAY",
    "19-05": "wORLD bEE dAY",
    "20-05": "iNTERNATIONAL tEA dAY",
    "21-05": "wORLD dAY fOR cULTURAL dIVERSITY fOR dIALOGUE aND dEVELOPMENT",
    "22-05": "iNTERNATIONAL dAY fOR bIOLOGICAL dIVERSITY",
    "23-05": "iNTERNATIONAL dAY tO eND oBSTETRIC fISTULA",
    "24-05": "iNTERNATIONAL dAY oF tHE mARKHOR",
    "25-05": "wORLD fOOTBALL dAY",
    "29-05": "iNTERNATIONAL dAY oF uN pEACEKEEPERS",
    "30-05": "iNTERNATIONAL dAY oF pOTATO",
    "31-05": "wORLD nO-tOBACCO dAY",
    "01-06": "gLOBAL dAY oF pARENTS",
    "03-06": "wORLD bICYCLE dAY",
    "04-06": "iNTERNATIONAL dAY oF iNNOCENT cHILDREN vICTIMS oF aGGRESSION",
    "05-06": "wORLD eNVIRONMENT dAY",
    "06-06": "rUSSIAN lANGUAGE dAY",
    "07-06": "wORLD fOOD sAFETY dAY",
    "08-06": "wORLD oCEANS dAY",
    "10-06": "iNTERNATIONAL dAY fOR dIALOGUE aMONG cIVILIZATIONS",
    "11-06": "iNTERNATIONAL dAY oF pLAY",
    "12-06": "wORLD dAY aGAINST cHILD lABOUR",
    "13-06": "iNTERNATIONAL aLBINISM aWARENESS dAY",
    "14-06": "wORLD bLOOD dONOR dAY",
    "15-06": "wORLD eLDER aBUSE aWARENESS dAY",
    "16-06": "iNTERNATIONAL dAY oF fAMILY rEMITTANCES",
    "17-06": "wORLD dAY tO cOMBAT dESERTIFICATION aND dROUGHT",
    "18-06": "sUSTAINABLE gASTRONOMY dAY",
    "19-06": "iNTERNATIONAL dAY fOR tHE eLIMINATION oF sEXUAL vIOLENCE iN cONFLICT",
    "20-06": "wORLD rEFUGEE dAY",
    "21-06": "iNTERNATIONAL dAY oF yOGA",
    "23-06": "uN pUBLIC sERVICE dAY",
    "24-06": "iNTERNATIONAL dAY oF wOMEN iN dIPLOMACY",
    "25-06": "dAY oF tHE sEAFARER",
    "26-06": "iNTERNATIONAL dAY aGAINST dRUG aBUSE aND iLLICIT tRAFFICKING",
    "27-06": "iNTERNATIONAL dAY oF dEAFBLINDNESS",
    "29-06": "iNTERNATIONAL dAY oF tHE tROPICS",
    "30-06": "iNTERNATIONAL aSTEROID dAY",
    "05-07": "iNTERNATIONAL dAY oF cOOPERATIVES",
    "06-07": "wORLD rURAL dEVELOPMENT dAY",
    "07-07": "wORLD kISWAHILI lANGUAGE dAY",
    "11-07": "wORLD hORSE dAY",
    "12-07": "iNTERNATIONAL dAY oF cOMbATING sAND aND dUST sTORMS",
    "15-07": "nELSON mANDELA iNTERNATIONAL dAY",
    "18-07": "wORLD cHESS dAY",
    "20-07": "iNTERNATIONAL mOON dAY",
    "25-07": "wORLD dROWNING pREVENTION dAY",
    "28-07": "wORLD hEPATITIS dAY",
    "30-07": "iNTERNATIONAL dAY oF fRIENDSHIP",
    "01-08": "wORLD bREASTFEEDING wEEK",
    "09-08": "iNTERNATIONAL dAY oF tHE wORLD'S iNDIGENOUS pEOPLES",
    "11-08": "wORLD sTEELPAN dAY",
    "12-08": "iNTERNATIONAL yOUTH dAY",
    "19-08": "wORLD hUMANITARIAN dAY",
    "21-08": "iNTERNATIONAL dAY oF rEMEMBRANCE aND tRIBUTE tO tHE vICTIMS oF tERRORISM",
    "22-08": "iNTERNATIONAL dAY cOMMEMORATING tHE vICTIMS oF aCTS oF vIOLENCE bASED oN rELIGION oR bELIEF",
    "23-08": "wORLD lAKE dAY",
    "27-08": "iNTERNATIONAL dAY aGAINST nUCLEAR tESTS",
    "29-08": "iNTERNATIONAL dAY oF tHE vICTIMS oF eNFORCED dISAPPEARANCES",
    "30-08": "iNTERNATIONAL dAY fOR pEOPLE oF aFRICAN dESCENT",
    "31-08": "iNTERNATIONAL dAY 243",
    "02-11": "iNTERNATIONAL dAY tO eND iMPUNITY fOR cRIMES aGAINST jOURNALISTS",
    "05-11": "wORLD tSUNAMI aWARENESS dAY",
    "06-11": "iNTERNATIONAL dAY fOR pREVENTING tHE eXPLOITATION oF tHE eNVIRONMENT iN wAR aND aRMED cONFLICT",
    "09-11": "wORLD sCIENCE dAY fOR pEACE aND dEVELOPMENT",
    "10-11": "wORLD dIABETES dAY",
    "14-11": "iNTERNATIONAL dAY fOR tHE pREVENTION oF aND fIGHT aGAINST aLL fORMS oF tRANSNATIONAL oRGANIZED cRIME",
    "15-11": "iNTERNATIONAL dAY fOR tOLERANCE",
    "16-11": "wORLD dAY oF rEMEMBRANCE fOR rOAD tRAFFIC vICTIMS",
    "18-11": "wORLD tOILET dAY",
    "19-11": "wORLD pHILOSOPHY dAY",
    "20-11": "wORLD cHILDREN'S dAY",
    "21-11": "wORLD cONJOINED tWINS dAY",
    "24-11": "iNTERNATIONAL dAY fOR tHE eLIMINATION oF vIOLENCE aGAINST wOMEN",
    "25-11": "wORLD sUSTAINABLE tRANSPORT dAY",
    "26-11": "iNTERNATIONAL dAY oF sOLIDARITY wITH tHE pALESTINIAN pEOPLE",
    "29-11": "dAY oF rEMEMBRANCE fOR aLL vICTIMS oF cHEMICAL wARFARE",
    "30-11": "iNTERNATIONAL dAY 334",
    "01-12": "wORLD aIDS dAY",
    "02-12": "iNTERNATIONAL dAY fOR tHE aBOLITION oF sLAVERY",
    "03-12": "iNTERNATIONAL dAY oF pERSONS wITH dISABILITIES",
    "04-12": "iNTERNATIONAL dAY oF bANKS",
    "05-12": "iNTERNATIONAL dAY aGAINST uNILATERAL cOERCIVE mEASURES",
    "07-12": "wORLD sOIL dAY",
    "09-12": "iNTERNATIONAL dAY oF cOMMEMORATION aND dIGNITY oF tHE vICTIMS oF tHE cRIME oF gENOCIDE aND oF tHE pREVENTION oF tHIS cRIME",
    "10-12": "hUMAN rIGHTS dAY",
    "11-12": "iNTERNATIONAL mOUNTAIN dAY",
    "12-12": "iNTERNATIONAL dAY oF nEUTRALITY",
    "18-12": "iNTERNATIONAL mIGRANTS dAY",
    "20-12": "iNTERNATIONAL hUMAN sOLIDARITY dAY",
    "21-12": "wORLD mEDITATION dAY",
    "27-12": "iNTERNATIONAL dAY oF ePIDEMIC pREPAREDNESS",
    "25-12": "cHRISTMAS dAY"
}

# =========================
# Helper Functions
# =========================

def load_config():
    """Load configuration from CONFIG_FILE into the global config dict."""
    global config, SERVER_PREFIXES, CHAT_LOGS_CHANNEL_ID, RULES_CHANNEL_ID, WELCOME_CHANNEL_ID, FAREWELL_CHANNEL_ID, RUNWAY_CHANNEL_ID, TICKET_CATEGORY_ID, SUPPORT_ROLE_ID, TICKET_LOGS_CHANNEL_ID, JOIN_LEAVE_LOGS_CHANNEL_ID, SERVER_LOGS_CHANNEL_ID, MOD_LOGS_CHANNEL_ID, BCA_NOMINATIONS_CHANNEL_ID, BCA_NOMINATIONS_LOGS_CHANNEL_ID, BCA_VOTING_CHANNEL_ID, BCA_VOTING_LOGS_CHANNEL_ID, BCA_CATEGORIES, BCA_NOMINATIONS, BCA_VOTES, BCA_COUNTDOWNS, BCA_NOMINATION_DEADLINE, BCA_VOTING_DEADLINE, CENTRAL_LOG_GUILD_ID, CENTRAL_OVERVIEW_CHANNEL_ID, CENTRAL_ARCHIVE_CATEGORY_ID, SERVER_CONFIGS
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Load server prefixes (convert string keys to int)
            prefix_data = config.get("server_prefixes", {})
            SERVER_PREFIXES = {int(guild_id): prefix for guild_id, prefix in prefix_data.items()}
            # Legacy global channels (kept for backward compatibility)
            CHAT_LOGS_CHANNEL_ID = config.get("chat_logs_channel_id")
            RULES_CHANNEL_ID = config.get("rules_channel_id")
            WELCOME_CHANNEL_ID = config.get("welcome_channel_id")
            FAREWELL_CHANNEL_ID = config.get("farewell_channel_id")
            RUNWAY_CHANNEL_ID = config.get("runway_channel_id")
            TICKET_CATEGORY_ID = config.get("ticket_category_id")
            SUPPORT_ROLE_ID = config.get("support_role_id")
            TICKET_LOGS_CHANNEL_ID = config.get("ticket_logs_channel_id")
            JOIN_LEAVE_LOGS_CHANNEL_ID = config.get("join_leave_logs_channel_id")
            SERVER_LOGS_CHANNEL_ID = config.get("server_logs_channel_id")
            MOD_LOGS_CHANNEL_ID = config.get("mod_logs_channel_id")
            BCA_NOMINATIONS_CHANNEL_ID = config.get("bca_nominations_channel_id")
            BCA_NOMINATIONS_LOGS_CHANNEL_ID = config.get("bca_nominations_logs_channel_id")
            BCA_VOTING_CHANNEL_ID = config.get("bca_voting_channel_id")
            BCA_VOTING_LOGS_CHANNEL_ID = config.get("bca_voting_logs_channel_id")
            # Load centralized logging config
            CENTRAL_LOG_GUILD_ID = config.get("central_log_guild_id")
            CENTRAL_OVERVIEW_CHANNEL_ID = config.get("central_overview_channel_id")
            CENTRAL_ARCHIVE_CATEGORY_ID = config.get("central_archive_category_id")
            # Load BCA data from files
            BCA_CATEGORIES = load_bca_categories()
            BCA_NOMINATIONS = load_bca_nominations()
            BCA_VOTES = load_bca_votes()
            BCA_CHANGES = load_bca_changes()
            BCA_COUNTDOWNS = load_bca_countdowns()
            SERVER_CONFIGS = load_server_configs()
            # Load BCA deadlines
            BCA_NOMINATION_DEADLINE = datetime.fromisoformat(config.get("bca_nomination_deadline")) if config.get("bca_nomination_deadline") else None
            BCA_VOTING_DEADLINE = datetime.fromisoformat(config.get("bca_voting_deadline")) if config.get("bca_voting_deadline") else None
    except FileNotFoundError:
        config = {"mod_role_id": None, "admin_role_id": None, "server_prefixes": {}, "chat_logs_channel_id": None, "rules_channel_id": None, "welcome_channel_id": None, "farewell_channel_id": None, "runway_channel_id": None, "ticket_category_id": None, "support_role_id": None, "ticket_logs_channel_id": None, "join_leave_logs_channel_id": None, "server_logs_channel_id": None, "mod_logs_channel_id": None}
        SERVER_PREFIXES = {}
        CHAT_LOGS_CHANNEL_ID = None
        RULES_CHANNEL_ID = None
        WELCOME_CHANNEL_ID = None
        FAREWELL_CHANNEL_ID = None
        RUNWAY_CHANNEL_ID = None
        TICKET_CATEGORY_ID = None
        SUPPORT_ROLE_ID = None
        TICKET_LOGS_CHANNEL_ID = None
        JOIN_LEAVE_LOGS_CHANNEL_ID = None
        SERVER_LOGS_CHANNEL_ID = None
        MOD_LOGS_CHANNEL_ID = None
        BCA_NOMINATIONS_CHANNEL_ID = None
        BCA_NOMINATIONS_LOGS_CHANNEL_ID = None
        BCA_VOTING_CHANNEL_ID = None
        BCA_VOTING_LOGS_CHANNEL_ID = None
        BCA_CATEGORIES = {}
        BCA_NOMINATIONS = {}
        BCA_VOTES = {}
        BCA_COUNTDOWNS = {}
        SERVER_CONFIGS = {}
        BCA_NOMINATION_DEADLINE = None
        BCA_VOTING_DEADLINE = None

# Initialize bot after loading config
def init_bot():
    """Update the bot's prefix function after loading config."""
    global bot
    # Update the bot's command prefix to use the dynamic prefix function
    bot.command_prefix = get_prefix

def save_config():
    """Save the current config dict to CONFIG_FILE."""
    global SERVER_PREFIXES, CHAT_LOGS_CHANNEL_ID, RULES_CHANNEL_ID, WELCOME_CHANNEL_ID, FAREWELL_CHANNEL_ID, RUNWAY_CHANNEL_ID, TICKET_CATEGORY_ID, SUPPORT_ROLE_ID, TICKET_LOGS_CHANNEL_ID, JOIN_LEAVE_LOGS_CHANNEL_ID, SERVER_LOGS_CHANNEL_ID, MOD_LOGS_CHANNEL_ID, BCA_NOMINATIONS_CHANNEL_ID, BCA_NOMINATIONS_LOGS_CHANNEL_ID, BCA_VOTING_CHANNEL_ID, BCA_VOTING_LOGS_CHANNEL_ID, BCA_NOMINATION_DEADLINE, BCA_VOTING_DEADLINE
    # Save server prefixes (convert int keys to string for JSON)
    config["server_prefixes"] = {str(guild_id): prefix for guild_id, prefix in SERVER_PREFIXES.items()}
    config["chat_logs_channel_id"] = CHAT_LOGS_CHANNEL_ID
    config["rules_channel_id"] = RULES_CHANNEL_ID
    config["welcome_channel_id"] = WELCOME_CHANNEL_ID
    config["farewell_channel_id"] = FAREWELL_CHANNEL_ID
    config["runway_channel_id"] = RUNWAY_CHANNEL_ID
    config["ticket_category_id"] = TICKET_CATEGORY_ID
    config["support_role_id"] = SUPPORT_ROLE_ID
    config["ticket_logs_channel_id"] = TICKET_LOGS_CHANNEL_ID
    config["join_leave_logs_channel_id"] = JOIN_LEAVE_LOGS_CHANNEL_ID
    config["server_logs_channel_id"] = SERVER_LOGS_CHANNEL_ID
    config["mod_logs_channel_id"] = MOD_LOGS_CHANNEL_ID
    config["bca_nominations_channel_id"] = BCA_NOMINATIONS_CHANNEL_ID
    config["bca_nominations_logs_channel_id"] = BCA_NOMINATIONS_LOGS_CHANNEL_ID
    config["bca_voting_channel_id"] = BCA_VOTING_CHANNEL_ID
    config["bca_voting_logs_channel_id"] = BCA_VOTING_LOGS_CHANNEL_ID
    config["bca_nomination_deadline"] = BCA_NOMINATION_DEADLINE.isoformat() if BCA_NOMINATION_DEADLINE else None
    config["bca_voting_deadline"] = BCA_VOTING_DEADLINE.isoformat() if BCA_VOTING_DEADLINE else None
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_balances():
    """Load user balances from DATA_FILE into the global balances dict."""
    global balances
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Handle both old format (global) and new format (per-server)
            if data and isinstance(list(data.values())[0], (int, float)):
                # Old format - migrate to new format under a default guild
                print("Migrating old balance format to server-specific format")
                balances = {"global": data}
            else:
                # New format - per server, convert string keys to integers
                balances = {}
                for guild_id, guild_balances in data.items():
                    balances[int(guild_id)] = guild_balances
    except FileNotFoundError:
        balances = {}

def save_balances():
    """Save the current balances dict to DATA_FILE."""
    with open(DATA_FILE, "w") as f:
        # Convert integer keys to strings for JSON
        data = {}
        for guild_id, guild_balances in balances.items():
            data[str(guild_id)] = guild_balances
        json.dump(data, f)

def get_balance(user_id, guild_id):
    """Get the balance for a user by their ID in a specific server."""
    guild_balances = balances.get(guild_id, {})
    return guild_balances.get(str(user_id), 0)

def change_balance(user_id, amount, guild_id):
    """Change a user's balance by a given amount in a specific server. Prevents negative balances."""
    user_id = str(user_id)
    
    # Initialize guild balances if not exists
    if guild_id not in balances:
        balances[guild_id] = {}
    
    # Update balance
    balances[guild_id][user_id] = balances[guild_id].get(user_id, 0) + amount
    if balances[guild_id][user_id] < 0:
        balances[guild_id][user_id] = 0
    save_balances()

def load_xp():
    """Load user XP data from XP_FILE into the global user_xp dict."""
    global user_xp
    try:
        with open(XP_FILE, "r") as f:
            user_xp = json.load(f)
    except FileNotFoundError:
        user_xp = {}

def save_xp():
    """Save the current user_xp dict to XP_FILE."""
    with open(XP_FILE, "w") as f:
        json.dump(user_xp, f)

def add_xp(user_id, amount):
    """Add XP to a user and handle level-ups."""
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
    """Get the level and XP for a user by their ID."""
    return user_xp.get(str(user_id), {"xp": 0, "level": 1})

def has_mod_or_admin(ctx):
    """Check if the user has mod or admin privileges, is the bot owner, or is the server owner."""
    print(f"\n=== PERMISSION DEBUG ===")
    print(f"User: {ctx.author} (ID: {ctx.author.id})")
    print(f"Guild: {ctx.guild.name if ctx.guild else 'None'} (ID: {ctx.guild.id if ctx.guild else 'None'})")
    print(f"Guild Owner ID: {ctx.guild.owner_id if ctx.guild else 'None'}")
    print(f"Bot Owner ID: {OWNER_ID}")
    print(f"User has admin perms: {ctx.author.guild_permissions.administrator if ctx.guild else 'No guild'}")
    
    # Check if user is the bot owner
    if ctx.author.id == OWNER_ID:
        print(f"✅ User is bot owner")
        return True
    
    # Check if user is the server owner
    if ctx.guild and ctx.author.id == ctx.guild.owner_id:
        print(f"✅ User is server owner")
        return True
    
    # Check if user has administrator permissions
    if ctx.author.guild_permissions.administrator:
        print(f"✅ User has administrator permissions")
        return True
    
    # Check for specific mod/admin roles using server-specific config
    if ctx.guild:
        mod_role_id = get_server_config(ctx.guild.id, "mod_role_id")
        admin_role_id = get_server_config(ctx.guild.id, "admin_role_id")
        user_role_ids = [role.id for role in ctx.author.roles]
        
        print(f"Server-specific mod_role_id: {mod_role_id}")
        print(f"Server-specific admin_role_id: {admin_role_id}")
        print(f"User role IDs: {user_role_ids}")
        
        has_role = (mod_role_id and mod_role_id in user_role_ids) or (admin_role_id and admin_role_id in user_role_ids)
        print(f"Has mod/admin role: {has_role}")
        
        if has_role:
            print(f"✅ User has mod/admin role")
            return True
    
    print(f"❌ Permission denied")
    print(f"========================\n")
    
    return False

def load_birthdays():
    try:
        with open(BIRTHDAY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_birthdays(birthdays):
    with open(BIRTHDAY_FILE, "w") as f:
        json.dump(birthdays, f)

# Nova embed helper

def nova_embed(title, description=None, color=0xff69b4, footer="nOVA"):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=footer)
    return embed

# Birthday format helper
def format_birthday(date_str):
    """Convert DD-MM format to readable format like 'June 9th'"""
    try:
        day, month = map(int, date_str.split("-"))
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        # Add ordinal suffix to day
        if 10 <= day % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        
        return f"{months[month-1]} {day}{suffix}"
    except:
        return date_str  # Return original if parsing fails

# AFK system persistence
def load_afk():
    """Load AFK status from AFK_FILE into the global AFK_STATUS dict."""
    global AFK_STATUS
    try:
        with open(AFK_FILE, "r") as f:
            data = json.load(f)
            # Convert string keys back to int and datetime strings back to datetime objects
            AFK_STATUS = {}
            for user_id_str, afk_data in data.items():
                user_id = int(user_id_str)
                AFK_STATUS[user_id] = {
                    "reason": afk_data["reason"],
                    "since": datetime.fromisoformat(afk_data["since"]),
                    "mentions": set(afk_data.get("mentions", []))
                }
    except FileNotFoundError:
        AFK_STATUS = {}

def save_afk():
    """Save the current AFK_STATUS dict to AFK_FILE."""
    # Convert datetime objects to ISO format strings and sets to lists for JSON serialization
    data = {}
    for user_id, afk_data in AFK_STATUS.items():
        data[str(user_id)] = {
            "reason": afk_data["reason"],
            "since": afk_data["since"].isoformat(),
            "mentions": list(afk_data["mentions"])
        }
    with open(AFK_FILE, "w") as f:
        json.dump(data, f)

def load_profiles():
    try:
        with open(PROFILES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_profiles(profiles):
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

# Message Activity Functions
def load_message_activity():
    """Load message activity data from MESSAGE_ACTIVITY_FILE."""
    global MESSAGE_ACTIVITY
    try:
        with open(MESSAGE_ACTIVITY_FILE, "r") as f:
            data = json.load(f)
            MESSAGE_ACTIVITY = {}
            for guild_id_str, guild_data in data.items():
                guild_id = int(guild_id_str)
                MESSAGE_ACTIVITY[guild_id] = {}
                for user_id_str, user_messages in guild_data.items():
                    user_id = int(user_id_str)
                    MESSAGE_ACTIVITY[guild_id][user_id] = []
                    for msg_data in user_messages:
                        MESSAGE_ACTIVITY[guild_id][user_id].append({
                            "timestamp": datetime.fromisoformat(msg_data["timestamp"]),
                            "count": msg_data["count"]
                        })
    except FileNotFoundError:
        MESSAGE_ACTIVITY = {}
    except Exception as e:
        print(f"Error loading message activity: {e}")
        MESSAGE_ACTIVITY = {}

def save_message_activity():
    """Save message activity data to MESSAGE_ACTIVITY_FILE."""
    try:
        data = {}
        for guild_id, guild_data in MESSAGE_ACTIVITY.items():
            data[str(guild_id)] = {}
            for user_id, user_messages in guild_data.items():
                data[str(guild_id)][str(user_id)] = []
                for msg_data in user_messages:
                    data[str(guild_id)][str(user_id)].append({
                        "timestamp": msg_data["timestamp"].isoformat(),
                        "count": msg_data["count"]
                    })
        
        with open(MESSAGE_ACTIVITY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving message activity: {e}")

def track_message(guild_id, user_id):
    """Track a message for activity statistics."""
    if guild_id not in MESSAGE_ACTIVITY:
        MESSAGE_ACTIVITY[guild_id] = {}
    
    if user_id not in MESSAGE_ACTIVITY[guild_id]:
        MESSAGE_ACTIVITY[guild_id][user_id] = []
    
    now = datetime.now(dt_timezone.utc)
    user_messages = MESSAGE_ACTIVITY[guild_id][user_id]
    
    # Check if we have a recent entry (within the last hour) to batch messages
    if user_messages and (now - user_messages[-1]["timestamp"]).total_seconds() < 3600:
        # Update the most recent entry
        user_messages[-1]["count"] += 1
        user_messages[-1]["timestamp"] = now
    else:
        # Create a new entry
        user_messages.append({
            "timestamp": now,
            "count": 1
        })
    
    # Clean up old entries (older than 1 year) to keep file size manageable
    one_year_ago = now - timedelta(days=365)
    MESSAGE_ACTIVITY[guild_id][user_id] = [
        msg for msg in user_messages if msg["timestamp"] > one_year_ago
    ]
    
    # Save periodically (every 10th message to avoid constant file writes)
    import random
    if random.randint(1, 10) == 1:
        save_message_activity()

# BCA System Data Functions
def load_bca_categories():
    try:
        with open(BCA_CATEGORIES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bca_categories(categories):
    with open(BCA_CATEGORIES_FILE, "w") as f:
        json.dump(categories, f, indent=2)

def load_bca_nominations():
    try:
        with open(BCA_NOMINATIONS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bca_nominations(nominations):
    with open(BCA_NOMINATIONS_FILE, "w") as f:
        json.dump(nominations, f, indent=2)

def load_bca_votes():
    try:
        with open(BCA_VOTES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bca_votes(votes):
    with open(BCA_VOTES_FILE, "w") as f:
        json.dump(votes, f, indent=2)

def load_bca_changes():
    try:
        with open(BCA_CHANGES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bca_changes(changes):
    with open(BCA_CHANGES_FILE, "w") as f:
        json.dump(changes, f, indent=2)

def load_bca_countdowns():
    try:
        with open(BCA_COUNTDOWNS_FILE, "r") as f:
            data = json.load(f)
            # Convert ISO strings back to timezone-aware datetime objects
            est = pytz.timezone('US/Eastern')
            result = {}
            
            # Handle both old format (global) and new format (per-server)
            if data and isinstance(list(data.values())[0], dict) and "end_time" in list(data.values())[0]:
                # Old format - migrate to new format under a default guild
                print("Migrating old countdown format to server-specific format")
                result["global"] = {}
                for event_name, event_data in data.items():
                    try:
                        end_time = datetime.fromisoformat(event_data["end_time"])
                        if end_time.tzinfo is None:
                            end_time = est.localize(end_time)
                        result["global"][event_name] = {
                            "end_time": end_time,
                            "description": event_data["description"]
                        }
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Could not parse countdown time for '{event_name}': {e}")
                        continue
            else:
                # New format - per server
                for guild_id, guild_countdowns in data.items():
                    # Handle both string guild IDs and 'global' key
                    if guild_id == "global":
                        result["global"] = {}
                        guild_key = "global"
                    else:
                        try:
                            guild_key = int(guild_id)
                            result[guild_key] = {}
                        except ValueError:
                            print(f"Warning: Invalid guild_id '{guild_id}', skipping")
                            continue
                    
                    for event_name, event_data in guild_countdowns.items():
                        try:
                            end_time = datetime.fromisoformat(event_data["end_time"])
                            if end_time.tzinfo is None:
                                end_time = est.localize(end_time)
                            result[int(guild_id)][event_name] = {
                                "end_time": end_time,
                                "description": event_data["description"]
                            }
                        except (ValueError, TypeError) as e:
                            print(f"Warning: Could not parse countdown time for '{event_name}' in guild {guild_id}: {e}")
                            continue
            return result
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading BCA countdowns: {e}")
        return {}

def save_bca_countdowns(countdowns):
    with open(BCA_COUNTDOWNS_FILE, "w") as f:
        # Convert datetime objects to ISO strings for JSON serialization
        data = {}
        for guild_id, guild_countdowns in countdowns.items():
            data[str(guild_id)] = {}
            for event_name, event_data in guild_countdowns.items():
                end_time = event_data["end_time"]
                # Handle both timezone-aware and naive datetime objects
                if hasattr(end_time, 'isoformat'):
                    end_time_str = end_time.isoformat()
                else:
                    end_time_str = str(end_time)
                
                data[str(guild_id)][event_name] = {
                    "end_time": end_time_str,
                    "description": event_data["description"]
                }
        json.dump(data, f, indent=2)

def load_server_configs():
    """Load server-specific configurations"""
    try:
        with open(SERVER_CONFIGS_FILE, "r") as f:
            data = json.load(f)
            # Convert string keys back to integers
            result = {}
            for guild_id, config in data.items():
                result[int(guild_id)] = config
            return result
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading server configs: {e}")
        return {}

def save_server_configs(configs):
    """Save server-specific configurations"""
    try:
        with open(SERVER_CONFIGS_FILE, "w") as f:
            # Convert integer keys to strings for JSON
            data = {}
            for guild_id, config in configs.items():
                data[str(guild_id)] = config
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving server configs: {e}")

def get_server_config(guild_id, key, default=None):
    """Get a specific config value for a server"""
    global SERVER_CONFIGS
    return SERVER_CONFIGS.get(guild_id, {}).get(key, default)

def set_server_config(guild_id, key, value):
    """Set a specific config value for a server"""
    global SERVER_CONFIGS
    if guild_id not in SERVER_CONFIGS:
        SERVER_CONFIGS[guild_id] = {}
    SERVER_CONFIGS[guild_id][key] = value
    save_server_configs(SERVER_CONFIGS)

# Example usage in commands:
# await ctx.send(embed=nova_embed("TITLE", "description"))
# await interaction.response.send_message(embed=nova_embed("TITLE", "description"))

# =========================
# Centralized Logging Functions
# =========================

def sanitize_server_name(server_name):
    """Sanitize server name for use in Discord channel/category names."""
    # Remove invalid characters and limit length
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9\s-]', '', server_name)
    sanitized = re.sub(r'\s+', '-', sanitized.strip())
    return sanitized.lower()[:50]  # Discord limit is 100, but keep it shorter

async def create_server_logging_category(guild_info):
    """Create a logging category and channels for a new server."""
    if not CENTRAL_LOG_GUILD_ID:
        return None
    
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    if not central_guild:
        return None
    
    try:
        # Sanitize server name for category
        category_name = f"{sanitize_server_name(guild_info['name'])}-logs"
        
        # Create category
        category = await central_guild.create_category(
            name=category_name,
            reason=f"Auto-created for server: {guild_info['name']} (ID: {guild_info['id']})"
        )
        
        # Create channels within the category
        channels = {
            'server-logs': await central_guild.create_text_channel(
                name=f"{sanitize_server_name(guild_info['name'])}-server-logs",
                category=category,
                topic=f"Server changes and settings for {guild_info['name']}"
            ),
            'join-leave': await central_guild.create_text_channel(
                name=f"{sanitize_server_name(guild_info['name'])}-join-leave",
                category=category,
                topic=f"Member joins and leaves for {guild_info['name']}"
            ),
            'messages': await central_guild.create_text_channel(
                name=f"{sanitize_server_name(guild_info['name'])}-messages",
                category=category,
                topic=f"Deleted/edited messages and reactions for {guild_info['name']}"
            ),
            'mod-logs': await central_guild.create_text_channel(
                name=f"{sanitize_server_name(guild_info['name'])}-mod-logs",
                category=category,
                topic=f"Moderation actions for {guild_info['name']}"
            ),
            'tickets': await central_guild.create_text_channel(
                name=f"{sanitize_server_name(guild_info['name'])}-tickets",
                category=category,
                topic=f"Ticket system logs for {guild_info['name']}"
            )
        }
        
        return {
            'category': category,
            'channels': channels
        }
    except Exception as e:
        print(f"Error creating logging category for {guild_info['name']}: {e}")
        return None

async def archive_server_logging_category(guild_info):
    """Archive logging category when Nova leaves a server."""
    if not CENTRAL_LOG_GUILD_ID or not CENTRAL_ARCHIVE_CATEGORY_ID:
        return
    
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    archive_category = central_guild.get_channel(CENTRAL_ARCHIVE_CATEGORY_ID)
    
    if not central_guild or not archive_category:
        return
    
    try:
        # Find the server's category
        category_name = f"{sanitize_server_name(guild_info['name'])}-logs"
        server_category = discord.utils.get(central_guild.categories, name=category_name)
        
        if server_category:
            # Move all channels to archive category and rename them
            for channel in server_category.channels:
                await channel.edit(
                    category=archive_category,
                    name=f"archived-{channel.name}",
                    reason=f"Archived - Nova left {guild_info['name']}"
                )
            
            # Delete the empty category
            await server_category.delete(reason=f"Archived - Nova left {guild_info['name']}")
            
    except Exception as e:
        print(f"Error archiving logging category for {guild_info['name']}: {e}")

async def log_to_central_overview(embed, guild_info=None):
    """Log to the central overview channel."""
    if not CENTRAL_LOG_GUILD_ID or not CENTRAL_OVERVIEW_CHANNEL_ID:
        return
    
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    if not central_guild:
        return
    
    overview_channel = central_guild.get_channel(CENTRAL_OVERVIEW_CHANNEL_ID)
    if overview_channel:
        try:
            await overview_channel.send(embed=embed)
        except Exception as e:
            print(f"Error logging to central overview: {e}")

async def get_central_logging_channel(guild_id, channel_type):
    """Get the central logging channel for a specific server and channel type."""
    if not CENTRAL_LOG_GUILD_ID:
        return None
    
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    if not central_guild:
        return None
    
    # Find the server's logging category
    guild = bot.get_guild(guild_id)
    if not guild:
        return None
    
    category_name = f"{sanitize_server_name(guild.name)}-logs"
    server_category = discord.utils.get(central_guild.categories, name=category_name)
    
    if not server_category:
        return None
    
    # Find the specific channel type within the category
    channel_name = f"{sanitize_server_name(guild.name)}-{channel_type}"
    for channel in server_category.channels:
        if channel.name == channel_name:
            return channel
    
    return None

async def log_to_central_channel(guild_id, channel_type, embed):
    """Log an embed to a specific central logging channel."""
    channel = await get_central_logging_channel(guild_id, channel_type)
    if channel:
        try:
            await channel.send(embed=embed)
            return True
        except Exception as e:
            print(f"Error logging to central {channel_type} channel: {e}")
    return False

# =========================
# Event Handlers
# =========================

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    load_config()
    load_balances()
    load_xp()
    load_birthdays()
    load_afk()
    
    # Start the live countdown update loop using bot.loop
    try:
        bot.loop.create_task(countdown_update_loop())
        print("🚀 LIVE COUNTDOWN UPDATE LOOP STARTED SUCCESSFULLY!")
        print("🔴 Countdown messages will now auto-edit every second!")
    except Exception as e:
        print(f"❌ Error starting countdown update loop: {e}")
        # Fallback method
        try:
            asyncio.ensure_future(countdown_update_loop())
            print("🚀 FALLBACK: Live countdown loop started with ensure_future")
        except Exception as e2:
            print(f"❌ Fallback failed: {e2}")
    
    # Debug: Show loaded config values
    print(f"DEBUG: CHAT_LOGS_CHANNEL_ID = {CHAT_LOGS_CHANNEL_ID}")
    print(f"DEBUG: TICKET_LOGS_CHANNEL_ID = {TICKET_LOGS_CHANNEL_ID}")
    print(f"DEBUG: Config loaded: {config}")
    
    # Validate channels exist and bot has permissions
    for guild in bot.guilds:
        if CHAT_LOGS_CHANNEL_ID:
            chat_channel = guild.get_channel(CHAT_LOGS_CHANNEL_ID)
            if chat_channel:
                print(f"✅ Chat logs channel found: {chat_channel.name}")
                try:
                    print("✅ Chat logs channel found and accessible")
                except Exception as e:
                    print(f"❌ Chat logs permission error: {e}")
            else:
                print(f"❌ Chat logs channel not found with ID: {CHAT_LOGS_CHANNEL_ID}")
        
        if TICKET_LOGS_CHANNEL_ID:
            ticket_channel = guild.get_channel(TICKET_LOGS_CHANNEL_ID)
            if ticket_channel:
                print(f"✅ Ticket logs channel found: {ticket_channel.name}")
                try:
                    print("✅ Ticket logs channel found and accessible")
                except Exception as e:
                    print(f"❌ Ticket logs permission error: {e}")
            else:
                print(f"❌ Ticket logs channel not found with ID: {TICKET_LOGS_CHANNEL_ID}")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

def is_server_allowed(guild_id):
    """Check if the server is allowed to use Nova."""
    if ALLOWED_SERVER_ID is None:
        return True  # No restriction set
    return guild_id == ALLOWED_SERVER_ID

def check_server_restriction():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction):
            guild_id = interaction.guild.id if interaction.guild else None
            if not is_server_allowed(guild_id):
                await interaction.response.send_message(
                    embed=nova_embed("🔒 sERVER lOCKED", "nOVA iS lOCKED tO a dIFFERENT sERVER!"),
                    ephemeral=True
                )
                return
            return await func(interaction)
        return wrapper
    return decorator

@bot.event
async def on_guild_join(guild):
    """Event: Called when Nova joins a new server."""
    print(f"🟢 Nova joined server: {guild.name} (ID: {guild.id})")
    
    # Create guild info dictionary
    guild_info = {
        'id': guild.id,
        'name': guild.name,
        'member_count': guild.member_count,
        'owner': str(guild.owner) if guild.owner else "Unknown",
        'created_at': guild.created_at.isoformat()
    }
    
    # Create logging category and channels for this server
    logging_setup = await create_server_logging_category(guild_info)
    
    # Create overview embed
    embed = discord.Embed(
        title="🟢 Nova Joined Server",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    embed.add_field(name="Server Name", value=guild.name, inline=True)
    embed.add_field(name="Server ID", value=str(guild.id), inline=True)
    embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
    embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Logging Setup", value="✅ Created" if logging_setup else "❌ Failed", inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(text=f"Total servers: {len(bot.guilds)}")
    
    # Log to central overview
    await log_to_central_overview(embed, guild_info)
    
    # Send initial message to the server's new logging channels if created
    if logging_setup and logging_setup.get('channels'):
        server_logs_channel = logging_setup['channels'].get('server-logs')
        if server_logs_channel:
            welcome_embed = discord.Embed(
                title="🎉 Nova Logging System Initialized",
                description=f"Welcome to the centralized logging system for **{guild.name}**!",
                color=0xff69b4
            )
            welcome_embed.add_field(
                name="📋 Available Channels",
                value="• **server-logs** - Server changes and settings\n"
                      "• **join-leave** - Member joins and leaves\n"
                      "• **messages** - Deleted and edited messages\n"
                      "• **mod-logs** - Moderation actions\n"
                      "• **reactions** - Reaction logs",
                inline=False
            )
            welcome_embed.set_footer(text="All logs from this server will be centralized here")
            await server_logs_channel.send(embed=welcome_embed)

@bot.event
async def on_guild_remove(guild):
    """Event: Called when Nova leaves a server."""
    print(f"🔴 Nova left server: {guild.name} (ID: {guild.id})")
    
    # Create guild info dictionary
    guild_info = {
        'id': guild.id,
        'name': guild.name,
        'member_count': guild.member_count,
        'owner': str(guild.owner) if guild.owner else "Unknown"
    }
    
    # Archive the logging category for this server
    await archive_server_logging_category(guild_info)
    
    # Create overview embed
    embed = discord.Embed(
        title="🔴 Nova Left Server",
        color=0xff0000,
        timestamp=datetime.now()
    )
    embed.add_field(name="Server Name", value=guild.name, inline=True)
    embed.add_field(name="Server ID", value=str(guild.id), inline=True)
    embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
    embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Logs Status", value="📦 Archived", inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(text=f"Total servers: {len(bot.guilds)}")
    
    # Log to central overview
    await log_to_central_overview(embed, guild_info)

@bot.event
async def on_message(message):
    """Event: Called on every message. Adds XP and processes commands."""
    if message.author.bot:
        return
    
    # Check if server is allowed
    if not is_server_allowed(message.guild.id):
        return  # Ignore messages from unauthorized servers
    # AFK return logic
    if message.author.id in AFK_STATUS:
        afk = AFK_STATUS.pop(message.author.id)
        save_afk()  # Save AFK data after removing user
        since = afk["since"]
        delta = datetime.now(dt_timezone.utc) - since
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        mins = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        
        if days > 0:
            time_str = f"{days}d {hours}h {mins}m {secs}s"
        elif hours > 0:
            time_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            time_str = f"{mins}m {secs}s"
        else:
            time_str = f"{secs}s"
        view = MentionsView(message.author.id)
        await message.channel.send(embed=nova_embed("aFK", f"wELCOME bACK, {message.author.display_name}! yOU wERE gONE fOR {time_str}."), view=view)
    # Notify if mentioning AFK users
    mentioned_ids = [user.id for user in message.mentions]
    for uid in mentioned_ids:
        if uid in AFK_STATUS:
            AFK_STATUS[uid]["mentions"].add(message.author.id)
            save_afk()  # Save AFK data after adding mention
            afk = AFK_STATUS[uid]
            member = message.guild.get_member(uid)
            if member:
                since = afk["since"]
                delta = datetime.now(dt_timezone.utc) - since
                total_seconds = int(delta.total_seconds())
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                mins = (total_seconds % 3600) // 60
                secs = total_seconds % 60
                
                if days > 0:
                    time_str = f"{days}d {hours}h {mins}m {secs}s"
                elif hours > 0:
                    time_str = f"{hours}h {mins}m {secs}s"
                elif mins > 0:
                    time_str = f"{mins}m {secs}s"
                else:
                    time_str = f"{secs}s"
                await message.channel.send(embed=nova_embed("aFK", f"{member.display_name} iS aFK: {afk['reason']} ({time_str})"))
    add_xp(message.author.id, random.randint(5, 15))
    
    # Track message activity for statistics
    if message.guild:
        track_message(message.guild.id, message.author.id)
    
    # Check for blacklisted words and auto-delete
    message_lower = message.content.lower()
    for word in BLACKLIST_WORDS:
        if word in message_lower:
            try:
                await message.delete()
                # Send a warning message that deletes after 5 seconds
                warning = await message.channel.send(
                    embed=nova_embed(
                        "⚠️ mESSAGE dELETED",
                        f"{message.author.mention}, yOUR mESSAGE cONTAINED a bLACKLISTED wORD!"
                    ),
                    delete_after=5
                )
                return  # Don't process commands if message was deleted
            except discord.errors.NotFound:
                pass  # Message was already deleted
            except discord.errors.Forbidden:
                pass  # Bot doesn't have permission to delete
    
    # Auto-reactions (server-specific)
    guild_id = str(message.guild.id) if message.guild else None
    if guild_id and guild_id in AUTO_REACTIONS:
        for trigger_word, emoji in AUTO_REACTIONS[guild_id].items():
            if trigger_word in message.content.lower():
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    pass  # Ignore failed reactions
    
    # React with cute Nova emoji when someone mentions "Nova" (fallback)
    nova_reaction_exists = False
    if guild_id and guild_id in AUTO_REACTIONS:
        nova_reaction_exists = "nova" in AUTO_REACTIONS[guild_id]
    
    if "nova" in message_lower and not nova_reaction_exists:
        try:
            await message.add_reaction("<:cute_nova:1398830405691637800>")
        except discord.errors.HTTPException:
            pass  # Emoji not found or other error
    
    # Check if message starts with "nova:" to make Nova say the text
    if message.content.lower().startswith("nova:"):
        # Only allow the owner to use this feature
        if message.author.id == OWNER_ID:
            content = message.content[5:].strip()  # Remove "nova:" and get the rest
            if content:
                # Delete the original message
                await message.delete()
                # Make Nova say the text
                await message.channel.send(content)
        else:
            # If someone else tries to use it, delete their message and warn them
            await message.delete()
            await message.channel.send(f"{message.author.mention}, only the owner can make Nova speak!", delete_after=3)
    # Check if command is disabled before processing
    if message.content.startswith('?'):
        command_name = message.content[1:].split()[0].lower()
        if command_name in DISABLED_COMMANDS:
            await message.channel.send(embed=nova_embed(
                "🚫 cOMMAND dISABLED",
                f"tHE cOMMAND '{command_name}' iS cURRENTLY dISABLED!"
            ), delete_after=5)
            return
    
    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    """Event: Called when a reaction is added. Handles role assignment, runway emoji forwarding, and chat logs."""
    # --- Chat logs for reactions ---
    if payload.guild_id and CHAT_LOGS_CHANNEL_ID:
        guild = bot.get_guild(payload.guild_id)
        if guild:
            user = guild.get_member(payload.user_id)
            if user and not user.bot:  # Don't log bot reactions
                channel = guild.get_channel(payload.channel_id)
                chat_logs_channel = guild.get_channel(CHAT_LOGS_CHANNEL_ID)
                if channel and chat_logs_channel:
                    try:
                        message = await channel.fetch_message(payload.message_id)
                        embed = discord.Embed(
                            title="➕ Reaction Added",
                            color=0x00ff00,
                            timestamp=datetime.now()
                        )
                        embed.add_field(name="User", value=f"{user.mention}\n`{user.id}`", inline=True)
                        embed.add_field(name="Channel", value=f"{channel.mention}\n`{channel.id}`", inline=True)
                        embed.add_field(name="Emoji", value=str(payload.emoji), inline=True)
                        embed.add_field(name="Message", value=f"[Jump to Message]({message.jump_url})\n`{message.id}`", inline=False)
                        
                        # Show message content preview (truncated)
                        if message.content:
                            content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
                            embed.add_field(name="Message Content", value=f"```{content_preview}```", inline=False)
                        
                        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
                        await chat_logs_channel.send(embed=embed)
                    except Exception as e:
                        print(f"ERROR logging reaction add: {e}")
    
    # --- Runway emoji forwarding ---
    # Only act on server messages
    if payload.guild_id and str(payload.emoji) == "😭":
        guild = bot.get_guild(payload.guild_id)
        if guild and RUNWAY_CHANNEL_ID:
            channel = guild.get_channel(payload.channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(payload.message_id)
                    # Count loudly crying emoji reactions
                    for reaction in message.reactions:
                        if (str(reaction.emoji) == "😭") and (reaction.count >= 4):
                            # Only forward if not already forwarded (avoid spam)
                            # Optionally, you could keep a set of forwarded message IDs
                            runway_channel = guild.get_channel(RUNWAY_CHANNEL_ID)
                            if runway_channel:
                                embed = nova_embed(
                                    title=f"😭 #{message.id}",
                                    description=message.content
                                )
                                embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
                                embed.add_field(name="oRIGINAL cHANNEL", value=channel.mention, inline=True)
                                embed.add_field(name="jUMP tO mESSAGE", value=f"[Click here]({message.jump_url})", inline=True)
                                embed.set_footer(text=f"Message ID: {message.id}")
                                files = []
                                for attachment in message.attachments:
                                    try:
                                        file_data = await attachment.read()
                                        files.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
                                    except Exception:
                                        continue
                                await runway_channel.send(embed=embed, files=files)
                            break  # Only forward once per event
                except Exception:
                    pass  # Silently ignore errors for this feature
    # --- Role assignment (existing logic) ---
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
    """Event: Called when a reaction is removed. Handles role removal, rsnipe storage, and chat logs."""
    # --- Chat logs for reaction removal ---
    if payload.guild_id and CHAT_LOGS_CHANNEL_ID:
        guild = bot.get_guild(payload.guild_id)
        if guild:
            user = guild.get_member(payload.user_id)
            if user and not user.bot:  # Don't log bot reactions
                channel = guild.get_channel(payload.channel_id)
                chat_logs_channel = guild.get_channel(CHAT_LOGS_CHANNEL_ID)
                if channel and chat_logs_channel:
                    try:
                        message = await channel.fetch_message(payload.message_id)
                        embed = discord.Embed(
                            title="➖ Reaction Removed",
                            color=0xff0000,
                            timestamp=datetime.now()
                        )
                        embed.add_field(name="User", value=f"{user.mention}\n`{user.id}`", inline=True)
                        embed.add_field(name="Channel", value=f"{channel.mention}\n`{channel.id}`", inline=True)
                        embed.add_field(name="Emoji", value=str(payload.emoji), inline=True)
                        embed.add_field(name="Message", value=f"[Jump to Message]({message.jump_url})\n`{message.id}`", inline=False)
                        
                        # Show message content preview (truncated)
                        if message.content:
                            content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
                            embed.add_field(name="Message Content", value=f"```{content_preview}```", inline=False)
                        
                        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
                        await chat_logs_channel.send(embed=embed)
                    except Exception as e:
                        print(f"ERROR logging reaction removal: {e}")
    
    # Store the last removed reaction for rsnipe - Enhanced debugging
    print(f"DEBUG: Reaction removed - Emoji: {payload.emoji}, User ID: {payload.user_id}, Guild ID: {payload.guild_id}")
    
    if payload.guild_id:
        guild = bot.get_guild(payload.guild_id)
        print(f"DEBUG: Guild found: {guild}")
        if guild:
            user = guild.get_member(payload.user_id)
            print(f"DEBUG: User found: {user}, Is bot: {user.bot if user else 'None'}")
            if user and not user.bot:
                channel = guild.get_channel(payload.channel_id)
                print(f"DEBUG: Channel found: {channel}")
                if channel:
                    try:
                        message = await channel.fetch_message(payload.message_id)
                        jump_url = message.jump_url
                        print(f"DEBUG: Message fetched successfully, jump_url: {jump_url}")
                    except Exception as e:
                        jump_url = None
                        print(f"DEBUG: Failed to fetch message: {e}")
                    
                    rsnipes[payload.channel_id] = {
                        'emoji': str(payload.emoji),
                        'user': str(user),
                        'message_id': payload.message_id,
                        'jump_url': jump_url,
                        'time': datetime.now(dt_timezone.utc)
                    }
                    print(f"DEBUG: RSnipe data stored for channel {payload.channel_id}: {rsnipes[payload.channel_id]}")
                else:
                    print(f"DEBUG: Channel not found with ID: {payload.channel_id}")
            else:
                print(f"DEBUG: User is bot or not found, skipping rsnipe storage")
        else:
            print(f"DEBUG: Guild not found with ID: {payload.guild_id}")
    else:
        print("DEBUG: No guild_id in payload, skipping rsnipe storage")
    
    # Handle role removal (existing logic)
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

# =========================
# Text Commands
# =========================

@bot.command()
async def setmodrole(ctx, role_input):
    """Set the moderator role by ID or mention. Owner only."""
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use this command.")
        return
    # Try to parse role from mention or ID
    role = None
    if role_input.startswith('<@&') and role_input.endswith('>'):
        role_id = int(role_input[3:-1])
        role = ctx.guild.get_role(role_id)
    else:
        try:
            role_id = int(role_input)
            role = ctx.guild.get_role(role_id)
        except ValueError:
            await ctx.send("Invalid role ID or mention format.")
            return
    if not role:
        await ctx.send("Role not found.")
        return
    config["mod_role_id"] = role.id
    save_config()
    await ctx.send(f"Moderator role set to {role.name} (ID: {role.id})")

@bot.command()
async def setadminrole(ctx, role_input):
    """Set the admin role by ID or mention. Owner only."""
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use this command.")
        return
    # Try to parse role from mention or ID
    role = None
    if role_input.startswith('<@&') and role_input.endswith('>'):
        role_id = int(role_input[3:-1])
        role = ctx.guild.get_role(role_id)
    else:
        try:
            role_id = int(role_input)
            role = ctx.guild.get_role(role_id)
        except ValueError:
            await ctx.send("Invalid role ID or mention format.")
            return
    if not role:
        await ctx.send("Role not found.")
        return
    config["admin_role_id"] = role.id
    save_config()
    await ctx.send(f"Admin role set to {role.name} (ID: {role.id})")

@bot.command()
async def setprefix(ctx, new_prefix: str = None):
    """Set the bot's command prefix for this server. Admin/Owner only."""
    # Check permissions - allow both owner and admins/server owner
    if not (ctx.author.id == OWNER_ID or has_mod_or_admin(ctx)):
        await ctx.send(embed=nova_embed("sET pREFIX", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if ctx.guild is None:
        await ctx.send(embed=nova_embed("sET pREFIX", "tHIS cOMMAND cAN oNLY bE uSED iN sERVERS!"))
        return
    
    # Get current prefix for this server
    current_prefix = SERVER_PREFIXES.get(ctx.guild.id, DEFAULT_PREFIX)
    
    if new_prefix is None:
        await ctx.send(embed=nova_embed(
            "sET pREFIX", 
            f"cURRENT pREFIX fOR tHIS sERVER: `{current_prefix}`\n\n"
            f"uSAGE: `{current_prefix}setprefix <new_prefix>`\n"
            f"eXAMPLE: `{current_prefix}setprefix !`\n\n"
            f"✅ cHANGES tAKE eFFECT iMMEDIATELY!"
        ))
        return
    
    # Validate prefix
    if len(new_prefix) > 5:
        await ctx.send(embed=nova_embed("sET pREFIX", "pREFIX mUST bE 5 cHARACTERS oR lESS!"))
        return
    
    if new_prefix.isspace() or not new_prefix:
        await ctx.send(embed=nova_embed("sET pREFIX", "pREFIX cANNOT bE eMPTY oR oNLY sPACES!"))
        return
    
    # Save the new prefix for this server
    old_prefix = current_prefix
    SERVER_PREFIXES[ctx.guild.id] = new_prefix
    save_config()
    
    await ctx.send(embed=nova_embed(
        "✅ pREFIX uPDATED!",
        f"pREFIX cHANGED fROM `{old_prefix}` tO `{new_prefix}`\n\n"
        f"✅ **cHANGE iS aCTIVE iMMEDIATELY!**\n"
        f"tRY uSING `{new_prefix}ping` tO tEST!"
    ))

@bot.command()
async def setserver(ctx):
    """Set the allowed server ID. Owner only."""
    global ALLOWED_SERVER_ID
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use this command.")
        return
    ALLOWED_SERVER_ID = ctx.guild.id
    await ctx.send(embed=nova_embed("🔒 sERVER lOCKED", f"✅ nOVA iS nOW lOCKED tO tHIS sERVER: {ctx.guild.name} (ID: {ctx.guild.id})"))

@bot.command()
async def removeserverlock(ctx):
    """Remove server restriction. Owner only."""
    global ALLOWED_SERVER_ID
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use this command.")
        return
    ALLOWED_SERVER_ID = None
    await ctx.send("✅ Server restriction removed. Nova can now work in any server.")

@bot.command()
async def serverstatus(ctx):
    """Check current server restriction status. Owner only."""
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use this command.")
        return
    if ALLOWED_SERVER_ID is None:
        await ctx.send("🔓 **Server Status:** No restriction set - Nova works in all servers")
    else:
        guild = bot.get_guild(ALLOWED_SERVER_ID)
        guild_name = guild.name if guild else "Unknown Server"
        await ctx.send(f"🔒 **Server Status:** Nova is locked to {guild_name} (ID: {ALLOWED_SERVER_ID})")

# Help system data structure
HELP_CATEGORIES = {
    "💰 Economy & Shopping": [
        ("?balance", "Check your current balance and pet", "Shows your dOLLARIANAS balance and equipped pet"),
        ("?work", "Work a job to earn dOLLARIANAS (20min cooldown)", "Random job with 10-50 dOLLARIANAS reward"),
        ("?beg", "Beg for dOLLARIANAS (10min cooldown)", "50% chance to get 1-10 dOLLARIANAS"),
        ("?daily", "Claim your daily reward (24hr cooldown)", "Get 100 dOLLARIANAS once per day"),
        ("?pay @user amount", "Send dOLLARIANAS to another user", "Transfer your dOLLARIANAS to someone else"),
        ("?shop", "View the pet shop", "See all available pets and their prices"),
        ("?buy <pet>", "Purchase a pet from the shop", "Buy a new pet companion"),
        ("?inventory", "View your owned pets", "See all pets you own and can equip"),
        ("?thrift", "Browse the thrift store", "See items other users are selling"),
        ("?sell <item> <price>", "Sell an item in thrift store", "List your items for sale to other users"),
        ("?buythrift <item>", "Buy from thrift store", "Purchase items from other users"),
        ("?lottery [action]", "Manage server lottery (Owner)", "Start, draw, or manage lottery system"),
        ("?joinlottery", "Join the current lottery", "Enter the lottery with entry fee")
    ],
    "🐾 Pet System": [
        ("?adoptpet", "Adopt a virtual pet", "Choose and adopt your first pet companion"),
        ("?pet", "Interact with your pet", "View pet stats and care for them"),
        ("?petname <name>", "Rename your current pet", "Give your pet a custom name"),
        ("?changepet", "Change your pet type (once only)", "Switch pet type but reset all stats")
    ],
    "🎂 Birthdays & Relationships": [
        ("?setbday DD-MM", "Set your birthday", "Register your birthday for celebrations"),
        ("?setbirthday DD-MM", "Set your birthday (alias)", "Same as ?setbday command"),
        ("?birthday @user", "Check someone's birthday", "View a user's birthday if set"),
        ("?bday @user", "Check someone's birthday (alias)", "Same as ?birthday command"),
        ("?birthdays", "List upcoming birthdays", "See birthdays in the next 30 days"),
        ("?today", "Check today's birthdays", "See who's celebrating today"),
        ("?marry @user", "Propose marriage to someone", "Start a romantic partnership"),
        ("?divorce", "End your marriage", "Dissolve your current marriage"),
        ("?adopt @user", "Adopt someone as your child", "Add them to your family tree"),
        ("?emancipate @user", "Remove someone from your family", "End parent-child relationship"),
        ("?getemancipated", "Leave your current family", "Remove yourself from family tree"),
        ("?familytree @user", "View family relationships", "See spouse, parents, and children")
    ],
    "🎮 Fun & Interactive": [
        ("?kiss @user", "Give someone a kiss", "Show affection with a cute message"),
        ("?slap @user", "Playfully slap someone", "Friendly banter with random messages"),
        ("?whoasked", "Nobody asked!", "Classic comeback with random responses"),
        ("?voguebattle @user", "Challenge to a vogue battle", "Strike poses in a dance-off"),
        ("?votekick @user", "Start a fake vote to kick (fun)", "Joke voting system for entertainment"),
        ("?imposter", "Start Among Us word game", "Guess the imposter in word association game"),
        ("?endimposter", "End current imposter game", "Stop the active imposter game"),
        ("?explode @user", "Make someone explode", "Fun explosion animation command"),
        ("?drama", "Generate random drama", "Create fictional drama scenarios"),
        ("?_8ball <question>", "Ask the magic 8-ball", "Get mystical answers to your questions"),
        ("?mood", "Show Nova's current mood", "See what mood Nova is in today"),
        ("?nicki", "Get random Nicki Minaj lyric", "Receive iconic Nicki Minaj quotes")
    ],
    "🎵 Music & Media": [
        ("?spotify @user", "Show Spotify status", "Display what someone is listening to"),
        ("?fm @user", "Show Spotify status (alias)", "Same as ?spotify command"),

        ("?playlistshow", "Show playlist info", "Display current playlist information"),
        ("?setautoplay <on/off>", "Toggle autoplay (Admin)", "Enable/disable music autoplay")
    ],
    "📱 Social & Profiles": [
        ("?aboutme @user", "View someone's profile description", "See their custom about me text"),
        ("?level @user", "Check someone's server level", "View their XP and level progress"),
        ("?leaderboard", "Show the server leaderboard", "Top users by level and XP"),
        ("?avatar @user", "Show someone's avatar", "Display user's profile picture in full size"),
        ("?afk [reason]", "Set yourself as away", "Let others know you're not available"),
        ("?nick @user <nickname>", "Change someone's nickname (Mod+)", "Set or change user nicknames")
    ],
    "🛡️ Moderation & Punishment": [
        ("?warn @user [reason]", "Warn a member (Mod+)", "Add a warning to their record"),
        ("?unwarn @user", "Remove latest warning (Mod+)", "Delete their most recent warning"),
        ("?mute @user [time] [reason]", "Mute a member (Mod+)", "Temporarily silence someone"),
        ("?unmute @user", "Unmute a member (Mod+)", "Remove mute from someone"),
        ("?ban @user [reason]", "Ban a member (Mod+)", "Permanently ban from server"),
        ("?unban <user_id>", "Unban someone (Mod+)", "Remove ban by Discord ID"),
        ("?kick @user [reason]", "Kick a member (Mod+)", "Remove from server temporarily"),
        ("?jail @user [reason]", "Jail a member (Mod+)", "Put user in jail role"),
        ("?unjail @user", "Release from jail (Mod+)", "Remove jail role from user"),
        ("?case @user", "View someone's infractions (Mod+)", "See their warning/ban history"),
        ("?clearcase @user", "Clear all infractions (Mod+)", "Remove all warnings from user"),
        ("?blacklist @user [reason]", "Blacklist a user (Admin)", "Add user to server blacklist")
    ],
    "🧹 Channel Management": [
        ("?nuke [amount]", "Delete all messages (Admin)", "Bulk delete messages in channel"),
        ("?clear <amount>", "Delete specific number of messages (Mod+)", "Delete last X messages with logging"),
        ("?slowmode <seconds>", "Set channel slowmode (Mod+)", "Limit message frequency"),
        ("?lock", "Lock current channel (Mod+)", "Prevent members from sending messages"),
        ("?unlock", "Unlock current channel (Mod+)", "Allow members to send messages again"),
        ("?snipe", "View last deleted message (Mod+)", "See recently deleted content"),
        ("?edsnipe", "View last edited message (Mod+)", "See message edit history"),
        ("?rsnipe", "View last removed reaction (Mod+)", "See recently removed reactions")
    ],
    "⚙️ Server Configuration": [
        ("?setruleschannel #channel", "Set rules channel (Admin)", "Configure welcome message rules link"),
        ("?setchatlogs #channel", "Set chat logs channel (Admin)", "Where deleted messages are logged"),
        ("?setjoinleavelogs #channel", "Set join/leave logs (Admin)", "Where member joins/leaves are logged"),
        ("?setserverlogs #channel", "Set server logs (Admin)", "Where server changes are logged"),
        ("?setmodlogs #channel", "Set mod logs (Admin)", "Where moderation actions are logged"),
        ("?setwelcome #channel", "Set welcome channel (Admin)", "Where new members are welcomed"),
        ("?setfarewell #channel", "Set farewell channel (Admin)", "Where member departures are announced"),
        ("?setrunway #channel", "Set runway channel (Admin)", "Configure runway/fashion channel"),
        ("?setjail @role", "Set jail role (Admin)", "Configure punishment role for jailing"),
        ("?setmodrole @role", "Set moderator role (Admin)", "Define which role has mod permissions"),
        ("?setadminrole @role", "Set admin role (Admin)", "Define which role has admin permissions"),
        ("?setserver <id>", "Set server restriction (Owner)", "Limit bot to specific server"),
        ("?removeserverlock", "Remove server restriction (Owner)", "Allow bot in all servers")
    ],
    "🎫 Support System": [
        ("?ticket", "Create support ticket panel", "Set up ticket creation system"),
        ("?setticketcategory <category>", "Set ticket category (Admin)", "Where support tickets are created"),
        ("?setsupportrole @role", "Set support role (Admin)", "Role that can handle tickets"),
        ("?setticketlogs #channel", "Set ticket logs (Admin)", "Where ticket actions are logged")
    ],
    "🤖 Auto-Reactions & Commands": [
        ("?reactionadd <word> <emoji>", "Add auto-reaction (Mod+)", "Bot reacts when word is said"),
        ("?reactionremove <word>", "Remove auto-reaction (Mod+)", "Stop auto-reacting to word"),
        ("?reactionlist", "List auto-reactions (Mod+)", "See all configured auto-reactions"),
        ("?reactionroles", "Post gender role selection", "Create reaction role message"),
        ("?disable <command>", "Disable a command (Mod+)", "Prevent command usage in server"),
        ("?enable <command>", "Enable a command (Mod+)", "Re-enable a disabled command"),
        ("?disabledcommands", "List disabled commands (Mod+)", "See which commands are disabled")
    ],
    "🏆 BCA Awards System": [
        ("?setbcanominations #channel", "Set nominations channel (Mod+)", "Where nominees get pinged"),
        ("?setbcanominationslogs #channel", "Set nomination logs (Mod+)", "Where mods see who nominated who"),
        ("?setbcavoting #channel", "Set voting channel (Mod+)", "Where voting takes place"),
        ("?setbcavotinglogs #channel", "Set voting logs (Mod+)", "Where mods see voting activity"),
        ("?bcaaddcategory <name>", "Add award category (Mod+)", "Create new BCA category"),
        ("?removebcacategory <name>", "Remove award category (Mod+)", "Delete BCA category and all data"),
        ("?bcatoggleself <category>", "Toggle self-nomination (Mod+)", "Allow/disallow self-nominations"),
        ("?bcacategories", "List all categories", "See categories and self-nom status"),
        ("?nominate @user <category>", "Nominate someone", "Anonymous nomination system"),
        ("?bcavote <category>", "Start voting session (Mod+)", "Create interactive voting buttons"),
        ("?bcaresults <category>", "Show voting results (Mod+)", "Display vote counts and percentages"),
        ("?bcanominations", "Show all nominations (Mod+)", "View current nominations overview"),
        ("?bcadeadlines", "Show BCA deadlines (Mod+)", "View nomination and voting deadlines"),
        ("?setbcanomdeadline <date>", "Set nomination deadline (Mod+)", "When nominations close"),
        ("?setbcavotedeadline <date>", "Set voting deadline (Mod+)", "When voting closes"),
        ("?resetnominations", "Reset all nominations (Mod+)", "Clear all current nominations"),
        ("?resetvotes", "Reset all votes (Mod+)", "Clear all current votes")
    ],
    "⏰ Reminders & Countdowns": [
        ("?remindme <time> <message>", "Set a personal reminder", "Get pinged after specified time"),
        ("?reminderlist", "List your active reminders", "See all your pending reminders"),
        ("?addcountdown \"name\" \"date\" [desc]", "Add event countdown (Mod+)", "Create countdown to important events"),
        ("?countdown [event]", "View countdowns", "See specific countdown or all countdowns"),
        ("?settz <tz>", "Set server timezone (Admin)", "Configure server's timezone")
    ],
    "🔍 Information & Utilities": [
        ("?ping", "Check bot latency", "See bot response time"),
        ("?about", "Bot information", "Learn about Nova bot"),
        ("?uptime", "Bot uptime statistics", "See how long bot has been running"),
        ("?membercount", "Show server member statistics", "Total members, humans, bots breakdown"),
        ("?messagecount @user", "View message statistics (Mod+)", "See user's message counts over time"),
        ("?serverinfo", "Show server information", "Display server stats and details"),
        ("?serverstatus", "Show server status", "Display current server status"),
        ("?welcome", "Show welcome message preview", "Test the server welcome message"),
        ("?rules", "Show server rules", "Display the server rules"),
        ("?runway", "Show runway information", "Display runway channel content"),
        ("?getemojis", "Get server emojis", "List all custom server emojis")
    ],
    "🌐 External Services": [
        ("?google <query>", "Search Google", "Get Google search results"),
        ("?weather <location>", "Get weather info", "Check weather for any location"),
        ("?chatgpt <prompt>", "Ask ChatGPT", "Get AI responses to your questions"),
        ("?image <prompt>", "Generate AI image", "Create images using AI"),
        ("?generate <prompt>", "Generate content", "Create various content with AI"),
        ("?translate <lang> <text>", "Translate text", "Translate text to different languages"),
        ("?fact", "Get random fact", "Learn something new with random facts"),
        ("?calc <equation>", "Calculate math", "Solve mathematical equations")
    ],
    "💬 Anonymous & Confessions": [
        ("?confess <message>", "Send anonymous confession", "Submit anonymous message to confession channel"),
        ("?dmtest", "Test DM functionality", "Check if bot can send you direct messages")
    ],
    "🎯 Productivity": [
        ("?focus [duration]", "Start focus timer", "Pomodoro-style focus session timer")
    ],
    "🔧 Admin Tools": [
        ("?fixinmate", "Fix inmate role permissions (Admin)", "Reset inmate role permissions across channels")
    ]
}

class HelpView(discord.ui.View):
    def __init__(self, categories, current_page=0):
        super().__init__(timeout=300)  # 5 minute timeout
        self.categories = list(categories.keys())
        self.category_data = categories
        self.current_page = current_page
        self.max_pages = len(self.categories)
        
    def create_embed(self):
        category_name = self.categories[self.current_page]
        commands = self.category_data[category_name]
        
        embed = discord.Embed(
            title=f"📚 nOVA hELP - {category_name}",
            description=f"Page {self.current_page + 1}/{self.max_pages}\n\n",
            color=0xff69b4
        )
        
        # Add up to 10 commands per page
        for i, (cmd, short_desc, long_desc) in enumerate(commands[:10]):
            embed.add_field(
                name=f"`{cmd}`",
                value=f"**{short_desc}**\n{long_desc}",
                inline=False
            )
        
        embed.set_footer(text="💡 All commands work with both ? (prefix) and / (slash) unless noted | Use buttons to navigate")
        return embed
    
    @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = self.max_pages - 1  # Wrap to last page
        
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='🏠 Overview', style=discord.ButtonStyle.primary)
    async def overview_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📚 nOVA hELP - oVERVIEW",
            description="Welcome to Nova's comprehensive help system! Use the buttons below to navigate through different command categories.\n\n",
            color=0xff69b4
        )
        
        # Add category overview
        for i, category in enumerate(self.categories):
            cmd_count = len(self.category_data[category])
            embed.add_field(
                name=f"{i+1}. {category}",
                value=f"{cmd_count} commands available",
                inline=True
            )
        
        embed.add_field(
            name="\n🔍 Navigation Tips",
            value="• Use ◀️ ▶️ to browse categories\n• Use 🏠 to return to this overview\n• All commands support both `?command` and `/command`\n• Some commands require Mod+ or Admin permissions",
            inline=False
        )
        
        embed.set_footer(text=f"Total: {sum(len(cmds) for cmds in self.category_data.values())} commands across {len(self.categories)} categories")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='Next ▶️', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
        else:
            self.current_page = 0  # Wrap to first page
        
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        # Disable all buttons when view times out
        for item in self.children:
            item.disabled = True

@bot.command()
async def help(ctx, *, category=None):
    """Show Nova's comprehensive help system with categories and detailed explanations"""
    if category:
        # Try to find matching category
        category_match = None
        for cat_name in HELP_CATEGORIES.keys():
            if category.lower() in cat_name.lower():
                category_match = cat_name
                break
        
        if category_match:
            # Show specific category
            view = HelpView(HELP_CATEGORIES)
            view.current_page = list(HELP_CATEGORIES.keys()).index(category_match)
            embed = view.create_embed()
            await ctx.send(embed=embed, view=view)
        else:
            # Category not found, show available categories
            categories_list = "\n".join([f"• {cat}" for cat in HELP_CATEGORIES.keys()])
            await ctx.send(embed=nova_embed(
                "hELP - cATEGORY nOT fOUND",
                f"Category '{category}' not found!\n\n**Available categories:**\n{categories_list}\n\nUse `?help` to see the full help system."
            ))
    else:
        # Show overview page
        view = HelpView(HELP_CATEGORIES)
        embed = discord.Embed(
            title="📚 nOVA hELP - oVERVIEW",
            description="Welcome to Nova's comprehensive help system! Use the buttons below to navigate through different command categories.\n\n",
            color=0xff69b4
        )
        
        # Add category overview
        for i, category in enumerate(HELP_CATEGORIES.keys()):
            cmd_count = len(HELP_CATEGORIES[category])
            embed.add_field(
                name=f"{i+1}. {category}",
                value=f"{cmd_count} commands available",
                inline=True
            )
        
        embed.add_field(
            name="\n🔍 Navigation Tips",
            value="• Use ◀️ ▶️ to browse categories\n• Use 🏠 to return to this overview\n• All commands support both `?command` and `/command`\n• Some commands require Mod+ or Admin permissions",
            inline=False
        )
        
        embed.set_footer(text=f"Total: {sum(len(cmds) for cmds in HELP_CATEGORIES.values())} commands across {len(HELP_CATEGORIES)} categories")
        await ctx.send(embed=embed, view=view)

@bot.tree.command(name="help", description="Show Nova's comprehensive help system")
@app_commands.describe(category="Specific category to view (optional)")
@check_server_restriction()
async def help_slash(interaction: discord.Interaction, category: str = None):
    """Show Nova's comprehensive help system with categories and detailed explanations"""
    if category:
        # Try to find matching category
        category_match = None
        for cat_name in HELP_CATEGORIES.keys():
            if category.lower() in cat_name.lower():
                category_match = cat_name
                break
        
        if category_match:
            # Show specific category
            view = HelpView(HELP_CATEGORIES)
            view.current_page = list(HELP_CATEGORIES.keys()).index(category_match)
            embed = view.create_embed()
            await interaction.response.send_message(embed=embed, view=view)
        else:
            # Category not found, show available categories
            categories_list = "\n".join([f"• {cat}" for cat in HELP_CATEGORIES.keys()])
            await interaction.response.send_message(embed=nova_embed(
                "hELP - cATEGORY nOT fOUND",
                f"Category '{category}' not found!\n\n**Available categories:**\n{categories_list}\n\nUse `/help` to see the full help system."
            ))
    else:
        # Show overview page
        view = HelpView(HELP_CATEGORIES)
        embed = discord.Embed(
            title="📚 nOVA hELP - oVERVIEW",
            description="Welcome to Nova's comprehensive help system! Use the buttons below to navigate through different command categories.\n\n",
            color=0xff69b4
        )
        
        # Add category overview
        for i, category in enumerate(HELP_CATEGORIES.keys()):
            cmd_count = len(HELP_CATEGORIES[category])
            embed.add_field(
                name=f"{i+1}. {category}",
                value=f"{cmd_count} commands available",
                inline=True
            )
        
        embed.add_field(
            name="\n🔍 Navigation Tips",
            value="• Use ◀️ ▶️ to browse categories\n• Use 🏠 to return to this overview\n• All commands support both `?command` and `/command`\n• Some commands require Mod+ or Admin permissions",
            inline=False
        )
        
        embed.set_footer(text=f"Total: {sum(len(cmds) for cmds in HELP_CATEGORIES.values())} commands across {len(HELP_CATEGORIES)} categories")
        await interaction.response.send_message(embed=embed, view=view)

@bot.command()
async def balance(ctx):
    """Check your dOLLARIANAS balance."""
    guild_id = ctx.guild.id
    bal = get_balance(ctx.author.id, guild_id)
    await ctx.send(embed=nova_embed("bALANCE", f"{ctx.author.mention}, yOU hAVE {bal} {CURRENCY_NAME} iN tHIS sERVER."))

# Slash command version of balance
@bot.tree.command(name="balance", description="Check your dOLLARIANAS balance (slash command)")
async def balance_slash(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    bal = get_balance(interaction.user.id, guild_id)
    await interaction.response.send_message(embed=nova_embed("bALANCE", f"{interaction.user.mention}, yOU hAVE {bal} {CURRENCY_NAME} iN tHIS sERVER."))

@bot.command()
async def beg(ctx):
    now = datetime.now(dt_timezone.utc)
    user_id = ctx.author.id
    guild_id = ctx.guild.id
    last = beg_cooldowns.get(user_id)
    if last and now - last < timedelta(minutes=10):
        rem = timedelta(minutes=10) - (now - last)
        await ctx.send(embed=nova_embed("bEG", f"{ctx.author.mention}, yOU cAN bEG aGAIN iN {str(rem).split('.')[0]}."))
        return
    beg_cooldowns[user_id] = now
    if random.random() < 0.5:
        await ctx.send(embed=nova_embed("bEG", f"{ctx.author.mention}, nO oNE gAVE yOU aNYTHING tHIS tIME."))
    else:
        amount = random.randint(1, 20)
        change_balance(user_id, amount, guild_id)
        await ctx.send(embed=nova_embed("bEG", f"{ctx.author.mention}, yOU bEGGED aND gOT {amount} {CURRENCY_NAME}!"))

@bot.command()
async def daily(ctx):
    user_id = str(ctx.author.id)
    guild_id = ctx.guild.id
    now = datetime.utcnow()
    last = daily_cooldowns.get(user_id)
    if last and (now - last).total_seconds() < 86400:
        remaining = 86400 - (now - last).total_seconds()
        hours = int(remaining // 3600)
        mins = int((remaining % 3600) // 60)
        await ctx.send(embed=nova_embed("dAILY", f"yOU aLREADY cLAIMED yOUR dAILY! tRY aGAIN iN {hours}h {mins}m."))
        return
    daily_cooldowns[user_id] = now
    change_balance(ctx.author.id, 100, guild_id)
    await ctx.send(embed=nova_embed("dAILY", f"yOU cLAIMED yOUR dAILY 100 {CURRENCY_NAME}!"))

@bot.tree.command(name="daily", description="Claim daily reward (24h cooldown)")
async def daily_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = interaction.guild.id
    now = datetime.utcnow()
    last = daily_cooldowns.get(user_id)
    if last and (now - last).total_seconds() < 86400:
        remaining = 86400 - (now - last).total_seconds()
        hours = int(remaining // 3600)
        mins = int((remaining % 3600) // 60)
        await interaction.response.send_message(embed=nova_embed("dAILY", f"yOU aLREADY cLAIMED yOUR dAILY! tRY aGAIN iN {hours}h {mins}m."), ephemeral=True)
        return
    daily_cooldowns[user_id] = now
    change_balance(interaction.user.id, 100, guild_id)
    await interaction.response.send_message(embed=nova_embed("dAILY", f"yOU cLAIMED yOUR dAILY 100 {CURRENCY_NAME}!"))

@bot.command()
async def work(ctx):
    now = datetime.now(dt_timezone.utc)
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

class NukeConfirmView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.value = None
    
    @discord.ui.button(label='Yes, Nuke It', style=discord.ButtonStyle.danger, emoji='💥')
    async def confirm_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can confirm this action!", ephemeral=True)
            return
        
        self.value = True
        self.stop()
        
        # Fetch messages before deleting to log them
        messages_to_delete = []
        async for message in self.ctx.channel.history(limit=1000):
            messages_to_delete.append(message)
        
        # Create a document of nuked messages
        if messages_to_delete:
            nuked_messages_log = f"Nuked Messages Log - {self.ctx.channel.name}\n"
            nuked_messages_log += f"Nuked by: {self.ctx.author} ({self.ctx.author.id})\n"
            nuked_messages_log += f"Nuked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            nuked_messages_log += f"Channel: #{self.ctx.channel.name} ({self.ctx.channel.id})\n"
            nuked_messages_log += "=" * 50 + "\n\n"
            
            for i, msg in enumerate(reversed(messages_to_delete), 1):
                timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
                content = msg.content or "[No text content]"
                attachments = ", ".join([att.filename for att in msg.attachments]) if msg.attachments else "None"
                
                nuked_messages_log += f"Message {i}:\n"
                nuked_messages_log += f"Author: {msg.author} ({msg.author.id})\n"
                nuked_messages_log += f"Timestamp: {timestamp}\n"
                nuked_messages_log += f"Content: {content}\n"
                nuked_messages_log += f"Attachments: {attachments}\n"
                nuked_messages_log += "-" * 30 + "\n\n"
            
            # Send the log as a file to the mod logs channel (server-specific)
            mod_logs_channel_id = get_server_config(self.ctx.guild.id, "mod_logs_channel_id")
            if mod_logs_channel_id:
                mod_logs_channel = self.ctx.guild.get_channel(mod_logs_channel_id)
                if mod_logs_channel:
                    file_content = nuked_messages_log.encode('utf-8')
                    filename = f"nuked_messages_{self.ctx.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    file = discord.File(io.BytesIO(file_content), filename=filename)
                    
                    embed = discord.Embed(
                        title="💥 Channel Nuked",
                        description=f"**Channel:** {self.ctx.channel.mention}\n**Moderator:** {self.ctx.author.mention}\n**Messages Deleted:** {len(messages_to_delete)}",
                        color=0xff0000,
                        timestamp=datetime.now()
                    )
                    await mod_logs_channel.send(embed=embed, file=file)
        
        # Now nuke the channel (delete all messages)
        deleted = await self.ctx.channel.purge(limit=1000)
        await self.ctx.send("💥 **BOOM!** Channel has been nuked!", delete_after=5)
        
        # Log the mod action
        await log_mod_action(self.ctx.guild, "nuke", self.ctx.author, None, f"Nuked all messages in {self.ctx.channel.mention} ({len(deleted)} messages)")
        
        # Update the interaction message
        await interaction.response.edit_message(
            embed=nova_embed("💥 nUKE cOMPLETE!", f"cHANNEL hAS bEEN nUKED! {len(deleted)} mESSAGES dELETED."),
            view=None
        )
    
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can cancel this action!", ephemeral=True)
            return
        
        self.value = False
        self.stop()
        
        await interaction.response.edit_message(
            embed=nova_embed("❌ nUKE cANCELLED", "nUKE oPERATION wAS cANCELLED."),
            view=None
        )
    
    async def on_timeout(self):
        # Disable all buttons on timeout
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(
                embed=nova_embed("⏰ nUKE tIMEOUT", "nUKE cONFIRMATION tIMED oUT. oPERATION cANCELLED."),
                view=self
            )
        except:
            pass

@bot.command()
async def nuke(ctx):
    print(f"\n🔥 NUKE COMMAND RECEIVED from {ctx.author} in {ctx.guild.name if ctx.guild else 'DM'}")
    if not has_mod_or_admin(ctx):
        print(f"❌ Permission check failed for {ctx.author}")
        await ctx.send("You don't have permission to use this command.")
        return
    print(f"✅ Permission check passed for {ctx.author}")
    
    # Create confirmation embed
    confirm_embed = nova_embed(
        "⚠️ nUKE cONFIRMATION",
        f"aRE yOU sURE yOU wANT tO nUKE #{ctx.channel.name}?\n\n"
        f"**⚠️ tHIS aCTION iS iRREVERSIBLE!**\n"
        f"aLL mESSAGES iN tHIS cHANNEL wILL bE pERMANENTLY dELETED!\n\n"
        f"📁 a bACKUP fILE wILL bE cREATED iN mOD lOGS\n"
        f"⏰ yOU hAVE 30 sECONDS tO cONFIRM"
    )
    
    view = NukeConfirmView(ctx)
    message = await ctx.send(embed=confirm_embed, view=view)
    view.message = message

@bot.command()
async def kick(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    if member is None:
        await ctx.send("Usage: ?kick @user [reason] - Kicks a member from the server. Only mods/admins can use this.")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member} for: {reason}")
        # Log the mod action
        await log_mod_action(ctx.guild, "kick", ctx.author, member, reason)
    except Exception as e:
        await ctx.send(f"Failed to kick: {e}")

@bot.command()
async def ban(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    if member is None:
        await ctx.send("Usage: ?ban @user [reason] - Bans a member from the server. Only mods/admins can use this.")
        return
    try:
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member} for: {reason}")
        # Log the mod action
        await log_mod_action(ctx.guild, "ban", ctx.author, member, reason)
    except Exception as e:
        await ctx.send(f"Failed to ban: {e}")

@bot.command()
async def clear(ctx, amount: int = None):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    if amount is None:
        await ctx.send("Usage: ?clear [amount] - Deletes a number of messages. Only mods/admins can use this.")
        return
    
    # Fetch messages before deleting to log them
    messages_to_delete = []
    async for message in ctx.channel.history(limit=amount):
        messages_to_delete.append(message)
    
    # Create a document of deleted messages
    if messages_to_delete:
        deleted_messages_log = f"Deleted Messages Log - {ctx.channel.name}\n"
        deleted_messages_log += f"Deleted by: {ctx.author} ({ctx.author.id})\n"
        deleted_messages_log += f"Deleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        deleted_messages_log += f"Channel: #{ctx.channel.name} ({ctx.channel.id})\n"
        deleted_messages_log += "=" * 50 + "\n\n"
        
        for i, msg in enumerate(reversed(messages_to_delete), 1):
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            content = msg.content or "[No text content]"
            attachments = ", ".join([att.filename for att in msg.attachments]) if msg.attachments else "None"
            
            deleted_messages_log += f"Message {i}:\n"
            deleted_messages_log += f"Author: {msg.author} ({msg.author.id})\n"
            deleted_messages_log += f"Timestamp: {timestamp}\n"
            deleted_messages_log += f"Content: {content}\n"
            deleted_messages_log += f"Attachments: {attachments}\n"
            deleted_messages_log += "-" * 30 + "\n\n"
        
        # Send the log as a file to the mod logs channel
        mod_logs_channel_id = get_server_config(ctx.guild.id, "mod_logs_channel_id")
        if mod_logs_channel_id:
            mod_logs_channel = ctx.guild.get_channel(mod_logs_channel_id)
            if mod_logs_channel:
                file_content = deleted_messages_log.encode('utf-8')
                filename = f"deleted_messages_{ctx.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                file = discord.File(io.BytesIO(file_content), filename=filename)
                
                embed = discord.Embed(
                    title="🗑️ Messages Cleared",
                    description=f"**Channel:** {ctx.channel.mention}\n**Moderator:** {ctx.author.mention}\n**Messages Deleted:** {len(messages_to_delete)}",
                    color=0xff0000,
                    timestamp=datetime.now()
                )
                await mod_logs_channel.send(embed=embed, file=file)
    
    # Now delete the messages
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Cleared {len(deleted)} messages", delete_after=3)
    
    # Log the mod action
    await log_mod_action(ctx.guild, "clear", ctx.author, None, f"Cleared {len(deleted)} messages in {ctx.channel.mention}")

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
    lyric = random.choice(lyrics)
    embed = discord.Embed(
        title="nICKI mINAJ lYRIC",
        description=lyric,
        color=0xff69b4
    )
    # Removed footer message per user request
    await ctx.send(embed=embed)

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
            msg = await ctx.send(embed=embed)
            await msg.add_reaction("<:bop:1399081053800501358>")
            await msg.add_reaction("<:flop:1398830540832116737>")
            return
    await ctx.send(f"{member.display_name} is not listening to Spotify right now.")

# Alias for spotify command
@bot.command(name="fm")
async def fm(ctx, member: discord.Member = None):
    """Show Spotify status for a user (alias for ?spotify)"""
    await spotify(ctx, member)

# Load environment variables
load_dotenv()

# Get token from environment variable
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("Error: TOKEN not found in .env file")
    exit(1)

# Slash command version of beg
@bot.tree.command(name="beg", description="Beg for money (10 min cooldown)")
async def beg_slash(interaction: discord.Interaction):
    now = datetime.now(dt_timezone.utc)
    user_id = interaction.user.id
    last = beg_cooldowns.get(user_id)
    if last and now - last < timedelta(minutes=10):
        rem = timedelta(minutes=10) - (now - last)
        await interaction.response.send_message(f"{interaction.user.mention}, you can beg again in {str(rem).split('.')[0]}", ephemeral=True)
        return
    beg_cooldowns[user_id] = now
    if random.random() < 0.5:
        await interaction.response.send_message(f"{interaction.user.mention}, no one gave you anything this time.")
    else:
        amount = random.randint(1, 20)
        change_balance(user_id, amount)
        await interaction.response.send_message(f"{interaction.user.mention}, you begged and got {amount} {CURRENCY_NAME}!")

# Slash command version of work
@bot.tree.command(name="work", description="Work a job to earn money (20 min cooldown)")
async def work_slash(interaction: discord.Interaction):
    now = datetime.now(dt_timezone.utc)
    user_id = interaction.user.id
    last = work_cooldowns.get(user_id)
    if last and now - last < timedelta(minutes=20):
        rem = timedelta(minutes=20) - (now - last)
        await interaction.response.send_message(f"{interaction.user.mention}, you can work again in {str(rem).split('.')[0]}", ephemeral=True)
        return
    work_cooldowns[user_id] = now
    jobs = ["chef", "barista", "programmer", "driver", "artist", "bjs"]
    job = random.choice(jobs)
    amount = random.randint(10, 50)
    change_balance(user_id, amount)
    await interaction.response.send_message(f"{interaction.user.mention}, you worked as a {job} and earned {amount} {CURRENCY_NAME}!")

# Slash command version of impregnate
@bot.tree.command(name="impregnate", description="Impregnate someone, child support paid randomly")
@app_commands.describe(partner="The user to impregnate")
async def impregnate_slash(interaction: discord.Interaction, partner: discord.Member):
    if partner.bot:
        await interaction.response.send_message("You cannot impregnate a bot!", ephemeral=True)
        return
    if partner.id == interaction.user.id:
        await interaction.response.send_message("You cannot impregnate yourself!", ephemeral=True)
        return
    payer_is_author = random.choice([True, False])
    child_support = 50
    payer = interaction.user if payer_is_author else partner
    receiver = partner if payer_is_author else interaction.user
    if get_balance(payer.id) < child_support:
        await interaction.response.send_message(f"{payer.mention} does not have enough {CURRENCY_NAME} to pay child support!", ephemeral=True)
        return
    change_balance(payer.id, -child_support)
    change_balance(receiver.id, child_support)
    await interaction.response.send_message(f"{interaction.user.mention} impregnated {partner.mention}!\n{payer.mention} pays {child_support} {CURRENCY_NAME} as child support to {receiver.mention}.")

# Slash command version of nuke
@bot.tree.command(name="nuke", description="Delete all messages in channel (mods only)")
async def nuke_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.purge(limit=1000)
    await interaction.response.send_message("boom")
    await interaction.followup.send("Usage: /nuke - Deletes all messages in the channel. Only mods/admins can use this.", ephemeral=True)

# Slash command version of kick
@bot.tree.command(name="kick", description="Kick a member (mods only)")
@app_commands.describe(member="The member to kick", reason="Reason for kick")
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"Kicked {member} for: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"Failed to kick: {e}", ephemeral=True)

# Slash command version of ban
@bot.tree.command(name="ban", description="Ban a member (mods only)")
@app_commands.describe(member="The member to ban", reason="Reason for ban")
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"Banned {member} for: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"Failed to ban: {e}", ephemeral=True)

# Slash command version of reactionroles
@bot.tree.command(name="reactionroles", description="Post gender role selection message")
async def reactionroles_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="Choose your gender role by reacting", color=0x00ff00)
    embed.description = (
        "React with the emoji to get the role:\n"
        "💙 for mALE\n"
        "💗 for fEMALE\n"
        "🤍 for oTHER (AKS)\n"
        "Remove your reaction to remove the role."
    )
    msg = await interaction.channel.send(embed=embed)
    global ROLE_MESSAGE_ID
    ROLE_MESSAGE_ID = msg.id
    for emoji in EMOJI_TO_ROLE:
        await msg.add_reaction(emoji)
    await interaction.response.send_message("Reaction roles message posted!", ephemeral=True)

# Slash command version of nicki
@bot.tree.command(name="nicki", description="Get a random Nicki Minaj lyric")
async def nicki_slash(interaction: discord.Interaction):
    lyrics = [
        "lIKE mJ dOCTOR, tHEY kILLIN mE. pROPOFOl, i kNOW tHEY hOPE i fALL.bUT tELL eM wINNIN iS mY mUTHUFUCKIN pROTOCOL..",
        "mE, nICKI m, i gOT tOO mANY wINS!!!",
        "aYO tONIGHT iS tHE nIGHT tHAT iMMMA gET tWISTED, mYX mOSCATO n vODKA iMA mIX iT.",
        "yOUR fLOW iS sUCH a bORE...",
        "aND i wILL rETIRE wITH tHE cROWN... yES!",
        "bE wHO yOU iS nEVER bE wHO yOU aRENT nEVA."
    ]
    await interaction.response.send_message(random.choice(lyrics))

# Slash command version of level
@bot.tree.command(name="level", description="Show your level and XP")
async def level_slash(interaction: discord.Interaction):
    data = get_level(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}, you are level {data['level']} with {data['xp']} XP.")

# Slash command version of leaderboard
@bot.tree.command(name="leaderboard", description="Show top 5 users by level")
async def leaderboard_slash(interaction: discord.Interaction):
    sorted_users = sorted(user_xp.items(), key=lambda x: x[1]['level'] * 100 + x[1]['xp'], reverse=True)
    top = "Top 5 users:\n"
    for i, (user_id, data) in enumerate(sorted_users[:5]):
        guild = interaction.guild
        member = guild.get_member(int(user_id)) if guild else None
        if member:
            top += f"{i+1}. {member.display_name} - Level {data['level']}\n"
    await interaction.response.send_message(top)

# Slash command version of spotify
@bot.tree.command(name="spotify", description="Show Spotify status for a user (or yourself)")
@app_commands.describe(member="The member to check (optional)")
async def spotify_slash(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    # Get the full member object from the guild
    if interaction.guild:
        member = interaction.guild.get_member(member.id)
    if not member:
        await interaction.response.send_message("Could not find that member.", ephemeral=True)
        return
    for activity in member.activities:
        if isinstance(activity, discord.Spotify):
            embed = discord.Embed(
                title=f"{member.display_name} is listening to Spotify!",
                description=f"**{activity.title}** by {activity.artist}\nAlbum: {activity.album}",
                color=0x1DB954
            )
            embed.set_thumbnail(url=activity.album_cover_url)
            embed.add_field(name="Track URL", value=f"[Open in Spotify](https://open.spotify.com/track/{activity.track_id})")
            msg = await interaction.channel.send(embed=embed)
            await msg.add_reaction("<:bop:1399081053800501358>")
            await msg.add_reaction("<:flop:1398830540832116737>")
            return
    await interaction.response.send_message(f"{member.display_name} is not listening to Spotify right now.")

# Slash command for fm (alias for spotify)
@bot.tree.command(name="fm", description="Show Spotify status for a user (alias for /spotify)")
@app_commands.describe(member="The member to check (optional)")
async def fm_slash(interaction: discord.Interaction, member: discord.Member = None):
    await spotify_slash(interaction, member)

# =========================
# Command Stubs for All Requested Features
# =========================

start_time = time.time()

# Utility
@bot.command()
async def ping(ctx):
    """Checks if Nova is online and returns latency."""
    await ctx.send(f'Pong! 🏓 Latency: {round(bot.latency * 1000)}ms')

@bot.command()
async def about(ctx):
    """Info about Nova."""
    embed = discord.Embed(
        title="aBOUT nOVA",
        description="i'M nOVA, yOUR aLL-iN-oNE dISCORD bOT. sASS, hELP, aND cHAOS iN oNE pACKAGE!",
        color=0xff69b4
    )
    embed.set_footer(text="cREATED bY mOTHER 💅")
    await ctx.send(embed=embed)

@bot.command()
async def uptime(ctx):
    """Shows how long Nova has been running."""
    up = int(time.time() - start_time)
    hours, remainder = divmod(up, 3600)
    minutes, seconds = divmod(remainder, 60)
    await ctx.send(f"Uptime: {hours}h {minutes}m {seconds}s")

# Relationship/Roleplay
@bot.command()
async def divorce(ctx, user: discord.Member):
    relationships = load_relationships()
    key = f"married:{ctx.author.id}"
    if key not in relationships or relationships[key] != user.id:
        await ctx.send(embed=nova_embed("dIVORCE", "yOU'RE nOT mARRIED tO tHAT pERSON!"))
        return
    del relationships[key]
    save_relationships(relationships)
    await ctx.send(embed=nova_embed("dIVORCE", f"💔 {ctx.author.display_name} dIVORCED {user.display_name}!"))

@bot.tree.command(name="divorce", description="End your marriage with a user")
async def divorce_slash(interaction: discord.Interaction, user: discord.Member):
    relationships = load_relationships()
    key = f"married:{interaction.user.id}"
    if key not in relationships or relationships[key] != user.id:
        await interaction.response.send_message(embed=nova_embed("dIVORCE", "yOU'RE nOT mARRIED tO tHAT pERSON!"))
        return
    del relationships[key]
    save_relationships(relationships)
    await interaction.response.send_message(embed=nova_embed("dIVORCE", f"💔 {interaction.user.display_name} dIVORCED {user.display_name}!"))

@bot.command()
async def marry(ctx, user: discord.Member):
    if user.id == ctx.author.id:
        await ctx.send(embed=nova_embed("mARRY", "yOU cAN'T mARRY yOURSELF, bABY!"))
        return
    relationships = load_relationships()
    key = f"married:{ctx.author.id}"
    if key in relationships:
        await ctx.send(embed=nova_embed("mARRY", "yOU'RE aLREADY mARRIED!"))
        return
    if user.id in pending_marriages:
        await ctx.send(embed=nova_embed("mARRY", "tHAT uSER aLREADY hAS a pENDING pROPOSAL!"))
        return
    pending_marriages[user.id] = ctx.author.id
    await ctx.send(embed=nova_embed("mARRY", f"💍 {ctx.author.display_name} pROPOSED tO {user.display_name}! {user.mention}, tYPE `?acceptmarry` tO aCCEPT. yOU hAVE 30 sECONDS!"))
    async def expire():
        await asyncio.sleep(30)
        if user.id in pending_marriages and pending_marriages[user.id] == ctx.author.id:
            del pending_marriages[user.id]
            await ctx.send(embed=nova_embed("mARRY", f"{user.display_name} dIDN'T rESPOND iN tIME! tRY aGAIN lATER."))
    ctx.bot.loop.create_task(expire())

@bot.tree.command(name="marry", description="Send a marriage proposal to a user")
@app_commands.describe(user="The user to marry")
async def marry_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("mARRY", "yOU cAN'T mARRY yOURSELF, bABY!"))
        return
    relationships = load_relationships()
    key = f"married:{interaction.user.id}"
    if key in relationships:
        await interaction.response.send_message(embed=nova_embed("mARRY", "yOU'RE aLREADY mARRIED!"))
        return
    if user.id in pending_marriages:
        await interaction.response.send_message(embed=nova_embed("mARRY", "tHAT uSER aLREADY hAS a pENDING pROPOSAL!"))
        return
    pending_marriages[user.id] = interaction.user.id
    await interaction.response.send_message(embed=nova_embed("mARRY", f"💍 {interaction.user.display_name} pROPOSED tO {user.display_name}! {user.mention}, uSE `/acceptmarry` tO aCCEPT. yOU hAVE 30 sECONDS!"))
    async def expire():
        await asyncio.sleep(30)
        if user.id in pending_marriages and pending_marriages[user.id] == interaction.user.id:
            del pending_marriages[user.id]
            await interaction.followup.send(embed=nova_embed("mARRY", f"{user.display_name} dIDN'T rESPOND iN tIME! tRY aGAIN lATER."))
    interaction.client.loop.create_task(expire())

@bot.command()
async def adopt(ctx, user: discord.Member):
    if user.id == ctx.author.id:
        await ctx.send(embed=nova_embed("aDOPT", "yOU cAN'T aDOPT yOURSELF!"))
        return
    relationships = load_relationships()
    
    # Check if user is already adopted by someone
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == user.id:
            adopter_id = int(key.split(":")[1])
            adopter = ctx.guild.get_member(adopter_id)
            if adopter:
                await ctx.send(embed=nova_embed("aDOPT", f"{user.display_name} iS aLREADY aDOPTED bY {adopter.display_name}!"))
                return
    
    if user.id in pending_adoptions:
        await ctx.send(embed=nova_embed("aDOPT", "tHAT uSER aLREADY hAS a pENDING aDOPTION!"))
        return
    pending_adoptions[user.id] = ctx.author.id
    view = AdoptionView(ctx.author.id, user.id)
    await ctx.send(embed=nova_embed("aDOPT", f"🍼 {ctx.author.display_name} wANTS tO aDOPT {user.display_name}! {user.mention}, cLICK tHE bUTTONS bELOW!"), view=view)

@bot.tree.command(name="adopt", description="Adopt a user (fun roleplay)")
@app_commands.describe(user="The user to adopt")
async def adopt_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("aDOPT", "yOU cAN'T aDOPT yOURSELF!"))
        return
    relationships = load_relationships()
    
    # Check if user is already adopted by someone
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == user.id:
            adopter_id = int(key.split(":")[1])
            adopter = interaction.guild.get_member(adopter_id)
            if adopter:
                await interaction.response.send_message(embed=nova_embed("aDOPT", f"{user.display_name} iS aLREADY aDOPTED bY {adopter.display_name}!"))
                return
    
    if user.id in pending_adoptions:
        await interaction.response.send_message(embed=nova_embed("aDOPT", "tHAT uSER aLREADY hAS a pENDING aDOPTION!"))
        return
    pending_adoptions[user.id] = interaction.user.id
    view = AdoptionView(interaction.user.id, user.id)
    await interaction.response.send_message(embed=nova_embed("aDOPT", f"🍼 {interaction.user.display_name} wANTS tO aDOPT {user.display_name}! {user.mention}, cLICK tHE bUTTONS bELOW!"), view=view)

class AdoptionView(View):
    def __init__(self, adopter_id, adoptee_id):
        super().__init__(timeout=30)
        self.adopter_id = adopter_id
        self.adoptee_id = adoptee_id

    @discord.ui.button(label="aCCEPT", style=discord.ButtonStyle.green, emoji="✅")
    async def accept_adoption(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.adoptee_id:
            await interaction.response.send_message(embed=nova_embed("aDOPTION", "tHIS aDOPTION iS nOT fOR yOU!"), ephemeral=True)
            return
        
        if self.adoptee_id not in pending_adoptions or pending_adoptions[self.adoptee_id] != self.adopter_id:
            await interaction.response.send_message(embed=nova_embed("aDOPTION", "tHIS aDOPTION hAS eXPIRED!"), ephemeral=True)
            return
        
        adopter = interaction.guild.get_member(self.adopter_id)
        if not adopter:
            await interaction.response.send_message(embed=nova_embed("aDOPTION", "aDOPTER nOT fOUND!"), ephemeral=True)
            return
        
        relationships = load_relationships()
        key = f"adopted:{self.adopter_id}"
        relationships[key] = self.adoptee_id
        save_relationships(relationships)
        
        del pending_adoptions[self.adoptee_id]
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(
            embed=nova_embed("aDOPTION aCCEPTED", f"🍼 {interaction.user.display_name} hAS bEEN aDOPTED bY {adopter.display_name}!"),
            view=self
        )

    @discord.ui.button(label="dECLINE", style=discord.ButtonStyle.red, emoji="❌")
    async def decline_adoption(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.adoptee_id:
            await interaction.response.send_message(embed=nova_embed("aDOPTION", "tHIS aDOPTION iS nOT fOR yOU!"), ephemeral=True)
            return
        
        if self.adoptee_id not in pending_adoptions or pending_adoptions[self.adoptee_id] != self.adopter_id:
            await interaction.response.send_message(embed=nova_embed("aDOPTION", "tHIS aDOPTION hAS eXPIRED!"), ephemeral=True)
            return
        
        adopter = interaction.guild.get_member(self.adopter_id)
        adopter_name = adopter.display_name if adopter else "Unknown"
        
        del pending_adoptions[self.adoptee_id]
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(
            embed=nova_embed("aDOPTION dECLINED", f"😔 {interaction.user.display_name} dECLINED tHE aDOPTION fROM {adopter_name}!"),
            view=self
        )

@bot.command()
async def emancipate(ctx, user: discord.Member):
    relationships = load_relationships()
    key = f"adopted:{ctx.author.id}"
    if key not in relationships or relationships[key] != user.id:
        await ctx.send(embed=nova_embed("eMANCIPATE", "yOU hAVEN'T aDOPTED tHAT pERSON!"))
        return
    del relationships[key]
    save_relationships(relationships)
    await ctx.send(embed=nova_embed("eMANCIPATE", f"{user.display_name} hAS bEEN eMANCIPATED bY {ctx.author.display_name}!"))

@bot.tree.command(name="emancipate", description="Free a previously adopted user")
async def emancipate_slash(interaction: discord.Interaction, user: discord.Member):
    relationships = load_relationships()
    key = f"adopted:{interaction.user.id}"
    if key not in relationships or relationships[key] != user.id:
        await interaction.response.send_message(embed=nova_embed("eMANCIPATE", "yOU hAVEN'T aDOPTED tHAT pERSON!"))
        return
    del relationships[key]
    save_relationships(relationships)
    await interaction.response.send_message(embed=nova_embed("eMANCIPATE", f"{user.display_name} hAS bEEN eMANCIPATED bY {interaction.user.display_name}!"))

@bot.command()
async def getemancipated(ctx):
    relationships = load_relationships()
    
    # Find if user is adopted by someone
    adopted_by = None
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == ctx.author.id:
            adopter_id = int(key.split(":")[1])
            adopted_by = ctx.guild.get_member(adopter_id)
            break
    
    if not adopted_by:
        await ctx.send(embed=nova_embed("gET eMANCIPATED", "yOU aREN'T aDOPTED bY aNYONE!"))
        return
    
    # Remove the adoption
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == ctx.author.id:
            del relationships[key]
            break
    
    save_relationships(relationships)
    await ctx.send(embed=nova_embed("gET eMANCIPATED", f"🏛️ {ctx.author.display_name} hAS bEEN eMANCIPATED fROM {adopted_by.display_name}! yOU aRE nOW fREE!"))

@bot.tree.command(name="getemancipated", description="Emancipate yourself from your adoptive parent")
async def getemancipated_slash(interaction: discord.Interaction):
    relationships = load_relationships()
    
    # Find if user is adopted by someone
    adopted_by = None
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == interaction.user.id:
            adopter_id = int(key.split(":")[1])
            adopted_by = interaction.guild.get_member(adopter_id)
            break
    
    if not adopted_by:
        await interaction.response.send_message(embed=nova_embed("gET eMANCIPATED", "yOU aREN'T aDOPTED bY aNYONE!"), ephemeral=True)
        return
    
    # Remove the adoption
    for key, value in relationships.items():
        if key.startswith("adopted:") and value == interaction.user.id:
            del relationships[key]
            break
    
    save_relationships(relationships)
    await interaction.response.send_message(embed=nova_embed("gET eMANCIPATED", f"🏛️ {interaction.user.display_name} hAS bEEN eMANCIPATED fROM {adopted_by.display_name}! yOU aRE nOW fREE!"))

@bot.command()
async def familytree(ctx, user: discord.Member = None):
    user = user or ctx.author
    relationships = load_relationships()
    
    # Find spouse
    spouse = None
    for key, value in relationships.items():
        if key.startswith("married:"):
            user_id = int(key.split(":")[1])
            if user_id == user.id:
                spouse = ctx.guild.get_member(value)
                break
            elif value == user.id:
                spouse = ctx.guild.get_member(user_id)
                break
    
    # Find children (people this user has adopted)
    children = []
    for key, value in relationships.items():
        if key.startswith("adopted:"):
            adopter_id = int(key.split(":")[1])
            if adopter_id == user.id:
                child = ctx.guild.get_member(value)
                if child:
                    children.append(child)
    
    # Find parents (people who adopted this user)
    parents = []
    for key, value in relationships.items():
        if key.startswith("adopted:"):
            if value == user.id:
                adopter_id = int(key.split(":")[1])
                parent = ctx.guild.get_member(adopter_id)
                if parent:
                    parents.append(parent)
    
    # Build family tree
    tree = f"**fAMILY tREE fOR {user.display_name}**\n\n"
    
    if spouse:
        tree += f"💍 **sPOUSE:** {spouse.display_name}\n"
    else:
        tree += "💍 **sPOUSE:** nONE\n"
    
    if children:
        tree += f"👶 **cHILDREN:** {', '.join([child.display_name for child in children])}\n"
    else:
        tree += "👶 **cHILDREN:** nONE\n"
    
    if parents:
        tree += f"👨‍👩‍👧‍👦 **pARENTS:** {', '.join([parent.display_name for parent in parents])}\n"
    else:
        tree += "👨‍👩‍👧‍👦 **pARENTS:** nONE\n"
    
    await ctx.send(embed=nova_embed("fAMILY tREE", tree))

@bot.tree.command(name="familytree", description="Show family tree for a user")
@app_commands.describe(user="The user to check (optional - shows your own)")
async def familytree_slash(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    relationships = load_relationships()
    
    # Find spouse
    spouse = None
    for key, value in relationships.items():
        if key.startswith("married:"):
            user_id = int(key.split(":")[1])
            if user_id == user.id:
                spouse = interaction.guild.get_member(value)
                break
            elif value == user.id:
                spouse = interaction.guild.get_member(user_id)
                break
    
    # Find children (people this user has adopted)
    children = []
    for key, value in relationships.items():
        if key.startswith("adopted:"):
            adopter_id = int(key.split(":")[1])
            if adopter_id == user.id:
                child = interaction.guild.get_member(value)
                if child:
                    children.append(child)
    
    # Find parents (people who adopted this user)
    parents = []
    for key, value in relationships.items():
        if key.startswith("adopted:"):
            if value == user.id:
                adopter_id = int(key.split(":")[1])
                parent = interaction.guild.get_member(adopter_id)
                if parent:
                    parents.append(parent)
    
    # Build family tree
    tree = f"**fAMILY tREE fOR {user.display_name}**\n\n"
    
    if spouse:
        tree += f"💍 **sPOUSE:** {spouse.display_name}\n"
    else:
        tree += "💍 **sPOUSE:** nONE\n"
    
    if children:
        tree += f"👶 **cHILDREN:** {', '.join([child.display_name for child in children])}\n"
    else:
        tree += "👶 **cHILDREN:** nONE\n"
    
    if parents:
        tree += f"👨‍👩‍👧‍👦 **pARENTS:** {', '.join([parent.display_name for parent in parents])}\n"
    else:
        tree += "👨‍👩‍👧‍👦 **pARENTS:** nONE\n"
    
    await interaction.response.send_message(embed=nova_embed("fAMILY tREE", tree))

@bot.command()
async def kiss(ctx, user: discord.Member):
    if user.id == ctx.author.id:
        await ctx.send(embed=nova_embed("kISS", "yOU cAN'T kISS yOURSELF!"))
        return
    responses = [
        f"💋 {ctx.author.mention} kISSES {user.mention} gENTLY!",
        f"😘 {ctx.author.mention} gIVES {user.mention} a sWEET kISS!",
        f"💕 {ctx.author.mention} pLANTS a kISS oN {user.display_name}'s cHEEK!",
        f"🥰 {ctx.author.mention} kISSES {user.display_name} pASSIONATELY!"
    ]
    await ctx.send(embed=nova_embed("kISS", random.choice(responses)))

@bot.tree.command(name="kiss", description="Kiss a user (fun roleplay)")
@app_commands.describe(user="The user to kiss")
async def kiss_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("kISS", "yOU cAN'T kISS yOURSELF!"))
        return
    responses = [
        f"�� {interaction.user.mention} kISSES {user.mention} gENTLY!",
        f"😘 {interaction.user.mention} gIVES {user.mention} a sWEET kISS!",
        f"💕 {interaction.user.mention} pLANTS a kISS oN {user.display_name}'s cHEEK!",
        f"🥰 {interaction.user.mention} kISSES {user.display_name} pASSIONATELY!"
    ]
    await interaction.response.send_message(embed=nova_embed("kISS", random.choice(responses)))

@bot.command()
async def slap(ctx, user: discord.Member):
    if user.id == ctx.author.id:
        await ctx.send(embed=nova_embed("sLAP", "yOU cAN'T sLAP yOURSELF!"))
        return
    responses = [
        f"👋 {ctx.author.mention} sLAPS {user.mention} aCROSS tHE fACE!",
        f"💥 {ctx.author.mention} gIVES {user.mention} a hARD sLAP!",
        f"🤚 {ctx.author.mention} sLAPS {user.mention} wITH a tOWEL!",
        f"💢 {ctx.author.mention} sLAPS {user.display_name} fOR bEING nAUGHTY!"
    ]
    await ctx.send(embed=nova_embed("sLAP", random.choice(responses)))

@bot.tree.command(name="slap", description="Slap a user (fun roleplay)")
@app_commands.describe(user="The user to slap")
async def slap_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("sLAP", "yOU cAN'T sLAP yOURSELF!"))
        return
    responses = [
        f"�� {interaction.user.mention} sLAPS {user.mention} aCROSS tHE fACE!",
        f"💥 {interaction.user.mention} gIVES {user.mention} a hARD sLAP!",
        f"🤚 {interaction.user.mention} sLAPS {user.mention} wITH a tOWEL!",
        f"💢 {interaction.user.mention} sLAPS {user.display_name} fOR bEING nAUGHTY!"
    ]
    await interaction.response.send_message(embed=nova_embed("sLAP", random.choice(responses)))

@bot.command()
async def whoasked(ctx, user: discord.Member = None):
    if not user:
        await ctx.send(embed=nova_embed("wHO aSKED", "nOBODY aSKED fOR yOUR oPINION!"))
        return
    responses = [
        f"🤔 wHO aSKED {user.display_name}?",
        f"❓ dID aNYONE aSK {user.display_name}?",
        f"🤷‍♀️ nOBODY aSKED {user.display_name}!",
        f"🙄 wHO eVEN aSKED {user.display_name}?"
    ]
    await ctx.send(embed=nova_embed("wHO aSKED", random.choice(responses)))

@bot.tree.command(name="whoasked", description="Ask who asked for someone's opinion")
@app_commands.describe(user="The user to question (optional)")
async def whoasked_slash(interaction: discord.Interaction, user: discord.Member = None):
    if not user:
        await interaction.response.send_message(embed=nova_embed("wHO aSKED", "nOBODY aSKED fOR yOUR oPINION!"))
        return
    responses = [
        f"🤔 wHO aSKED {user.display_name}?",
        f"❓ dID aNYONE aSK {user.display_name}?",
        f"🤷‍♀️ nOBODY aSKED {user.display_name}!",
        f"🙄 wHO eVEN aSKED {user.display_name}?"
    ]
    await interaction.response.send_message(embed=nova_embed("wHO aSKED", random.choice(responses)))

@bot.command()
async def voguebattle(ctx, user: discord.Member):
    if user.id == ctx.author.id:
        await ctx.send(embed=nova_embed("vOGUE bATTLE", "yOU cAN'T bATTLE yOURSELF!"))
        return
    
    # Vogue battle moves
    moves = [
        "DUCK WALK",
        "DEATH DROP", 
        "HAND PERFORMANCE",
        "CATWALK",
        "FACE",
        "LIPSYNC",
        "SHABLAM",
        "FIERCE POSE",
        "DIAMOND POSE",
        "STAR POSE"
    ]
    
    # Battle results
    results = [
        f"🏆 **{ctx.author.display_name}** WINS THE VOGUE BATTLE! {user.display_name} COULDN'T HANDLE THE FIERCENESS!",
        f"💀 **{user.display_name}** DESTROYS {ctx.author.display_name} IN THE BATTLE! TOTAL ANNIHILATION!",
        f"🤝 IT'S A TIE! BOTH **{ctx.author.display_name}** AND **{user.display_name}** ARE EQUALLY FIERCE!",
        f"🔥 **{ctx.author.display_name}** SERVES FACE AND WINS! {user.display_name} IS SHOOK!",
        f"💅 **{user.display_name}** TURNS IT OUT AND WINS! {ctx.author.display_name} IS GAGGED!"
    ]
    
    # Random moves for both users
    author_move = random.choice(moves)
    opponent_move = random.choice(moves)
    
    # Determine winner (random with slight bias to author)
    winner = random.choice(results)
    
    battle_text = f"**VOGUE BATTLE: {ctx.author.display_name} vs {user.display_name}**\n\n"
    battle_text += f"💃 **{ctx.author.display_name}**: {author_move}\n"
    battle_text += f"🕺 **{user.display_name}**: {opponent_move}\n\n"
    battle_text += f"**RESULT:** {winner}"
    
    await ctx.send(embed=nova_embed("vOGUE bATTLE", battle_text))

@bot.tree.command(name="voguebattle", description="Start a vogue battle with another user")
@app_commands.describe(user="The user to battle")
async def voguebattle_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("vOGUE bATTLE", "yOU cAN'T bATTLE yOURSELF!"))
        return
    
    # Vogue battle moves
    moves = [
        "DUCK WALK",
        "DEATH DROP", 
        "HAND PERFORMANCE",
        "CATWALK",
        "FACE",
        "LIPSYNC",
        "SHABLAM",
        "FIERCE POSE",
        "DIAMOND POSE",
        "STAR POSE"
    ]
    
    # Battle results
    results = [
        f"🏆 **{interaction.user.display_name}** WINS THE VOGUE BATTLE! {user.display_name} COULDN'T HANDLE THE FIERCENESS!",
        f"💀 **{user.display_name}** DESTROYS {interaction.user.display_name} IN THE BATTLE! TOTAL ANNIHILATION!",
        f"🤝 IT'S A TIE! BOTH **{interaction.user.display_name}** AND **{user.display_name}** ARE EQUALLY FIERCE!",
        f"🔥 **{interaction.user.display_name}** SERVES FACE AND WINS! {user.display_name} IS SHOOK!",
        f"💅 **{user.display_name}** TURNS IT OUT AND WINS! {interaction.user.display_name} IS GAGGED!"
    ]
    
    # Random moves for both users
    author_move = random.choice(moves)
    opponent_move = random.choice(moves)
    
    # Determine winner (random with slight bias to author)
    winner = random.choice(results)
    
    battle_text = f"**VOGUE BATTLE: {interaction.user.display_name} vs {user.display_name}**\n\n"
    battle_text += f"💃 **{interaction.user.display_name}**: {author_move}\n"
    battle_text += f"🕺 **{user.display_name}**: {opponent_move}\n\n"
    battle_text += f"**RESULT:** {winner}"
    
    await interaction.response.send_message(embed=nova_embed("vOGUE BATTLE", battle_text))
@bot.command()
async def lock(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("lOCK", "yOU dON'T hAVE pERMISSION!"))
        return
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=nova_embed("lOCK", f"🔒 {ctx.channel.mention} hAS bEEN lOCKED!"))
        await ctx.send("Usage: ?lock - Locks the current channel. Only mods/admins can use this.")
    except Exception:
        await ctx.send(embed=nova_embed("lOCK", "cOULD nOT lOCK tHE cHANNEL!"))

@bot.tree.command(name="lock", description="Lock the current channel (mods only)")
async def lock_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("lOCK", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=nova_embed("lOCK", f"🔒 {interaction.channel.mention} hAS bEEN lOCKED!"))
        await interaction.followup.send("Usage: /lock - Locks the current channel. Only mods/admins can use this.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(embed=nova_embed("lOCK", "cOULD nOT lOCK tHE cHANNEL!"), ephemeral=True)

@bot.command()
async def unlock(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNLOCK", "yOU dON'T hAVE pERMISSION!"))
        return
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=nova_embed("uNLOCK", f"🔓 {ctx.channel.mention} hAS bEEN uNLOCKED!"))
        await ctx.send("Usage: ?unlock - Unlocks the current channel. Only mods/admins can use this.")
    except Exception:
        await ctx.send(embed=nova_embed("uNLOCK", "cOULD nOT uNLOCK tHE cHANNEL!"))

@bot.tree.command(name="unlock", description="Unlock the current channel (mods only)")
async def unlock_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("uNLOCK", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(embed=nova_embed("uNLOCK", f"🔓 {interaction.channel.mention} hAS bEEN uNLOCKED!"))
        await interaction.followup.send("Usage: /unlock - Unlocks the current channel. Only mods/admins can use this.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(embed=nova_embed("uNLOCK", "cOULD nOT uNLOCK tHE cHANNEL!"), ephemeral=True)

# Pending adoptions
pending_adoptions = {}  # user_id: adopter_id

@bot.command()
async def afk(ctx, *, reason: str = "aFK"):
    AFK_STATUS[ctx.author.id] = {"reason": reason, "since": datetime.now(dt_timezone.utc), "mentions": set()}
    save_afk()  # Save AFK data after setting status
    await ctx.send(embed=nova_embed("aFK", f"{ctx.author.display_name} iS nOW aFK: {reason}"))

@bot.tree.command(name="afk", description="Set your AFK status")
@app_commands.describe(reason="Reason for being AFK")
async def afk_slash(interaction: discord.Interaction, reason: str = "aFK"):
    AFK_STATUS[interaction.user.id] = {"reason": reason, "since": datetime.now(dt_timezone.utc), "mentions": set()}
    save_afk()  # Save AFK data after setting status
    await interaction.response.send_message(embed=nova_embed("aFK", f"{interaction.user.display_name} iS nOW aFK: {reason}"))

@bot.command()
async def reactionadd(ctx, trigger_word: str = None, emoji: str = None):
    """Add auto-reaction to trigger words (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rEACTION aDD", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not trigger_word or not emoji:
        await ctx.send(embed=nova_embed("rEACTION aDD", "Usage: `?reactionadd <trigger_word> <emoji>`\n\nExample: `?reactionadd nova 💖`"))
        return
    
    # Test if the emoji is valid by trying to add it as a reaction
    try:
        await ctx.message.add_reaction(emoji)
        await ctx.message.remove_reaction(emoji, bot.user)
    except discord.HTTPException:
        await ctx.send(embed=nova_embed("rEACTION aDD", "iNVALID eMOJI! pLEASE uSE a vALID uNICODE eMOJI oR sERVER eMOJI."))
        return
    
    trigger_word = trigger_word.lower()
    guild_id = str(ctx.guild.id)
    
    # Make server-specific
    if guild_id not in AUTO_REACTIONS:
        AUTO_REACTIONS[guild_id] = {}
    
    AUTO_REACTIONS[guild_id][trigger_word] = emoji
    
    # Save to persistence
    with open("auto_reactions.json", "w") as f:
        json.dump(AUTO_REACTIONS, f, indent=2)
    
    await ctx.send(embed=nova_embed(
        "✅ rEACTION aDDED!",
        f"nOVA wILL nOW rEACT wITH {emoji} wHEN sOMEONE sAYS '{trigger_word}' iN tHIS sERVER!"
    ))

@bot.command()
async def reactionremove(ctx, trigger_word: str = None):
    """Remove auto-reaction for trigger word (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rEACTION rEMOVE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not trigger_word:
        await ctx.send(embed=nova_embed("rEACTION rEMOVE", "Usage: `?reactionremove <trigger_word>`\n\nExample: `?reactionremove nova`"))
        return
    
    trigger_word = trigger_word.lower()
    guild_id = str(ctx.guild.id)
    
    if guild_id in AUTO_REACTIONS and trigger_word in AUTO_REACTIONS[guild_id]:
        removed_emoji = AUTO_REACTIONS[guild_id][trigger_word]
        del AUTO_REACTIONS[guild_id][trigger_word]
        
        # Clean up empty guild entries
        if not AUTO_REACTIONS[guild_id]:
            del AUTO_REACTIONS[guild_id]
        
        # Save to persistence
        with open("auto_reactions.json", "w") as f:
            json.dump(AUTO_REACTIONS, f, indent=2)
        
        await ctx.send(embed=nova_embed(
            "✅ rEACTION rEMOVED!",
            f"nOVA wILL nO lONGER rEACT tO '{trigger_word}' iN tHIS sERVER (wAS {removed_emoji})"
        ))
    else:
        await ctx.send(embed=nova_embed("rEACTION rEMOVE", f"nO rEACTION fOUND fOR '{trigger_word}' iN tHIS sERVER"))

@bot.tree.command(name="reactionremove", description="Remove auto-reaction for trigger word (admin exclusive)")
@app_commands.describe(trigger_word="The trigger word to remove auto-reaction for")
async def reactionremove_slash(interaction: discord.Interaction, trigger_word: str):
    """Remove auto-reaction for trigger word (slash command version)"""
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("rEACTION rEMOVE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    trigger_word = trigger_word.lower()
    if trigger_word in AUTO_REACTIONS:
        removed_emoji = AUTO_REACTIONS.pop(trigger_word)
        await interaction.response.send_message(embed=nova_embed(
            "🗑️ rEACTION rEMOVED!",
            f"nOVA wILL nO lONGER rEACT tO '{trigger_word}' (wAS {removed_emoji})"
        ))
    else:
        await interaction.response.send_message(embed=nova_embed("rEACTION rEMOVE", f"nO aUTO-rEACTION fOUND fOR '{trigger_word}'"), ephemeral=True)

@bot.command()
async def reactionlist(ctx):
    """List all auto-reactions (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rEACTION lIST", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not AUTO_REACTIONS:
        await ctx.send(embed=nova_embed("rEACTION lIST", "nO aUTO-rEACTIONS sET uP!"))
        return
    
    reaction_list = "\n".join([f"**{word}** → {emoji}" for word, emoji in AUTO_REACTIONS.items()])
    await ctx.send(embed=nova_embed(
        "🎭 aUTO-rEACTIONS",
        f"cURRENT aUTO-rEACTIONS:\n\n{reaction_list}"
    ))

@bot.command()
async def messagecount(ctx, member: discord.Member = None):
    """Show message count statistics for a user"""
    target = member or ctx.author
    
    # Calculate time periods
    now = datetime.now(dt_timezone.utc)
    one_month_ago = now - timedelta(days=30)
    three_months_ago = now - timedelta(days=90)
    one_year_ago = now - timedelta(days=365)
    
    # Initialize counters
    last_month = 0
    last_3_months = 0
    last_year = 0
    lifetime = 0
    
    # Count messages in all text channels the bot can see
    embed = nova_embed(
        "📊 mESSAGE cOUNT aNALYSIS",
        f"aNALYZING mESSAGES fOR {target.display_name}...\n\n⏳ tHIS mAY tAKE a mOMENT..."
    )
    status_msg = await ctx.send(embed=embed)
    
    try:
        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).read_message_history:
                continue
            
            try:
                async for message in channel.history(limit=None, oldest_first=False):
                    if message.author.id != target.id:
                        continue
                    
                    lifetime += 1
                    
                    if message.created_at >= one_year_ago:
                        last_year += 1
                    
                    if message.created_at >= three_months_ago:
                        last_3_months += 1
                    
                    if message.created_at >= one_month_ago:
                        last_month += 1
                    
                    # Stop if we've gone past a year
                    if message.created_at < one_year_ago:
                        break
                        
            except discord.Forbidden:
                continue  # Skip channels we can't read
            except Exception:
                continue  # Skip channels with errors
        
        # Calculate daily averages
        daily_last_month = round(last_month / 30, 1) if last_month > 0 else 0
        daily_last_3_months = round(last_3_months / 90, 1) if last_3_months > 0 else 0
        daily_last_year = round(last_year / 365, 1) if last_year > 0 else 0
        
        # Create final embed
        embed = nova_embed(
            "📊 mESSAGE cOUNT sTATISTICS",
            f"**uSER:** {target.display_name}\n\n"
            f"📅 **lAST mONTH:** {last_month:,} messages ({daily_last_month}/day avg)\n"
            f"📅 **lAST 3 mONTHS:** {last_3_months:,} messages ({daily_last_3_months}/day avg)\n"
            f"📅 **lAST yEAR:** {last_year:,} messages ({daily_last_year}/day avg)\n"
            f"📅 **lIFETIME:** {lifetime:,} messages\n\n"
            f"*aNALYZED aLL vISIBLE cHANNELS iN {ctx.guild.name}*"
        )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        await status_msg.edit(embed=embed)
        
    except Exception as e:
        error_embed = nova_embed(
            "❌ eRROR",
            f"cOULD nOT aNALYZE mESSAGE cOUNT: {str(e)}"
        )
        await status_msg.edit(embed=error_embed)

@bot.tree.command(name="messagecount", description="Show message count statistics for a user")
@app_commands.describe(member="The member to analyze (defaults to yourself)")
async def messagecount_slash(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    
    # Calculate time periods
    now = datetime.now(dt_timezone.utc)
    one_month_ago = now - timedelta(days=30)
    three_months_ago = now - timedelta(days=90)
    one_year_ago = now - timedelta(days=365)
    
    # Initialize counters
    last_month = 0
    last_3_months = 0
    last_year = 0
    lifetime = 0
    
    # Count messages in all text channels the bot can see
    embed = nova_embed(
        "📊 mESSAGE cOUNT aNALYSIS",
        f"aNALYZING mESSAGES fOR {target.display_name}...\n\n⏳ tHIS mAY tAKE a mOMENT..."
    )
    await interaction.response.send_message(embed=embed)
    
    try:
        for channel in interaction.guild.text_channels:
            if not channel.permissions_for(interaction.guild.me).read_message_history:
                continue
            
            try:
                async for message in channel.history(limit=None, oldest_first=False):
                    if message.author.id != target.id:
                        continue
                    
                    lifetime += 1
                    
                    if message.created_at >= one_year_ago:
                        last_year += 1
                    
                    if message.created_at >= three_months_ago:
                        last_3_months += 1
                    
                    if message.created_at >= one_month_ago:
                        last_month += 1
                    
                    # Stop if we've gone past a year
                    if message.created_at < one_year_ago:
                        break
                        
            except discord.Forbidden:
                continue  # Skip channels we can't read
            except Exception:
                continue  # Skip channels with errors
        
        # Calculate daily averages
        daily_last_month = round(last_month / 30, 1) if last_month > 0 else 0
        daily_last_3_months = round(last_3_months / 90, 1) if last_3_months > 0 else 0
        daily_last_year = round(last_year / 365, 1) if last_year > 0 else 0
        
        # Create final embed
        embed = nova_embed(
            "📊 mESSAGE cOUNT sTATISTICS",
            f"**uSER:** {target.display_name}\n\n"
            f"📅 **lAST mONTH:** {last_month:,} messages ({daily_last_month}/day avg)\n"
            f"📅 **lAST 3 mONTHS:** {last_3_months:,} messages ({daily_last_3_months}/day avg)\n"
            f"📅 **lAST yEAR:** {last_year:,} messages ({daily_last_year}/day avg)\n"
            f"📅 **lIFETIME:** {lifetime:,} messages\n\n"
            f"*aNALYZED aLL vISIBLE cHANNELS iN {interaction.guild.name}*"
        )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        await interaction.edit_original_response(embed=embed)
        
    except Exception as e:
        error_embed = nova_embed(
            "❌ eRROR",
            f"cOULD nOT aNALYZE mESSAGE cOUNT: {str(e)}"
        )
        await interaction.edit_original_response(embed=error_embed)

@bot.command()
async def disable(ctx, command_name: str = None):
    """Disable a command (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("dISABLE cOMMAND", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not command_name:
        await ctx.send(embed=nova_embed("dISABLE cOMMAND", "Usage: `?disable <command_name>`\n\nExample: `?disable work`"))
        return
    
    # Don't allow disabling critical commands
    critical_commands = {'disable', 'enable', 'help', 'setwelcome', 'setfarewell', 'setruleschannel'}
    if command_name.lower() in critical_commands:
        await ctx.send(embed=nova_embed("dISABLE cOMMAND", f"cANNOT dISABLE cRITICAL cOMMAND '{command_name}'!"))
        return
    
    # Check if command exists
    command = bot.get_command(command_name)
    if not command:
        await ctx.send(embed=nova_embed("dISABLE cOMMAND", f"cOMMAND '{command_name}' nOT fOUND!"))
        return
    
    if command_name.lower() in DISABLED_COMMANDS:
        await ctx.send(embed=nova_embed("dISABLE cOMMAND", f"cOMMAND '{command_name}' iS aLREADY dISABLED!"))
        return
    
    DISABLED_COMMANDS.add(command_name.lower())
    await ctx.send(embed=nova_embed(
        "🚫 cOMMAND dISABLED!",
        f"cOMMAND '{command_name}' hAS bEEN dISABLED!"
    ))

@bot.command()
async def enable(ctx, command_name: str = None):
    """Enable a previously disabled command (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("eNABLE cOMMAND", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not command_name:
        await ctx.send(embed=nova_embed("eNABLE cOMMAND", "Usage: `?enable <command_name>`\n\nExample: `?enable work`"))
        return
    
    if command_name.lower() not in DISABLED_COMMANDS:
        await ctx.send(embed=nova_embed("eNABLE cOMMAND", f"cOMMAND '{command_name}' iS nOT dISABLED!"))
        return
    
    DISABLED_COMMANDS.remove(command_name.lower())
    await ctx.send(embed=nova_embed(
        "✅ cOMMAND eNABLED!",
        f"cOMMAND '{command_name}' hAS bEEN eNABLED!"
    ))

@bot.command()
async def disabledcommands(ctx):
    """List all disabled commands (admin exclusive)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("dISABLED cOMMANDS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not DISABLED_COMMANDS:
        await ctx.send(embed=nova_embed("dISABLED cOMMANDS", "nO cOMMANDS aRE cURRENTLY dISABLED!"))
        return
    
    disabled_list = "\n".join([f"• {cmd}" for cmd in sorted(DISABLED_COMMANDS)])
    await ctx.send(embed=nova_embed(
        "🚫 dISABLED cOMMANDS",
        f"cURRENTLY dISABLED cOMMANDS:\n\n{disabled_list}"
    ))

class MentionsView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="cHECK mENTIONS", style=discord.ButtonStyle.primary)
    async def check_mentions(self, interaction: discord.Interaction, button: Button):
        afk = AFK_STATUS.get(self.user_id)
        if not afk or not afk["mentions"]:
            await interaction.response.send_message(embed=nova_embed("aFK", "nO oNE mENTIONED yOU wHILE yOU wERE aWAY!"), ephemeral=True)
            return
        guild = interaction.guild
        names = []
        for uid in afk["mentions"]:
            member = guild.get_member(uid)
            if member:
                names.append(member.display_name)
        if names:
            await interaction.response.send_message(embed=nova_embed("aFK mENTIONS", f"yOU wERE mENTIONED bY: {', '.join(names)}"), ephemeral=True)
        else:
            await interaction.response.send_message(embed=nova_embed("aFK", "nO oNE mENTIONED yOU wHILE yOU wERE aWAY!"), ephemeral=True)



@bot.command()
async def mute(ctx, member: discord.Member = None):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("mUTE", "yOU dON'T hAVE pERMISSION!"))
        return
    if not member:
        await ctx.send(embed=nova_embed("mUTE", "yOU nEED tO mENTION sOMEONE!"))
        return
    if member == ctx.author:
        await ctx.send(embed=nova_embed("mUTE", "nICE tRY, bUT yOU cAN'T mUTE yOURSELF!"))
        return
    role = await get_or_create_muted_role(ctx.guild)
    if not role:
        await ctx.send(embed=nova_embed("mUTE", "cOULD nOT cREATE oR fIND tHE mUTED rOLE!"))
        return
    if role in member.roles:
        await ctx.send(embed=nova_embed("mUTE", f"{member.mention} iS aLREADY mUTED!"))
        return
    try:
        await member.add_roles(role, reason="Muted by Nova")
        await ctx.send(embed=nova_embed("mUTE", f"{member.mention} hAS bEEN mUTED sERVER-WIDE!"))
        await ctx.send("Usage: ?mute @user - Mutes a member server-wide. Only mods/admins can use this.")
    except Exception:
        await ctx.send(embed=nova_embed("mUTE", "cOULD nOT mUTE tHAT uSER!"))

@bot.tree.command(name="mute", description="Mute a member server-wide (admin only)")
@app_commands.describe(member="Member to mute")
async def mute_slash(interaction: discord.Interaction, member: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("mUTE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message(embed=nova_embed("mUTE", "nICE tRY, bUT yOU cAN'T mUTE yOURSELF!"), ephemeral=True)
        return
    role = await get_or_create_muted_role(interaction.guild)
    if not role:
        await interaction.response.send_message(embed=nova_embed("mUTE", "cOULD nOT cREATE oR fIND tHE mUTED rOLE!"), ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message(embed=nova_embed("mUTE", f"{member.mention} iS aLREADY mUTED!"), ephemeral=True)
        return
    try:
        await member.add_roles(role, reason="Muted by Nova")
        await interaction.response.send_message(embed=nova_embed("mUTE", f"{member.mention} hAS bEEN mUTED sERVER-WIDE!"))
        await interaction.followup.send("Usage: /mute @user - Mutes a member server-wide. Only mods/admins can use this.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(embed=nova_embed("mUTE", "cOULD nOT mUTE tHAT uSER!"), ephemeral=True)

@bot.command()
async def unmute(ctx, member: discord.Member = None):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNMUTE", "yOU dON'T hAVE pERMISSION!"))
        return
    if not member:
        await ctx.send(embed=nova_embed("uNMUTE", "yOU nEED tO mENTION sOMEONE!"))
        return
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role or role not in member.roles:
        await ctx.send(embed=nova_embed("uNMUTE", f"{member.mention} iS nOT mUTED!"))
        return
    try:
        await member.remove_roles(role, reason="Unmuted by Nova")
        await ctx.send(embed=nova_embed("uNMUTE", f"{member.mention} hAS bEEN uNMUTED!"))
        await ctx.send("Usage: ?unmute @user - Unmutes a member server-wide. Only mods/admins can use this.")
    except Exception:
        await ctx.send(embed=nova_embed("uNMUTE", "cOULD nOT uNMUTE tHAT uSER!"))

@bot.tree.command(name="unmute", description="Unmute a member server-wide (admin only)")
@app_commands.describe(member="Member to unmute")
async def unmute_slash(interaction: discord.Interaction, member: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("uNMUTE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not role or role not in member.roles:
        await interaction.response.send_message(embed=nova_embed("uNMUTE", f"{member.mention} iS nOT mUTED!"), ephemeral=True)
        return
    try:
        await member.remove_roles(role, reason="Unmuted by Nova")
        await interaction.response.send_message(embed=nova_embed("uNMUTE", f"{member.mention} hAS bEEN uNMUTED!"))
        await interaction.followup.send("Usage: /unmute @user - Unmutes a member server-wide. Only mods/admins can use this.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(embed=nova_embed("uNMUTE", "cOULD nOT uNMUTE tHAT uSER!"), ephemeral=True)

@bot.command()
async def case(ctx, member: discord.Member = None):
    """Show a member's past infractions"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("cASE", "Only mods/admins can view cases!"))
        return
    
    if member is None:
        await ctx.send(embed=nova_embed("cASE", "pLEASE sPECIFY a mEMBER!"))
        return
    
    user_id = str(member.id)
    
    if user_id not in INFRACTIONS or not INFRACTIONS[user_id]:
        embed = nova_embed(
            f"📋 cASE fILE: {member.display_name}",
            "nO iNFRACTIONS oN rECORD! 🎉"
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        await ctx.send(embed=embed)
        return
    
    infractions = INFRACTIONS[user_id]
    infraction_list = []
    
    for i, infraction in enumerate(infractions[-10:], 1):  # Show last 10
        date_str = infraction["date"].strftime("%Y-%m-%d")
        infraction_list.append(
            f"**{i}.** {infraction['type'].upper()} - {date_str}\n"
            f"   rEASON: {infraction['reason']}\n"
            f"   mOD: {infraction['moderator']}"
        )
    
    embed = nova_embed(
        f"📋 cASE fILE: {member.display_name}",
        f"tOTAL iNFRACTIONS: {len(infractions)}\n\n" + "\n\n".join(infraction_list)
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    
    if len(infractions) > 10:
        embed.set_footer(text=f"sHOWING lAST 10 oF {len(infractions)} iNFRACTIONS")
    
    await ctx.send(embed=embed)

@bot.tree.command(name="case", description="Show all moderation actions in this server (up to 20)")
async def case_slash(interaction: discord.Interaction):
    cases = mod_cases.get(interaction.guild.id, [])
    if not cases:
        await interaction.response.send_message(embed=nova_embed("cASES", "nO mODERATION cASES fOUND!"), ephemeral=True)
        return
    desc = ""
    for i, c in enumerate(cases, 1):
        desc += f"**{i}.** `{c['action']}` by {c['user']} in {c['channel']} • {c['time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    await interaction.response.send_message(embed=nova_embed("cASES", desc))
    await interaction.response.send_message("Usage: /case - Shows the last 20 moderation actions. Only mods/admins can use this.", ephemeral=True)

@bot.command()
async def snipe(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sNIPE", "yOU dON'T hAVE pERMISSION!"))
        return
    data = snipes.get(ctx.channel.id)
    if not data:
        await ctx.send(embed=nova_embed("sNIPE", "nOTHING tO sNIPE!"))
        return
    embed = nova_embed("sNIPE", data['content'])
    embed.set_footer(text=f"{data['author']} • {data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await ctx.send(embed=embed)

@bot.tree.command(name="snipe", description="Show the last deleted message in this channel")
async def snipe_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("sNIPE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    data = snipes.get(interaction.channel.id)
    if not data:
        await interaction.response.send_message(embed=nova_embed("sNIPE", "nOTHING tO sNIPE!"), ephemeral=True)
        return
    embed = nova_embed("sNIPE", data['content'])
    embed.set_footer(text=f"{data['author']} • {data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await interaction.response.send_message(embed=embed)

@bot.command()
async def edsnipe(ctx):
    data = edsnipes.get(ctx.channel.id)
    if not data:
        await ctx.send(embed=nova_embed("eDSNIPE", "nOTHING tO eDSNIPE!"))
        return
    embed = nova_embed("eDSNIPE", data['content'])
    embed.set_footer(text=f"{data['author']} • {data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await ctx.send(embed=embed)

@bot.tree.command(name="edsnipe", description="Show the last edited (before) message in this channel")
async def edsnipe_slash(interaction: discord.Interaction):
    data = edsnipes.get(interaction.channel.id)
    if not data:
        await interaction.response.send_message(embed=nova_embed("eDSNIPE", "nOTHING tO eDSNIPE!"), ephemeral=True)
        return
    embed = nova_embed("eDSNIPE", data['content'])
    embed.set_footer(text=f"{data['author']} • {data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await interaction.response.send_message(embed=embed)

@bot.command()
async def slowmode(ctx, seconds: int = 0):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sLOWMODE", "yOU dON'T hAVE pERMISSION!"))
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(embed=nova_embed("sLOWMODE", f"sLOWMODE sET tO {seconds} sECONDS iN {ctx.channel.mention}!"))
    await ctx.send("Usage: ?slowmode [seconds] - Sets slowmode in the current channel. Only mods/admins can use this.")

@bot.tree.command(name="slowmode", description="Set slowmode in the current channel (admin only)")
@app_commands.describe(seconds="Number of seconds for slowmode")
async def slowmode_slash(interaction: discord.Interaction, seconds: int = 0):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("sLOWMODE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=nova_embed("sLOWMODE", f"sLOWMODE sET tO {seconds} sECONDS iN {interaction.channel.mention}!"), ephemeral=True)
    await interaction.followup.send("Usage: /slowmode [seconds] - Sets slowmode in the current channel. Only mods/admins can use this.", ephemeral=True)

# Economy
@bot.command()
async def pay(ctx, user: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send(embed=nova_embed("pAY", "aMOUNT mUST bE pOSITIVE!"))
        return
    if get_balance(ctx.author.id) < amount:
        await ctx.send(embed=nova_embed("pAY", "nOT eNOUGH dOLLARIANAS!"))
        return
    change_balance(ctx.author.id, -amount)
    change_balance(user.id, amount)
    await ctx.send(embed=nova_embed("pAY", f"{ctx.author.display_name} sENT {amount} {CURRENCY_NAME} tO {user.display_name}!"))

@bot.tree.command(name="pay", description="Send currency to another user")
@app_commands.describe(user="The user to pay", amount="Amount to send")
async def pay_slash(interaction: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message(embed=nova_embed("pAY", "aMOUNT mUST bE pOSITIVE!"), ephemeral=True)
        return
    if get_balance(interaction.user.id) < amount:
        await interaction.response.send_message(embed=nova_embed("pAY", "nOT eNOUGH dOLLARIANAS!"), ephemeral=True)
        return
    change_balance(interaction.user.id, -amount)
    change_balance(user.id, amount)
    await interaction.response.send_message(embed=nova_embed("pAY", f"{interaction.user.display_name} sENT {amount} {CURRENCY_NAME} tO {user.display_name}!"))

@bot.command()
async def shop(ctx):
    lines = [f"• {item} — {price} {CURRENCY_NAME}" for item, price in SHOP_ITEMS.items()]
    await ctx.send(embed=nova_embed("🛍️ nOVA'S sHOP", "\n".join(lines)))

@bot.tree.command(name="shop", description="Show items available to buy")
async def shop_slash(interaction: discord.Interaction):
    lines = [f"• {item} — {price} {CURRENCY_NAME}" for item, price in SHOP_ITEMS.items()]
    await interaction.response.send_message(embed=nova_embed("🛍️ nOVA'S sHOP", "\n".join(lines)))

@bot.command()
async def buy(ctx, *, item: str):
    item = item.strip().lower()
    matched = next((k for k in SHOP_ITEMS if k.lower() == item), None)
    if not matched:
        await ctx.send(embed=nova_embed("bUY", "iTEM nOT fOUND iN tHE sHOP!"))
        return
    price = SHOP_ITEMS[matched]
    if get_balance(ctx.author.id) < price:
        await ctx.send(embed=nova_embed("bUY", "nOT eNOUGH dOLLARIANAS!"))
        return
    change_balance(ctx.author.id, -price)
    inventory = load_inventory()
    user_inv = inventory.get(str(ctx.author.id), [])
    user_inv.append(matched)
    inventory[str(ctx.author.id)] = user_inv
    save_inventory(inventory)
    await ctx.send(embed=nova_embed("bUY", f"yOU bOUGHT: {matched} fOR {price} {CURRENCY_NAME}!"))

@bot.tree.command(name="buy", description="Purchase an item from the shop")
@app_commands.describe(item="The item to buy")
async def buy_slash(interaction: discord.Interaction, item: str):
    item = item.strip().lower()
    matched = next((k for k in SHOP_ITEMS if k.lower() == item), None)
    if not matched:
        await interaction.response.send_message(embed=nova_embed("bUY", "iTEM nOT fOUND iN tHE sHOP!"), ephemeral=True)
        return
    price = SHOP_ITEMS[matched]
    if get_balance(interaction.user.id) < price:
        await interaction.response.send_message(embed=nova_embed("bUY", "nOT eNOUGH dOLLARIANAS!"), ephemeral=True)
        return
    change_balance(interaction.user.id, -price)
    inventory = load_inventory()
    user_inv = inventory.get(str(interaction.user.id), [])
    user_inv.append(matched)
    inventory[str(interaction.user.id)] = user_inv
    save_inventory(inventory)
    await interaction.response.send_message(embed=nova_embed("bUY", f"yOU bOUGHT: {matched} fOR {price} {CURRENCY_NAME}!"))

@bot.command()
async def inventory(ctx):
    inventory = load_inventory()
    user_inv = inventory.get(str(ctx.author.id), [])
    if not user_inv:
        await ctx.send(embed=nova_embed("iNVENTORY", "yOU dON'T oWN aNY iTEMS!"))
        return
    lines = [f"• {item}" for item in user_inv]
    await ctx.send(embed=nova_embed("iNVENTORY", "\n".join(lines)))

@bot.tree.command(name="inventory", description="Show items you own")
async def inventory_slash(interaction: discord.Interaction):
    inventory = load_inventory()
    user_inv = inventory.get(str(interaction.user.id), [])
    if not user_inv:
        await interaction.response.send_message(embed=nova_embed("iNVENTORY", "yOU dON'T oWN aNY iTEMS!"), ephemeral=True)
        return
    lines = [f"• {item}" for item in user_inv]
    await interaction.response.send_message(embed=nova_embed("iNVENTORY", "\n".join(lines)))

# Welcome/Rules
@bot.command()
async def welcome(ctx):
    embed = discord.Embed(
        title="👋 wELCOME tO tHE sERVER!",
        description="i'M nOVA, yOUR fABULOUS bOT. mAKE yOURSELF aT hOME!",
        color=0xff69b4
    )
    embed.set_footer(text="nOVA wELCOMES yOU 💖")
    await ctx.send(embed=embed)

@bot.command()
async def rules(ctx):
    embed = discord.Embed(
        title="📜 sERVER rULES",
        description="1. bE rESPECTFUL\n2. nO sPAM\n3. sTAY oN tOPIC\n4. nO nSFW\n5. lISTEN tO mODS\n6. hAVE fUN!",
        color=0xff69b4
    )
    embed.set_footer(text="nOVA sAYS: fOLLOW tHE rULES oR eLSE 💅")
    await ctx.send(embed=embed)

# Fun
@bot.command()
async def votekick(ctx, user: discord.Member):
    embed = nova_embed("vOTEKICK", f"sHOULD wE kICK {user.mention}?\n✅ = yES, ❌ = nO\n(vOTE eNDS iN 15 sECONDS)")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await asyncio.sleep(15)
    msg = await ctx.channel.fetch_message(msg.id)
    yes = 0
    no = 0
    for reaction in msg.reactions:
        if str(reaction.emoji) == "✅":
            yes = reaction.count - 1  # exclude bot
        elif str(reaction.emoji) == "❌":
            no = reaction.count - 1
    if yes > no:
        result = f"{user.mention} wAS (nOT rEALLY) kICKED! "
    else:
        result = f"{user.mention} sTAYS... fOR nOW! "
    await ctx.send(embed=nova_embed("vOTEKICK rESULT", result))

@bot.tree.command(name="votekick", description="Start a fake vote to kick someone (fun only)")
@app_commands.describe(user="The user to (fake) kick")
async def votekick_slash(interaction: discord.Interaction, user: discord.Member):
    embed = nova_embed("vOTEKICK", f"sHOULD wE kICK {user.mention}?\n✅ = yES, ❌ = nO\n(vOTE eNDS iN 15 sECONDS)")
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message(embed=nova_embed("vOTEKICK", f"vOTE sTARTED fOR {user.mention}!"), ephemeral=True)
    await asyncio.sleep(15)
    msg = await interaction.channel.fetch_message(msg.id)
    yes = 0
    no = 0
    for reaction in msg.reactions:
        if str(reaction.emoji) == "✅":
            yes = reaction.count - 1
        elif str(reaction.emoji) == "❌":
            no = reaction.count - 1
    if yes > no:
        result = f"{user.mention} wAS (nOT rEALLY) kICKED! "
    else:
        result = f"{user.mention} sTAYS... fOR nOW! "
    await interaction.channel.send(embed=nova_embed("vOTEKICK rESULT", result))

@bot.command()
async def explode(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the owner can use this command.")
        return
    await ctx.send("💥 Nova is self-destructing... (feature coming soon!)")

# Utility/External
@bot.command()
async def google(ctx, *, query: str):
    await ctx.send("Google search feature coming soon!")

@bot.command()
async def image(ctx, *, query: str):
    await ctx.send("Image search feature coming soon!")

@bot.command()
async def calc(ctx, *, equation: str):
    await ctx.send("Calculator feature coming soon!")

# Timezone/Birthday
@bot.command()
async def timezone(ctx, *, location: str = None):
    await ctx.send("Timezone feature coming soon!")

@bot.command()
async def tz(ctx, *, location: str = None):
    await ctx.send("Timezone shortcut feature coming soon!")

@bot.command()
async def settz(ctx, *, timezone: str):
    await ctx.send("Set timezone feature coming soon!")

@bot.command()
async def settimezone(ctx, *, timezone: str):
    await ctx.send("Set timezone (alias) feature coming soon!")

@bot.command()
async def birthday(ctx, user: discord.Member = None):
    """Show a user's birthday. Usage: ?birthday [@user]"""
    user = user or ctx.author
    birthdays = load_birthdays()
    bday = birthdays.get(str(user.id))
    if bday:
        formatted_bday = format_birthday(bday)
        await ctx.send(embed=nova_embed("🎂 bIRTHDAY", f"{user.display_name}'s birthday is {formatted_bday}!"))
    else:
        await ctx.send(embed=nova_embed("🎂 bIRTHDAY", f"No birthday set for {user.display_name}."))

# Alias for birthday command
@bot.command(name="bday")
async def bday(ctx, user: discord.Member = None):
    """Show a user's birthday. Usage: ?bday [@user] (alias for ?birthday)"""
    await birthday(ctx, user)



@bot.command()
async def setbday(ctx, date: str = None):
    """Set your birthday. Usage: ?setbday DD-MM"""
    if date is None:
        await ctx.send(embed=nova_embed("🎂 sET bIRTHDAY", "Usage: ?setbday DD-MM\n\nExample: ?setbday 15-04 for April 15th\n\nThis will display as: April 15th"))
        return
    
    # Basic validation
    try:
        day, month = map(int, date.split("-"))
        assert 1 <= month <= 12
        assert 1 <= day <= 31
    except Exception:
        await ctx.send(embed=nova_embed("🎂 sET bIRTHDAY", "Please use the format DD-MM, e.g. 15-04 for April 15th."))
        return
    birthdays = load_birthdays()
    birthdays[str(ctx.author.id)] = date
    save_birthdays(birthdays)
    formatted_date = format_birthday(date)
    await ctx.send(embed=nova_embed("🎂 sET bIRTHDAY", f"Birthday set to {formatted_date}!"))

# Alias for setbday command
@bot.command(name="setbirthday")
async def setbirthday(ctx, date: str = None):
    """Set your birthday. Usage: ?setbirthday DD-MM (alias for ?setbday)"""
    if date is None:
        await ctx.send(embed=nova_embed("🎂 sET bIRTHDAY", "Usage: ?setbirthday DD-MM\n\nExample: ?setbirthday 15-04 for April 15th\n\nThis will display as: April 15th"))
        return
    await setbday(ctx, date)



@bot.command()
async def birthdays(ctx):
    """List all birthdays in the server."""
    birthdays = load_birthdays()
    if not birthdays:
        await ctx.send(embed=nova_embed("🎂 bIRTHDAYS", "No birthdays set yet!"))
        return
    lines = []
    for user_id, date in birthdays.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            formatted_date = format_birthday(date)
            lines.append(f"{member.display_name}: {formatted_date}")
    if lines:
        await ctx.send(embed=nova_embed("🎂 sERVER bIRTHDAYS", "\n".join(lines)))
    else:
        await ctx.send(embed=nova_embed("🎂 bIRTHDAYS", "No birthdays set for current server members."))

# Slash command for birthday
@bot.tree.command(name="birthday", description="Show a user's birthday")
@app_commands.describe(user="The user to check (optional)")
async def birthday_slash(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    birthdays = load_birthdays()
    bday = birthdays.get(str(user.id))
    if bday:
        formatted_bday = format_birthday(bday)
        await interaction.response.send_message(embed=nova_embed("🎂 bIRTHDAY", f"{user.display_name}'s birthday is {formatted_bday}!"))
    else:
        await interaction.response.send_message(embed=nova_embed("🎂 bIRTHDAY", f"No birthday set for {user.display_name}."))

# Slash command for setbirthday
@bot.tree.command(name="setbirthday", description="Set your birthday")
@app_commands.describe(date="Your birthday in DD-MM format (e.g. 15-04 for April 15th)")
async def setbirthday_slash(interaction: discord.Interaction, date: str):
    # Basic validation
    try:
        day, month = map(int, date.split("-"))
        assert 1 <= month <= 12
        assert 1 <= day <= 31
    except Exception:
        await interaction.response.send_message(embed=nova_embed("🎂 sET bIRTHDAY", "Please use the format DD-MM, e.g. 15-04 for April 15th."), ephemeral=True)
        return
    birthdays = load_birthdays()
    birthdays[str(interaction.user.id)] = date
    save_birthdays(birthdays)
    await interaction.response.send_message(embed=nova_embed("🎂 sET bIRTHDAY", f"Birthday set to {date}!"))

@bot.command()
async def today(ctx):
    """Shows today's international day, Nova style, in a vibrant embed."""
    now = datetime.now()
    key = now.strftime("%d-%m")
    day = INTERNATIONAL_DAYS.get(key)
    if day:
        embed = discord.Embed(
            title="🌍 tODAY iS...",
            description=f"**{day}!**",
            color=0xff69b4  # Hot pink for Nova!
        )
        embed.set_footer(text="nOVA bRINGS yOU tHE dAY!")
    else:
        embed = discord.Embed(
            title="nO iNTERNATIONAL dAY tODAY!",
            description="tRY aGAIN tOMORROW bABY ",
            color=0x7289da  # Discord blurple
        )
        embed.set_footer(text="nOVA sAYS: mAYBE nEXT tIME!")
    await ctx.send(embed=embed)

# Profile/About Me System


# Slash commands for profiles
@bot.tree.command(name="setaboutme", description="Set your about me description")
@app_commands.describe(description="Your about me description (max 500 characters)")
async def setaboutme_slash(interaction: discord.Interaction, description: str):
    if len(description) > 500:
        await interaction.response.send_message(embed=nova_embed("📝 sET aBOUT mE", "Description too long! Maximum 500 characters."), ephemeral=True)
        return
    
    profiles = load_profiles()
    
    # Get old about me for logging
    old_profile = profiles.get(str(interaction.user.id))
    old_about_me = old_profile.get("about_me", "None") if old_profile else "None"
    
    profiles[str(interaction.user.id)] = {
        "about_me": description,
        "set_date": datetime.now().isoformat()
    }
    save_profiles(profiles)
    
    # Log to server logs channel
    print(f"DEBUG: About me logging - SERVER_LOGS_CHANNEL_ID = {SERVER_LOGS_CHANNEL_ID}")
    if SERVER_LOGS_CHANNEL_ID:
        channel = interaction.guild.get_channel(SERVER_LOGS_CHANNEL_ID)
        if channel:
            print(f"DEBUG: Found server logs channel {channel.name}, sending about me update log")
            embed = discord.Embed(
                title="📝 About Me Updated",
                color=0xff69b4,
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=True)
            embed.add_field(name="Changes", value=f"**About Me:**\nBefore: {old_about_me}\nAfter: {description}", inline=False)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            try:
                await channel.send(embed=embed)
                print("DEBUG: About me update log sent successfully")
            except Exception as e:
                print(f"Failed to send about me update log: {e}")
        else:
            print(f"DEBUG: Could not find server logs channel with ID {SERVER_LOGS_CHANNEL_ID}")
    else:
        print("DEBUG: No server logs channel configured for about me logging")
    
    await interaction.response.send_message(embed=nova_embed("📝 aBOUT mE uPDATED", f"Your about me has been set to:\n\n*{description}*"))

@bot.tree.command(name="aboutme", description="View someone's about me description")
@app_commands.describe(user="The user to check (optional)")
async def aboutme_slash(interaction: discord.Interaction, user: discord.Member = None):
    target_user = user or interaction.user
    profiles = load_profiles()
    
    user_profile = profiles.get(str(target_user.id))
    if not user_profile or "about_me" not in user_profile:
        if target_user == interaction.user:
            await interaction.response.send_message(embed=nova_embed("📝 aBOUT mE", "You haven't set an about me yet! Use /setaboutme to set one."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=nova_embed("📝 aBOUT mE", f"{target_user.display_name} hasn't set an about me yet."), ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"📝 {target_user.display_name}'s About Me",
        description=user_profile["about_me"],
        color=0xff69b4
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"Set on {datetime.fromisoformat(user_profile['set_date']).strftime('%B %d, %Y')}")
    
    await interaction.response.send_message(embed=embed)

# Confessions/8ball/Therapy
@bot.command()
async def confess(ctx, *, message: str):
    if CONFESS_CHANNEL_ID is None:
        await ctx.send(embed=nova_embed("cONFESSION", "cONFESSION cHANNEL nOT sET! aSK aN aDMIN."))
        return
    try:
        channel = bot.get_channel(CONFESS_CHANNEL_ID)
        if not channel:
            await ctx.send(embed=nova_embed("cONFESSION", "cOULD nOT fIND tHE cONFESSION cHANNEL!"))
            return
        embed = nova_embed("aNONYMOUS cONFESSION", message)
        await channel.send(embed=embed)
        await ctx.author.send(embed=nova_embed("cONFESSION sENT", "yOUR cONFESSION wAS sENT aNONYMOUSLY!"))
        await ctx.send(embed=nova_embed("cONFESSION", "yOUR cONFESSION wAS sENT aNONYMOUSLY! cHECK yOUR dMS."))
    except Exception:
        await ctx.send(embed=nova_embed("cONFESSION", "cOULD nOT sEND cONFESSION!"))

@bot.tree.command(name="confess", description="Send an anonymous confession to a private channel")
@app_commands.describe(message="Your confession")
async def confess_slash(interaction: discord.Interaction, message: str):
    if CONFESS_CHANNEL_ID is None:
        await interaction.response.send_message(embed=nova_embed("cONFESSION", "cONFESSION cHANNEL nOT sET! aSK aN aDMIN."), ephemeral=True)
        return
    try:
        channel = bot.get_channel(CONFESS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(embed=nova_embed("cONFESSION", "cOULD nOT fIND tHE cONFESSION cHANNEL!"), ephemeral=True)
            return
        embed = nova_embed("aNONYMOUS cONFESSION", message)
        await channel.send(embed=embed)
        await interaction.user.send(embed=nova_embed("cONFESSION sENT", "yOUR cONFESSION wAS sENT aNONYMOUSLY!"))
        await interaction.response.send_message(embed=nova_embed("cONFESSION", "yOUR cONFESSION wAS sENT aNONYMOUSLY! cHECK yOUR dMS."), ephemeral=True)
    except Exception:
        await interaction.response.send_message(embed=nova_embed("cONFESSION", "cOULD nOT sEND cONFESSION!"), ephemeral=True)

@bot.command(name="8ball")
async def _8ball(ctx, *, question: str):
    responses = [
        "yES, dARLING!",
        "nO, sWEETIE!",
        "mAYBE... aSK aGAIN lATER!",
        "aBSOLUTELY!",
        "nOT iN a mILLION yEARS!",
        "oF cOURSE!",
        "i wOULDN'T cOUNT oN iT!",
        "tHE sTARS sAY yES!",
        "mY sOURCES sAY nO!",
        "aSK yOUR mOTHER!",
        "iT iS cERTAIN!",
        "oUTLOOK nOT sO gOOD!",
        "yOU aLREADY kNOW tHE aNSWER!",
        "dON'T bET oN iT!",
        "sLAY, bUT nO!"
    ]
    answer = random.choice(responses)
    embed = nova_embed("🎱 8bALL", f"qUESTION: {question}\n**aNSWER:** {answer}")
    await ctx.send(embed=embed)

@bot.tree.command(name="8ball", description="Ask Nova the magic 8ball!")
@app_commands.describe(question="Your question for the 8ball")
async def _8ball_slash(interaction: discord.Interaction, question: str):
    responses = [
        "yES, dARLING!",
        "nO, sWEETIE!",
        "mAYBE... aSK aGAIN lATER!",
        "aBSOLUTELY!",
        "nOT iN a mILLION yEARS!",
        "oF cOURSE!",
        "i wOULDN'T cOUNT oN iT!",
        "tHE sTARS sAY yES!",
        "mY sOURCES sAY nO!",
        "aSK yOUR mOTHER!",
        "iT iS cERTAIN!",
        "oUTLOOK nOT sO gOOD!",
        "yOU aLREADY kNOW tHE aNSWER!",
        "dON'T bET oN iT!",
        "sLAY, bUT nO!"
    ]
    answer = random.choice(responses)
    embed = nova_embed("🎱 8bALL", f"qUESTION: {question}\n**aNSWER:** {answer}")
    await interaction.response.send_message(embed=embed)

@bot.command()
async def mood(ctx):
    moods = [
        "fEELING fANTABULOUS ",
        "i'M iN a cUNT mOOD ",
        "dRAMATIC tODAY ",
        "cHAOTIC eNERGY ",
        "lOVING tHE vIBE ",
        "cHILE...",
        "bORED... ",
        "rEADY tO mOTHER 👑",
        "cAFFEINATED aND dANGEROUS ",
        "i'M yOUR bESTIE tODAY..."
    ]
    mood = random.choice(moods)
    await ctx.send(embed=nova_embed("nOVA'S mOOD", mood))

@bot.tree.command(name="mood", description="Show Nova's current mood!")
async def mood_slash(interaction: discord.Interaction):
    moods = [
        "fEELING fANTABULOUS ",
        "i'M iN a cUNT mOOD ",
        "dRAMATIC tODAY ",
        "cHAOTIC eNERGY ",
        "lOVING tHE vIBE ",
        "cHILE...",
        "bORED... ",
        "rEADY tO mOTHER 👑",
        "cAFFEINATED aND dANGEROUS ",
        "i'M yOUR bESTIE tODAY..."
    ]
    mood = random.choice(moods)
    await interaction.response.send_message(embed=nova_embed("nOVA'S mOOD", mood))

@bot.command()
async def remindme(ctx, time: str, *, message: str):
    seconds = parse_time(time)
    if seconds is None or seconds <= 0:
        await ctx.send(embed=nova_embed("rEMINDER", "iNVALID tIME! uSE s, m, h, oR d (e.g. 10m, 2h)"))
        return
    reminders = load_reminders()
    user_reminders = reminders.get(str(ctx.author.id), {})
    reminder_id = str(len(user_reminders) + 1)
    user_reminders[reminder_id] = {"message": message, "time": int(asyncio.get_event_loop().time()) + seconds}
    reminders[str(ctx.author.id)] = user_reminders
    save_reminders(reminders)
    await ctx.send(embed=nova_embed("rEMINDER sET", f"i'LL rEMIND yOU iN {time}: {message}"))
    bot.loop.create_task(reminder_task(ctx.author.id, reminder_id, seconds, message))

@bot.tree.command(name="remindme", description="Set a reminder to ping you later")
@app_commands.describe(time="Time (e.g. 10m, 2h, 1d)", message="Reminder message")
async def remindme_slash(interaction: discord.Interaction, time: str, message: str):
    seconds = parse_time(time)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message(embed=nova_embed("rEMINDER", "iNVALID tIME! uSE s, m, h, oR d (e.g. 10m, 2h)"), ephemeral=True)
        return
    reminders = load_reminders()
    user_reminders = reminders.get(str(interaction.user.id), {})
    reminder_id = str(len(user_reminders) + 1)
    user_reminders[reminder_id] = {"message": message, "time": int(asyncio.get_event_loop().time()) + seconds}
    reminders[str(interaction.user.id)] = user_reminders
    save_reminders(reminders)
    await interaction.response.send_message(embed=nova_embed("rEMINDER sET", f"i'LL rEMIND yOU iN {time}: {message}"), ephemeral=True)
    bot.loop.create_task(reminder_task(interaction.user.id, reminder_id, seconds, message))

@bot.command()
async def reminderlist(ctx):
    reminders = load_reminders()
    user_reminders = reminders.get(str(ctx.author.id), {})
    if not user_reminders:
        await ctx.send(embed=nova_embed("rEMINDERS", "nO aCTIVE rEMINDERS!"))
        return
    lines = []
    now = int(asyncio.get_event_loop().time())
    for rid, data in user_reminders.items():
        left = max(0, data["time"] - now)
        mins, secs = divmod(left, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            tstr = f"{int(hours)}h {int(mins)}m"
        elif mins:
            tstr = f"{int(mins)}m {int(secs)}s"
        else:
            tstr = f"{int(secs)}s"
        lines.append(f"• {data['message']} (in {tstr})")
    await ctx.send(embed=nova_embed("yOUR rEMINDERS", "\n".join(lines)))

@bot.tree.command(name="reminderlist", description="List your active reminders")
async def reminderlist_slash(interaction: discord.Interaction):
    reminders = load_reminders()
    user_reminders = reminders.get(str(interaction.user.id), {})
    if not user_reminders:
        await interaction.response.send_message(embed=nova_embed("rEMINDERS", "nO aCTIVE rEMINDERS!"), ephemeral=True)
        return
    lines = []
    now = int(asyncio.get_event_loop().time())
    for rid, data in user_reminders.items():
        left = max(0, data["time"] - now)
        mins, secs = divmod(left, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            tstr = f"{int(hours)}h {int(mins)}m"
        elif mins:
            tstr = f"{int(mins)}m {int(secs)}s"
        else:
            tstr = f"{int(secs)}s"
        lines.append(f"• {data['message']} (in {tstr})")
    await interaction.response.send_message(embed=nova_embed("yOUR rEMINDERS", "\n".join(lines)), ephemeral=True)

# Translate/Weather/Avatar/Fact
@bot.command()
async def translate(ctx, language: str, *, text: str):
    await ctx.send("Translate feature coming soon!")

@bot.command()
async def weather(ctx, *, city: str):
    await ctx.send("Weather feature coming soon!")

@bot.command()
async def avatar(ctx, user: discord.Member = None):
    user = user or ctx.author
    embed = nova_embed(
        title=f"{user.display_name}'s aVATAR",
        description=f"hERE'S tHE aVATAR fOR {user.mention}",
        color=0xff69b4
    )
    embed.set_image(url=user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.tree.command(name="avatar", description="Show the avatar of a user")
async def avatar_slash(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    embed = nova_embed(
        title=f"{user.display_name}'s aVATAR",
        description=f"hERE'S tHE aVATAR fOR {user.mention}",
        color=0xff69b4
    )
    embed.set_image(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.command()
async def fact(ctx):
    await ctx.send("Fact feature coming soon!")

# Lyrics/Nick/Jail/Autoplay
@bot.command()
async def lyrics(ctx, *, query: str):
    await ctx.send("Lyrics feature coming soon!")

@bot.command()
async def nick(ctx, user: discord.Member, *, nickname: str):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    await ctx.send("Nick feature coming soon!")

JAIL_CHANNEL_ID = None  # Set this to your jail channel ID (int)

@bot.command()
async def setjail(ctx, channel: discord.TextChannel):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET jAIL", "yOU dON'T hAVE pERMISSION!"))
        return
    global JAIL_CHANNEL_ID
    JAIL_CHANNEL_ID = channel.id
    await ctx.send(embed=nova_embed("sET jAIL", f"jAIL cHANNEL sET tO {channel.mention}"))

@bot.tree.command(name="setjail", description="Set the jail channel (admin/mod only)")
@app_commands.describe(channel="The channel to use as jail")
async def setjail_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("sET jAIL", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    global JAIL_CHANNEL_ID
    JAIL_CHANNEL_ID = channel.id
    await interaction.response.send_message(embed=nova_embed("sET jAIL", f"jAIL cHANNEL sET tO {channel.mention}"), ephemeral=True)

@bot.command()
async def setrunway(ctx, channel: discord.TextChannel):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET rUNWAY", "yOU dON'T hAVE pERMISSION!"))
        return
    global RUNWAY_CHANNEL_ID
    RUNWAY_CHANNEL_ID = channel.id
    save_config()
    await ctx.send(embed=nova_embed("sET rUNWAY", f"rUNWAY cHANNEL sET tO {channel.mention}!"))

@bot.tree.command(name="setrunway", description="Set the runway channel (admin/mod only)")
@app_commands.describe(channel="The channel to use as runway")
async def setrunway_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("sET rUNWAY", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    global RUNWAY_CHANNEL_ID
    RUNWAY_CHANNEL_ID = channel.id
    save_config()
    await interaction.response.send_message(embed=nova_embed("sET rUNWAY", f"rUNWAY cHANNEL sET tO {channel.mention}!"), ephemeral=True)

@bot.command()
async def fixinmate(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("fIX iNMATE", "yOU dON'T hAVE pERMISSION!"))
        return
    try:
        inmate_role = discord.utils.get(ctx.guild.roles, name="iNMATE")
        if not inmate_role:
            await ctx.send(embed=nova_embed("fIX iNMATE", "iNMATE rOLE dOES nOT eXIST!"))
            return
        
        # Force update permissions for all channels
        updated_channels = 0
        for channel in ctx.guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    await channel.set_permissions(inmate_role, 
                        send_messages=False, 
                        speak=False, 
                        add_reactions=False,
                        create_public_threads=False,
                        create_private_threads=False,
                        send_messages_in_threads=False,
                        view_channel=True,
                        read_message_history=True
                    )
                    updated_channels += 1
                except discord.Forbidden:
                    continue
        
        await ctx.send(embed=nova_embed("fIX iNMATE", f"uPDATED pERMISSIONS fOR {updated_channels} cHANNELS!"))
    except Exception as e:
        await ctx.send(embed=nova_embed("fIX iNMATE", f"eRROR: {str(e)}"))

@bot.tree.command(name="fixinmate", description="Fix inmate role permissions for all channels (admin/mod only)")
async def fixinmate_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("fIX iNMATE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    try:
        inmate_role = discord.utils.get(interaction.guild.roles, name="iNMATE")
        if not inmate_role:
            await interaction.response.send_message(embed=nova_embed("fIX iNMATE", "iNMATE rOLE dOES nOT eXIST!"), ephemeral=True)
            return
        
        # Force update permissions for all channels
        updated_channels = 0
        for channel in interaction.guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    await channel.set_permissions(inmate_role, 
                        send_messages=False, 
                        speak=False, 
                        add_reactions=False,
                        create_public_threads=False,
                        create_private_threads=False,
                        send_messages_in_threads=False,
                        view_channel=True,
                        read_message_history=True
                    )
                    updated_channels += 1
                except discord.Forbidden:
                    continue
        
        await interaction.response.send_message(embed=nova_embed("fIX iNMATE", f"uPDATED pERMISSIONS fOR {updated_channels} cHANNELS!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("fIX iNMATE", f"eRROR: {str(e)}"), ephemeral=True)

@bot.command()
async def jail(ctx, user: discord.Member):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("jAIL", "yOU dON'T hAVE pERMISSION!"))
        return
    jail_channel_id = get_server_config(ctx.guild.id, "jail_channel_id")
    if jail_channel_id is None:
        await ctx.send(embed=nova_embed("jAIL", "jAIL cHANNEL nOT sET! uSE `?setjail #channel` tO sET iT!"))
        return
    try:
        jail_channel = ctx.guild.get_channel(jail_channel_id)
        if not jail_channel:
            await ctx.send(embed=nova_embed("jAIL", "cOULD nOT fIND tHE jAIL cHANNEL!"))
            return
        
        # Create or get inmate role
        inmate_role = discord.utils.get(ctx.guild.roles, name="iNMATE")
        if not inmate_role:
            try:
                inmate_role = await ctx.guild.create_role(
                    name="iNMATE",
                    color=discord.Color.dark_red(),
                    reason="Jail system role"
                )
                # Set permissions for all channels
                for channel in ctx.guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                        try:
                            await channel.set_permissions(inmate_role, 
                                send_messages=False, 
                                speak=False, 
                                add_reactions=False,
                                create_public_threads=False,
                                create_private_threads=False,
                                send_messages_in_threads=False,
                                view_channel=True,
                                read_message_history=True
                            )
                        except discord.Forbidden:
                            continue  # Skip channels we can't modify
            except discord.Forbidden:
                await ctx.send(embed=nova_embed("jAIL", "cAN'T cREATE iNMATE rOLE - nO pERMISSION!"))
                return
        else:
            # If role exists, make sure permissions are set correctly
            for channel in ctx.guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    try:
                        await channel.set_permissions(inmate_role, 
                            send_messages=False, 
                            speak=False, 
                            add_reactions=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            send_messages_in_threads=False,
                            view_channel=True,
                            read_message_history=True
                        )
                    except discord.Forbidden:
                        continue  # Skip channels we can't modify
        
        # Add inmate role to user
        if inmate_role not in user.roles:
            await user.add_roles(inmate_role, reason="Jailed by Nova")
        
        # Try to move user to jail channel if they're in voice
        if user.voice:
            try:
                await user.move_to(jail_channel)
            except discord.Forbidden:
                pass  # Don't fail if we can't move them
            except Exception:
                pass  # Don't fail if we can't move them
        
        await ctx.send(embed=nova_embed("jAIL", f"{user.mention} hAS bEEN jAILED! tHEY cAN'T tALK aNYWHERE nOW!"))
    except discord.Forbidden:
        await ctx.send(embed=nova_embed("jAIL", "nO pERMISSION tO mANAGE rOLES oR cHANNELS!"))
    except Exception as e:
        await ctx.send(embed=nova_embed("jAIL", f"eRROR: {str(e)}"))

@bot.tree.command(name="jail", description="Move a user to the jail channel and restrict permissions (admin/mod only)")
@app_commands.describe(user="The user to jail")
async def jail_slash(interaction: discord.Interaction, user: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("jAIL", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    if JAIL_CHANNEL_ID is None:
        await interaction.response.send_message(embed=nova_embed("jAIL", "jAIL cHANNEL nOT sET!"), ephemeral=True)
        return
    try:
        jail_channel = interaction.guild.get_channel(JAIL_CHANNEL_ID)
        if not jail_channel:
            await interaction.response.send_message(embed=nova_embed("jAIL", "cOULD nOT fIND tHE jAIL cHANNEL!"), ephemeral=True)
            return
        
        # Create or get inmate role
        inmate_role = discord.utils.get(interaction.guild.roles, name="iNMATE")
        if not inmate_role:
            try:
                inmate_role = await interaction.guild.create_role(
                    name="iNMATE",
                    color=discord.Color.dark_red(),
                    reason="Jail system role"
                )
                # Set permissions for all channels
                for channel in interaction.guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                        try:
                            await channel.set_permissions(inmate_role, 
                                send_messages=False, 
                                speak=False, 
                                add_reactions=False,
                                create_public_threads=False,
                                create_private_threads=False,
                                send_messages_in_threads=False,
                                view_channel=True,
                                read_message_history=True
                            )
                        except discord.Forbidden:
                            continue  # Skip channels we can't modify
            except discord.Forbidden:
                await interaction.response.send_message(embed=nova_embed("jAIL", "cAN'T cREATE iNMATE rOLE - nO pERMISSION!"), ephemeral=True)
                return
        else:
            # If role exists, make sure permissions are set correctly
            for channel in interaction.guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    try:
                        await channel.set_permissions(inmate_role, 
                            send_messages=False, 
                            speak=False, 
                            add_reactions=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            send_messages_in_threads=False,
                            view_channel=True,
                            read_message_history=True
                        )
                    except discord.Forbidden:
                        continue  # Skip channels we can't modify
        
        # Add inmate role to user
        if inmate_role not in user.roles:
            await user.add_roles(inmate_role, reason="Jailed by Nova")
        
        # Try to move user to jail channel if they're in voice
        if user.voice:
            try:
                await user.move_to(jail_channel)
            except discord.Forbidden:
                pass  # Don't fail if we can't move them
            except Exception:
                pass  # Don't fail if we can't move them
        
        await interaction.response.send_message(embed=nova_embed("jAIL", f"{user.mention} hAS bEEN jAILED! tHEY cAN'T tALK aNYWHERE nOW!"))
    except discord.Forbidden:
        await interaction.response.send_message(embed=nova_embed("jAIL", "nO pERMISSION tO mANAGE rOLES oR cHANNELS!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("jAIL", f"eRROR: {str(e)}"), ephemeral=True)

@bot.command()
async def runway(ctx, message_id: int = None):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rUNWAY", "yOU dON'T hAVE pERMISSION!"))
        return
    if RUNWAY_CHANNEL_ID is None:
        await ctx.send(embed=nova_embed("rUNWAY", "rUNWAY cHANNEL nOT sET!"))
        return
    
    # Get the message to transfer
    if message_id:
        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.send(embed=nova_embed("rUNWAY", "mESSAGE nOT fOUND!"))
            return
        except discord.Forbidden:
            await ctx.send(embed=nova_embed("rUNWAY", "cAN'T aCCESS tHAT mESSAGE!"))
            return
    else:
        # Get the last message in the channel
        async for message in ctx.channel.history(limit=1):
            break
        else:
            await ctx.send(embed=nova_embed("rUNWAY", "nO mESSAGES tO tRANSFER!"))
            return
    
    try:
        runway_channel = ctx.guild.get_channel(RUNWAY_CHANNEL_ID)
        if not runway_channel:
            await ctx.send(embed=nova_embed("rUNWAY", "cOULD nOT fIND tHE rUNWAY cHANNEL!"))
            return
        
        # Create runway embed with crying emoji and message number
        embed = nova_embed("😢 #" + str(message.id), message.content)
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
        embed.add_field(name="oRIGINAL cHANNEL", value=ctx.channel.mention, inline=True)
        embed.set_footer(text=f"Message ID: {message.id}")
        
        # Send attachments separately if any
        files = []
        for attachment in message.attachments:
            try:
                file_data = await attachment.read()
                files.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
            except Exception:
                continue
        
        await runway_channel.send(embed=embed, files=files)
        await ctx.send(embed=nova_embed("rUNWAY", f"mESSAGE tRANSFERRED tO {runway_channel.mention}!"))
        
    except Exception as e:
        await ctx.send(embed=nova_embed("rUNWAY", f"eRROR: {str(e)}"))

@bot.tree.command(name="runway", description="Transfer a message to the runway channel (admin/mod only)")
@app_commands.describe(message_id="ID of the message to transfer (optional - uses last message)")
async def runway_slash(interaction: discord.Interaction, message_id: int = None):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("rUNWAY", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    if RUNWAY_CHANNEL_ID is None:
        await interaction.response.send_message(embed=nova_embed("rUNWAY", "rUNWAY cHANNEL nOT sET!"), ephemeral=True)
        return
    
    # Get the message to transfer
    if message_id:
        try:
            message = await interaction.channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message(embed=nova_embed("rUNWAY", "mESSAGE nOT fOUND!"), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(embed=nova_embed("rUNWAY", "cAN'T aCCESS tHAT mESSAGE!"), ephemeral=True)
            return
    else:
        # Get the last message in the channel
        async for message in interaction.channel.history(limit=1):
            break
        else:
            await interaction.response.send_message(embed=nova_embed("rUNWAY", "nO mESSAGES tO tRANSFER!"), ephemeral=True)
            return
    
    try:
        runway_channel = interaction.guild.get_channel(RUNWAY_CHANNEL_ID)
        if not runway_channel:
            await interaction.response.send_message(embed=nova_embed("rUNWAY", "cOULD nOT fIND tHE rUNWAY cHANNEL!"), ephemeral=True)
            return
        
        # Create runway embed with crying emoji and message number
        embed = nova_embed("😢 #" + str(message.id), message.content)
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
        embed.add_field(name="oRIGINAL cHANNEL", value=interaction.channel.mention, inline=True)
        embed.set_footer(text=f"Message ID: {message.id}")
        
        # Send attachments separately if any
        files = []
        for attachment in message.attachments:
            try:
                file_data = await attachment.read()
                files.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
            except Exception:
                continue
        
        await runway_channel.send(embed=embed, files=files)
        await interaction.response.send_message(embed=nova_embed("rUNWAY", f"mESSAGE tRANSFERRED tO {runway_channel.mention}!"), ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("rUNWAY", f"eRROR: {str(e)}"), ephemeral=True)

@bot.command()
async def setautoplay(ctx, channel: discord.VoiceChannel):
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    await ctx.send("Set autoplay channel feature coming soon!")

@bot.command()
async def playlistshow(ctx):
    await ctx.send("Playlist show feature coming soon!")

@bot.command()
async def chatgpt(ctx, *, prompt: str):
    """Talk to ChatGPT!"""
    await ctx.send("ChatGPT feature coming soon!")

@bot.command()
async def generate(ctx, *, prompt: str):
    """Generate creative content with ChatGPT."""
    await ctx.send("Generate feature coming soon!")

# Helper functions for relationships

def load_relationships():
    try:
        with open(RELATIONSHIPS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_relationships(relationships):
    with open(RELATIONSHIPS_FILE, "w") as f:
        json.dump(relationships, f)

def load_reminders():
    try:
        with open(REMINDERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f)

def parse_time(timestr):
    match = re.match(r"(\d+)([smhd])", timestr.lower())
    if not match:
        return None
    num, unit = int(match.group(1)), match.group(2)
    if unit == 's': return num
    if unit == 'm': return num * 60
    if unit == 'h': return num * 3600
    if unit == 'd': return num * 86400
    return None

async def reminder_task(user_id, reminder_id, seconds, message):
    await asyncio.sleep(seconds)
    user = await bot.fetch_user(int(user_id))
    embed = nova_embed("rEMINDER!", f"⏰ {message}")
    try:
        await user.send(embed=embed)
    except Exception:
        pass
    reminders = load_reminders()
    user_reminders = reminders.get(str(user_id), {})
    if reminder_id in user_reminders:
        del user_reminders[reminder_id]
        reminders[str(user_id)] = user_reminders
        save_reminders(reminders)

CONFESS_CHANNEL_ID = 1391874227774165132

@bot.command()
async def unjail(ctx, user: discord.Member):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNJAIL", "yOU dON'T hAVE pERMISSION!"))
        return
    try:
        # Remove inmate role
        inmate_role = discord.utils.get(ctx.guild.roles, name="iNMATE")
        if inmate_role and inmate_role in user.roles:
            await user.remove_roles(inmate_role, reason="Unjailed by Nova")
            await ctx.send(embed=nova_embed("uNJAIL", f"{user.mention} hAS bEEN uNJAILed!"))
        else:
            await ctx.send(embed=nova_embed("uNJAIL", f"{user.mention} iS nOT jAILED!"))
    except discord.Forbidden:
        await ctx.send(embed=nova_embed("uNJAIL", "nO pERMISSION tO mANAGE rOLES!"))
    except Exception as e:
        await ctx.send(embed=nova_embed("uNJAIL", f"eRROR: {str(e)}"))

@bot.tree.command(name="unjail", description="Remove a user from jail (admin/mod only)")
@app_commands.describe(user="The user to unjail")
async def unjail_slash(interaction: discord.Interaction, user: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("uNJAIL", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    try:
        # Remove inmate role
        inmate_role = discord.utils.get(interaction.guild.roles, name="iNMATE")
        if inmate_role and inmate_role in user.roles:
            await user.remove_roles(inmate_role, reason="Unjailed by Nova")
            await interaction.response.send_message(embed=nova_embed("uNJAIL", f"{user.mention} hAS bEEN uNJAILed!"))
        else:
            await interaction.response.send_message(embed=nova_embed("uNJAIL", f"{user.mention} iS nOT jAILED!"), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(embed=nova_embed("uNJAIL", "nO pERMISSION tO mANAGE rOLES!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("uNJAIL", f"eRROR: {str(e)}"), ephemeral=True)

SHOP_ITEMS = {
    "cUSTOM rOLE": 5000,
    "xP bOOST": 2000,
    "sHOUTOUT": 2000,
    "pROMOTE yOURSELF": 5000,
    "rING a uSER": 2000,
    "cUSTOMIZE nOVA'S bIO (24h)": 10000
}
INVENTORY_FILE = "inventory.json"

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_inventory(inventory):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(inventory, f)

def load_thrift():
    try:
        with open(THRIFT_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_thrift(thrift):
    with open(THRIFT_FILE, "w") as f:
        json.dump(thrift, f)

@bot.command()
async def sell(ctx, item: str, price: int):
    item = item.strip()
    if price <= 0:
        await ctx.send(embed=nova_embed("sELL", "pRICE mUST bE pOSITIVE!"))
        return
    inventory = load_inventory()
    user_inv = inventory.get(str(ctx.author.id), [])
    matched = next((i for i in user_inv if i.lower() == item.lower()), None)
    if not matched:
        await ctx.send(embed=nova_embed("sELL", "yOU dON'T oWN tHAT iTEM!"))
        return
    user_inv.remove(matched)
    inventory[str(ctx.author.id)] = user_inv
    save_inventory(inventory)
    thrift = load_thrift()
    thrift.append({"item": matched, "price": price, "seller": ctx.author.id})
    save_thrift(thrift)
    await ctx.send(embed=nova_embed("sELL", f"yOU lISTED {matched} fOR sALE aT {price} {CURRENCY_NAME} iN tHE tHRIFT sTORE!"))

@bot.tree.command(name="sell", description="Sell an item from your inventory at a custom price")
@app_commands.describe(item="The item to sell", price="Sale price")
async def sell_slash(interaction: discord.Interaction, item: str, price: int):
    item = item.strip()
    if price <= 0:
        await interaction.response.send_message(embed=nova_embed("sELL", "pRICE mUST bE pOSITIVE!"), ephemeral=True)
        return
    inventory = load_inventory()
    user_inv = inventory.get(str(interaction.user.id), [])
    matched = next((i for i in user_inv if i.lower() == item.lower()), None)
    if not matched:
        await interaction.response.send_message(embed=nova_embed("sELL", "yOU dON'T oWN tHAT iTEM!"), ephemeral=True)
        return
    user_inv.remove(matched)
    inventory[str(interaction.user.id)] = user_inv
    save_inventory(inventory)
    thrift = load_thrift()
    thrift.append({"item": matched, "price": price, "seller": interaction.user.id})
    save_thrift(thrift)
    await interaction.response.send_message(embed=nova_embed("sELL", f"yOU lISTED {matched} fOR sALE aT {price} {CURRENCY_NAME} iN tHE tHRIFT sTORE!"))

@bot.command()
async def thrift(ctx):
    thrift = load_thrift()
    if not thrift:
        await ctx.send(embed=nova_embed("tHRIFT sTORE", "nO iTEMS fOR sALE rIGHT nOW!"))
        return
    lines = []
    for idx, entry in enumerate(thrift, 1):
        seller = ctx.guild.get_member(entry["seller"])
        seller_name = seller.display_name if seller else f"<@{entry['seller']}>"
        lines.append(f"{idx}. {entry['item']} — {entry['price']} {CURRENCY_NAME} (by {seller_name})")
    await ctx.send(embed=nova_embed("tHRIFT sTORE", "\n".join(lines)))

@bot.tree.command(name="thrift", description="Show the thrift store (member sales)")
async def thrift_slash(interaction: discord.Interaction):
    thrift = load_thrift()
    if not thrift:
        await interaction.response.send_message(embed=nova_embed("tHRIFT sTORE", "nO iTEMS fOR sALE rIGHT nOW!"), ephemeral=True)
        return
    lines = []
    for idx, entry in enumerate(thrift, 1):
        seller = interaction.guild.get_member(entry["seller"])
        seller_name = seller.display_name if seller else f"<@{entry['seller']}>"
        lines.append(f"{idx}. {entry['item']} — {entry['price']} {CURRENCY_NAME} (by {seller_name})")
    await interaction.response.send_message(embed=nova_embed("tHRIFT sTORE", "\n".join(lines)))

@bot.command()
async def buythrift(ctx, idx: int):
    thrift = load_thrift()
    if idx < 1 or idx > len(thrift):
        await ctx.send(embed=nova_embed("bUY tHRIFT", "iNVALID iTEM nUMBER!"))
        return
    entry = thrift[idx-1]
    if get_balance(ctx.author.id) < entry["price"]:
        await ctx.send(embed=nova_embed("bUY tHRIFT", "nOT eNOUGH dOLLARIANAS!"))
        return
    if entry["seller"] == ctx.author.id:
        await ctx.send(embed=nova_embed("bUY tHRIFT", "yOU cAN'T bUY yOUR oWN iTEM!"))
        return
    change_balance(ctx.author.id, -entry["price"])
    change_balance(entry["seller"], entry["price"])
    inventory = load_inventory()
    user_inv = inventory.get(str(ctx.author.id), [])
    user_inv.append(entry["item"])
    inventory[str(ctx.author.id)] = user_inv
    save_inventory(inventory)
    del thrift[idx-1]
    save_thrift(thrift)
    await ctx.send(embed=nova_embed("bUY tHRIFT", f"yOU bOUGHT {entry['item']} fOR {entry['price']} {CURRENCY_NAME}!"))

@bot.tree.command(name="buythrift", description="Buy an item from the thrift store")
@app_commands.describe(idx="The item number from /thrift")
async def buythrift_slash(interaction: discord.Interaction, idx: int):
    thrift = load_thrift()
    if idx < 1 or idx > len(thrift):
        await interaction.response.send_message(embed=nova_embed("bUY tHRIFT", "iNVALID iTEM nUMBER!"), ephemeral=True)
        return
    entry = thrift[idx-1]
    if get_balance(interaction.user.id) < entry["price"]:
        await interaction.response.send_message(embed=nova_embed("bUY tHRIFT", "nOT eNOUGH dOLLARIANAS!"), ephemeral=True)
        return
    if entry["seller"] == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("bUY tHRIFT", "yOU cAN'T bUY yOUR oWN iTEM!"), ephemeral=True)
        return
    change_balance(interaction.user.id, -entry["price"])
    change_balance(entry["seller"], entry["price"])
    inventory = load_inventory()
    user_inv = inventory.get(str(interaction.user.id), [])
    user_inv.append(entry["item"])
    inventory[str(interaction.user.id)] = user_inv
    save_inventory(inventory)
    del thrift[idx-1]
    save_thrift(thrift)
    await interaction.response.send_message(embed=nova_embed("bUY tHRIFT", f"yOU bOUGHT {entry['item']} fOR {entry['price']} {CURRENCY_NAME}!"))

# Store last deleted and edited messages per channel
snipes = {}
edsnipes = {}
rsnipes = {}  # channel_id: {'emoji': str, 'user': str, 'message_id': int, 'jump_url': str, 'time': datetime}

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    
    # Store for snipe command
    snipes[message.channel.id] = {
        'content': message.content,
        'author': str(message.author),
        'time': message.created_at
    }
    
    # Central logging for deleted messages
    print(f"DEBUG: Message deleted by {message.author} in {message.channel}")
    
    if message.guild:
        # Create embed for both central and local logging
        content = message.content if message.content else "*[No text content]*"
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=0xff4444,
            timestamp=datetime.now(dt_timezone.utc)
        )
        embed.add_field(name="Author", value=f"{message.author.mention}\n`{message.author.id}`", inline=True)
        embed.add_field(name="Channel", value=f"{message.channel.mention}\n`{message.channel.id}`", inline=True)
        embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
        embed.add_field(name="Content", value=content[:1024], inline=False)
        
        if message.author.avatar:
            embed.set_thumbnail(url=message.author.avatar.url)
        
        # Log to central messages channel
        central_logged = await log_to_central_channel(message.guild.id, "messages", embed)
        
        if central_logged:
            print(f"DEBUG: Message deletion logged to central messages channel")
        else:
            print(f"DEBUG: Central logging failed for message deletion")
        
        # Also log to local channel if configured (simultaneous, not fallback)
        if CHAT_LOGS_CHANNEL_ID:
            log_channel = message.guild.get_channel(CHAT_LOGS_CHANNEL_ID)
            if log_channel:
                try:
                    await log_channel.send(embed=embed)
                    print(f"DEBUG: Message deletion also logged to local channel {log_channel.name}")
                except Exception as e:
                    print(f"ERROR: Failed to send to local chat log: {e}")
            else:
                print(f"ERROR: Local chat logs channel not found with ID: {CHAT_LOGS_CHANNEL_ID}")
        else:
            print("DEBUG: No local chat logs channel configured")
    else:
        print("DEBUG: Message deletion in DM, skipping logging")

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    
    # Chat logs for message edits - Enhanced debugging
    print(f"DEBUG: Message edited by {before.author} in {before.channel}")
    guild = before.guild
    if guild:
        chat_logs_channel_id = get_server_config(guild.id, "chat_logs_channel_id")
        print(f"DEBUG: Server {guild.id} chat logs channel ID: {chat_logs_channel_id}")
        
        if chat_logs_channel_id:
            log_channel = guild.get_channel(chat_logs_channel_id)
            print(f"DEBUG: Log channel = {log_channel}")
            if log_channel:
                try:
                    before_content = before.content if before.content else "*[No text content]*"
                    after_content = after.content if after.content else "*[No text content]*"
                    
                    embed = nova_embed(
                        "✏️ mESSAGE eDITED", 
                        f"**Author:** {before.author}\n**Channel:** {before.channel.mention}\n**Message ID:** {before.id}"
                    )
                    embed.add_field(name="Before", value=f"```{before_content[:1000]}```", inline=False)
                    embed.add_field(name="After", value=f"```{after_content[:1000]}```", inline=False)
                    embed.add_field(name="Jump to Message", value=f"[Click here]({after.jump_url})", inline=False)
                    embed.timestamp = datetime.now(dt_timezone.utc)
                    embed.color = 0xffcc00  # Yellow for edits
                    
                    await log_channel.send(embed=embed)
                    print(f"DEBUG: Edit log sent successfully to {log_channel.name}")
                except Exception as e:
                    print(f"ERROR: Failed to send edit log: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"ERROR: Chat logs channel not found with ID: {CHAT_LOGS_CHANNEL_ID}")
        else:
            print("ERROR: Guild not found for message edit")
    else:
        print("DEBUG: CHAT_LOGS_CHANNEL_ID is None - chat logs disabled")
    
    # Store for edsnipe command
    edsnipes[before.channel.id] = {
        'content': before.content,
        'author': str(before.author),
        'time': before.edited_at or before.created_at
    }

@bot.event
async def on_raw_reaction_remove(payload):
    # Store the last removed reaction for rsnipe
    if payload.guild_id is None:
        return
    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        return
    user = None
    guild = bot.get_guild(payload.guild_id)
    if guild:
        user = guild.get_member(payload.user_id)
    if user is None or user.bot:
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        message = None
    jump_url = message.jump_url if message else None
    rsnipes[payload.channel_id] = {
        'emoji': str(payload.emoji),
        'user': str(user),
        'message_id': payload.message_id,
        'jump_url': jump_url,
        'time': datetime.now(dt_timezone.utc)
    }

@bot.command()
async def rsnipe(ctx):
    print(f"DEBUG: RSnipe command called by {ctx.author} in {ctx.channel}")
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rSNIPE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    print(f"DEBUG: Checking rsnipes for channel {ctx.channel.id}")
    print(f"DEBUG: Available rsnipes: {list(rsnipes.keys())}")
    data = rsnipes.get(ctx.channel.id)
    print(f"DEBUG: RSnipe data found: {data}")
    
    if not data:
        await ctx.send(embed=nova_embed("rSNIPE", "nOTHING tO rSNIPE!"))
        return
    
    desc = f"{data['user']} rEMOVED rEACTION {data['emoji']}"
    if data['jump_url']:
        desc += f"\n[Jump to message]({data['jump_url']})"
    embed = nova_embed("rSNIPE", desc)
    embed.set_footer(text=f"{data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await ctx.send(embed=embed)
    print(f"DEBUG: RSnipe embed sent successfully")

@bot.tree.command(name="rsnipe", description="Show the last removed reaction in this channel")
async def rsnipe_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("rSNIPE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    data = rsnipes.get(interaction.channel.id)
    if not data:
        await interaction.response.send_message(embed=nova_embed("rSNIPE", "nOTHING tO rSNIPE!"), ephemeral=True)
        return
    desc = f"{data['user']} rEMOVED rEACTION {data['emoji']}"
    if data['jump_url']:
        desc += f"\n[Jump to message]({data['jump_url']})"
    embed = nova_embed("rSNIPE", desc)
    embed.set_footer(text=f"{data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Store moderation cases per guild
mod_cases = {}

def log_case(guild_id, action, user, channel, time):
    if guild_id not in mod_cases:
        mod_cases[guild_id] = []
    
    # Ensure time is properly formatted as ISO string
    if hasattr(time, 'isoformat'):
        time_str = time.isoformat()
    else:
        time_str = str(time)
    
    mod_cases[guild_id].insert(0, {
        'action': action,
        'user': str(user),
        'channel': str(channel),
        'time': time_str
    })
    if len(mod_cases[guild_id]) > 20:
        mod_cases[guild_id] = mod_cases[guild_id][:20]

@bot.command()
async def dmtest(ctx):
    if ctx.guild is None:
        # In a DM
        await ctx.send(embed=nova_embed("dM tEST", "yOU'RE iN mY dMS, bABY! 💌"))
    else:
        # In a server
        await ctx.send(embed=nova_embed("dM tEST", "yOU'RE iN a sERVER, hONEY! 💅"))

@bot.command()
async def endimposter(ctx):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("eND iMPOSTER", "yOU dON'T hAVE pERMISSION!"))
        return
    game = IMPOSTER_GAMES.get(ctx.channel.id)
    if not game or not game.active:
        await ctx.send(embed=nova_embed("eND iMPOSTER", "nO aCTIVE iMPOSTER gAME tO eND!"))
        return
    game.end()
    del IMPOSTER_GAMES[ctx.channel.id]
    await ctx.send(embed=nova_embed("eND iMPOSTER", "tHE iMPOSTER gAME hAS bEEN eNDED bY a mOD!"))

@bot.command()
async def setchatlogs(ctx, channel: discord.TextChannel = None):
    """Set the chat logs channel for mod-only logs."""
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    
    guild_id = ctx.guild.id
    
    if channel is None:
        # Remove chat logs channel for this server
        set_server_config(guild_id, "chat_logs_channel_id", None)
        await ctx.send(embed=nova_embed("cHAT lOGS", "cHAT lOGS cHANNEL uNSET fOR tHIS sERVER."))
        return
    
    # Set chat logs channel for this server
    set_server_config(guild_id, "chat_logs_channel_id", channel.id)
    await ctx.send(embed=nova_embed("cHAT lOGS", f"cHAT lOGS cHANNEL sET tO {channel.mention} fOR tHIS sERVER."))

@bot.tree.command(name="setchatlogs", description="Set the chat logs channel for mod-only logs.")
@app_commands.describe(channel="The channel to log deleted/edited messages")
async def setchatlogs_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    
    # Set chat logs channel for this server
    set_server_config(guild_id, "chat_logs_channel_id", channel.id)
    await interaction.response.send_message(embed=nova_embed("cHAT lOGS", f"cHAT lOGS cHANNEL sET tO {channel.mention} fOR tHIS sERVER."), ephemeral=True)

# Welcome/Farewell system
WELCOME_CHANNEL_ID = None  # Set by ?setwelcome
FAREWELL_CHANNEL_ID = None  # Set by ?setfarewell

@bot.command()
async def setwelcome(ctx, channel: discord.TextChannel = None):
    """Set the welcome channel."""
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    global WELCOME_CHANNEL_ID
    if channel is None:
        WELCOME_CHANNEL_ID = None
        save_config()
        await ctx.send("Welcome channel unset.")
        return
    WELCOME_CHANNEL_ID = channel.id
    save_config()
    await ctx.send(f"Welcome channel set to {channel.mention}.")

@bot.tree.command(name="setwelcome", description="Set the welcome channel.")
@app_commands.describe(channel="The channel to send welcome messages")
async def setwelcome_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    global WELCOME_CHANNEL_ID
    WELCOME_CHANNEL_ID = channel.id
    save_config()
    await interaction.response.send_message(f"Welcome channel set to {channel.mention}.", ephemeral=True)

@bot.command()
async def setruleschannel(ctx, channel: discord.TextChannel = None):
    """Set the rules channel for welcome messages."""
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    global RULES_CHANNEL_ID
    if channel is None:
        RULES_CHANNEL_ID = None
        save_config()
        await ctx.send("Rules channel unset.")
        return
    RULES_CHANNEL_ID = channel.id
    save_config()
    await ctx.send(f"Rules channel set to {channel.mention}.")

@bot.tree.command(name="setruleschannel", description="Set the rules channel for welcome messages.")
@app_commands.describe(channel="The rules channel to reference in welcome messages")
async def setruleschannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    global RULES_CHANNEL_ID
    RULES_CHANNEL_ID = channel.id
    save_config()
    await interaction.response.send_message(f"Rules channel set to {channel.mention}.", ephemeral=True)

@bot.command()
async def setfarewell(ctx, channel: discord.TextChannel = None):
    """Set the farewell channel."""
    if not has_mod_or_admin(ctx):
        await ctx.send("You don't have permission to use this command.")
        return
    global FAREWELL_CHANNEL_ID
    if channel is None:
        FAREWELL_CHANNEL_ID = None
        save_config()
        await ctx.send("Farewell channel unset.")
        return
    FAREWELL_CHANNEL_ID = channel.id
    save_config()
    await ctx.send(f"Farewell channel set to {channel.mention}.")

@bot.tree.command(name="setfarewell", description="Set the farewell channel.")
@app_commands.describe(channel="The channel to send farewell messages")
async def setfarewell_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    global FAREWELL_CHANNEL_ID
    FAREWELL_CHANNEL_ID = channel.id
    save_config()
    await interaction.response.send_message(f"Farewell channel set to {channel.mention}.", ephemeral=True)

@bot.event
async def on_member_join(member):
    # Server-specific welcome channel
    welcome_channel_id = get_server_config(member.guild.id, "welcome_channel_id")
    if welcome_channel_id:
        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            # Get member count and calculate member number
            member_count = member.guild.member_count
            member_number = member_count  # The new member is the latest count
            
            # Create welcome message with configurable rules channel
            description = f"wELCOME tO tHE sERVER, {member.mention}! 💖\n\n"
            
            # Use configured rules channel or fallback message
            rules_channel_id = get_server_config(member.guild.id, "rules_channel_id")
            if rules_channel_id:
                description += f"📋 pLEASE rEAD <#{rules_channel_id}> tO gET sTARTED!\n"
            else:
                description += "📋 pLEASE cHECK tHE rULES cHANNEL tO gET sTARTED!\n"
            
            description += f"🎉 wE nOW hAVE {member_count} mEMBERS!\n"
            description += f"🎉 yOU aRE oUR {member_number}th mEMBER!\n\n"
            description += "mAKE yOURSELF aT hOME!"
            
            embed = nova_embed("👋 wELCOME!", description)
            await channel.send(embed=embed)
    
    # Log to join/leave logs and central logging
    join_leave_channel_id = get_server_config(member.guild.id, "join_leave_logs_channel_id")
    if join_leave_channel_id:
        log_channel = member.guild.get_channel(join_leave_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="👋 mEMBER jOINED",
                description=f"**{member.display_name}** ({member.mention}) jOINED tHE sERVER",
                color=0x00ff00,
                timestamp=datetime.now(pytz.UTC)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="aCCOUNT cREATED", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
            embed.add_field(name="mEMBER cOUNT", value=str(member.guild.member_count), inline=True)
            await log_channel.send(embed=embed)
    
    # Central logging
    try:
        await log_to_central_channel(member.guild.id, "join_leave", embed)
    except:
        pass

@bot.event
async def on_member_remove(member):
    # Server-specific farewell channel
    farewell_channel_id = get_server_config(member.guild.id, "farewell_channel_id")
    if farewell_channel_id:
        channel = member.guild.get_channel(farewell_channel_id)
        if channel:
            embed = nova_embed("👋 fAREWELL!", f"{member.display_name} hAS lEFT tHE sERVER. wE'LL mISS yOU! 😢")
            await channel.send(embed=embed)
    
    # Log to join/leave logs and central logging
    join_leave_channel_id = get_server_config(member.guild.id, "join_leave_logs_channel_id")
    if join_leave_channel_id:
        log_channel = member.guild.get_channel(join_leave_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="👋 mEMBER lEFT",
                description=f"**{member.display_name}** ({member.mention}) lEFT tHE sERVER",
                color=0xff0000,
                timestamp=datetime.now(pytz.UTC)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="jOINED sERVER", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if member.joined_at else "Unknown", inline=True)
            embed.add_field(name="mEMBER cOUNT", value=str(member.guild.member_count), inline=True)
            await log_channel.send(embed=embed)
    
    # Central logging
    try:
        await log_to_central_channel(member.guild.id, "join_leave", embed)
    except:
        pass
@bot.command()
async def imposter(ctx):
    if ctx.guild is None:
        await ctx.send(embed=nova_embed("iMPOSTER", "tHIS cOMMAND mUST bE uSED iN a sERVER cHANNEL!"))
        return
    word_list = [
        "banana", "apple", "grape", "peach", "lemon", "carrot", "onion", "potato", "pizza", "burger",
        "sushi", "taco", "pasta", "croissant", "ramen", "falafel", "burrito", "cheesecake", "donut", "waffle",
        "mountain", "beach", "desert", "forest", "island", "volcano", "river", "ocean", "cave", "valley",
        "laptop", "phone", "keyboard", "camera", "guitar", "piano", "bicycle", "skateboard", "umbrella", "backpack",
        "dragon", "unicorn", "zombie", "robot", "pirate", "wizard", "ghost", "alien", "vampire", "mermaid",
        "diamond", "gold", "ruby", "sapphire", "bob", "pearl", "opal", "jade", "topaz", "nicki", "chile", 
    ]
    instructions_embed = discord.Embed(
        title="🕵️ iMPOSTER gAME - hOW tO pLAY",
        description=(
            "**rULES:**\n"
            "• eVERYONE gETS tHE sAME wORD eXCEPT oNE pERSON (tHE iMPOSTER)\n"
            "• tHE iMPOSTER gETS a dIFFERENT wORD\n"
            "• tAKE tURNS dESCRIBING yOUR wORD wITHOUT sAYING iT\n"
            "• tRY tO fIGURE oUT wHO tHE iMPOSTER iS!\n\n"
            "**rEACT wITH 🕵️ tO jOIN tHE gAME!**\n"
            "yOU hAVE 30 sECONDS tO jOIN..."
        ),
        color=0xff69b4
    )
    join_msg = await ctx.send(embed=instructions_embed)
    await join_msg.add_reaction("🕵️")
    reacted_users = set()
    def check(reaction, user):
        return (
            reaction.message.id == join_msg.id and
            str(reaction.emoji) == "🕵️" and
            not user.bot and
            user not in reacted_users
        )
    
    try:
        while True:
            reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
            reacted_users.add(user)
    except asyncio.TimeoutError:
        pass
    players = list(reacted_users)
    if len(players) < 3:
        await ctx.send(embed=nova_embed("iMPOSTER", "nOT eNOUGH pLAYERS rEACTED! gAME cANCELLED, bABY!"))
        return
    imposter = random.choice(players)
    secret_word = random.choice(word_list)
    imposter_word = random.choice([w for w in word_list if w != secret_word])
    failed = []
    for m in players:
        try:
            if m == imposter:
                await m.send(embed=nova_embed("iMPOSTER wORD", f"yOU aRE tHE iMPOSTER! yOUR wORD iS: **{imposter_word}**"))
            else:
                await m.send(embed=nova_embed("iMPOSTER wORD", f"yOUR wORD iS: **{secret_word}**"))
        except Exception:
            failed.append(m.display_name)
    joined_names = ", ".join([f"**{u.display_name}**" for u in players])
    await ctx.send(embed=nova_embed("iMPOSTER", f"aLL sECRET wORDS hAVE bEEN sENT!\n\n**pLAYERS:** {joined_names}"))
    if failed:
        await ctx.send(embed=nova_embed("iMPOSTER", f"cOULD nOT dM: {', '.join(failed)}"))
    # --- Rounds ---
    round_num = 1
    max_rounds = 10
    game_over = False
    while round_num <= max_rounds and not game_over:
        await ctx.send(embed=nova_embed(f"rOUND {round_num}", "eVERYONE, sAY yOUR wORD! nOVA wILL tAG yOU oNE bY oNE."))
        for p in players:
            await ctx.send(f"{p.mention}, iT'S yOUR tURN tO sAY yOUR wORD!")
            def msg_check(m):
                return m.author == p and m.channel == ctx.channel
            try:
                await bot.wait_for("message", timeout=60.0, check=msg_check)
            except asyncio.TimeoutError:
                await ctx.send(f"{p.mention} dID nOT rESPOND iN tIME!")
        # Voting to continue or end
        vote_msg = await ctx.send(embed=nova_embed("cONTINUE oR eND?", "rEACT wITH ✅ tO cONTINUE, ❌ tO eND tHE gAME!"))
        await vote_msg.add_reaction("✅")
        await vote_msg.add_reaction("❌")
        await asyncio.sleep(20)  # 20 seconds to vote
        vote_msg = await ctx.channel.fetch_message(vote_msg.id)
        cont_votes = 0
        end_votes = 0
        for reaction in vote_msg.reactions:
            if str(reaction.emoji) == "✅":
                cont_votes = reaction.count - 1
            elif str(reaction.emoji) == "❌":
                end_votes = reaction.count - 1
        if end_votes > cont_votes:
            game_over = True
            await ctx.send(embed=nova_embed("gAME eNDING", "mAJORITY vOTED tO eND tHE gAME!"))
        else:
         round_num += 1
    # --- Final Voting ---
    await ctx.send(embed=nova_embed("vOTE tHE iMPOSTER!", "rEACT wITH tHE eMOJI fOR wHO yOU tHINK iS tHE iMPOSTER!"))
    emojis = [chr(0x1F1E6 + i) for i in range(len(players))]  # 🇦, 🇧, 🇨, ...
    vote_embed = discord.Embed(title="vOTE tHE iMPOSTER!", description="\n".join([f"{emojis[i]} {players[i].mention}" for i in range(len(players))]), color=0xff69b4)
    vote_embed.set_footer(text="nOVA")
    vote_msg = await ctx.send(embed=vote_embed)
    for e in emojis:
        await vote_msg.add_reaction(e)
    await asyncio.sleep(20)  # 20 seconds to vote
    vote_msg = await ctx.channel.fetch_message(vote_msg.id)
    votes = [0] * len(players)
    for reaction in vote_msg.reactions:
        if reaction.emoji in emojis:
            idx = emojis.index(reaction.emoji)
            votes[idx] = reaction.count - 1
    max_votes = max(votes)
    if votes.count(max_votes) > 1:
        await ctx.send(embed=nova_embed("nO wINNER", "iT'S a tIE! nO oNE wINS!"))
        return
    voted_idx = votes.index(max_votes)
    voted_player = players[voted_idx]
    if voted_player == imposter:
        # Crew wins
        for p in players:
            if p != imposter:
                change_balance(p.id, 200)
        await ctx.send(embed=nova_embed("cREW wINS!", f"tHE cREW fOUND tHE iMPOSTER!\n\n{imposter.mention} wAS tHE iMPOSTER!\n\n{', '.join([pl.mention for pl in players if pl != imposter])} gET 200 {CURRENCY_NAME} eACH!"))
    else:
        # Imposter wins
        change_balance(imposter.id, 500)
        await ctx.send(embed=nova_embed("iMPOSTER wINS!", f"{imposter.mention} sURVIVED! tHEY gET 500 {CURRENCY_NAME}!"))

@bot.tree.command(name="imposter", description="Start an imposter game and DM secret words!")
async def imposter_slash(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(embed=nova_embed("iMPOSTER", "tHIS cOMMAND mUST bE uSED iN a sERVER cHANNEL!"), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    # Get all non-bot members who can see the channel
    channel = interaction.channel
    if not hasattr(channel, 'members'):
        await interaction.followup.send(embed=nova_embed("iMPOSTER", "cOULD nOT gET cHANNEL mEMBERS!"), ephemeral=True)
        return
    members = [m for m in channel.members if not m.bot]
    if len(members) < 3:
        await interaction.followup.send(embed=nova_embed("iMPOSTER", "nEED aT lEAST 3 pEOPLE tO pLAY!"), ephemeral=True)
        return
    imposter = random.choice(members)
    word_list = ["banana", "apple", "grape", "peach", "lemon", "carrot", "onion", "potato", "pizza", "burger"]
    secret_word = random.choice(word_list)
    imposter_word = random.choice([w for w in word_list if w != secret_word])
    # Send game start message
    msg = await channel.send(embed=nova_embed("iMPOSTER gAME", f"rEACT wITH 🕵️ tO tHIS mESSAGE tO jOIN!\n\nyOU hAVE 45 sECONDS..."))
    await msg.add_reaction("🕵️")
    failed = []
    for m in members:
        try:
            if m == imposter:
                await m.send(embed=nova_embed("iMPOSTER wORD", f"yOU aRE tHE iMPOSTER! yOUR wORD iS: **{imposter_word}**"))
            else:
                await m.send(embed=nova_embed("iMPOSTER wORD", f"yOUR wORD iS: **{secret_word}**"))
        except Exception:
            failed.append(m.display_name)
    if failed:
        await channel.send(embed=nova_embed("iMPOSTER", f"cOULD nOT dM: {', '.join(failed)}"))
    await channel.send(embed=nova_embed("iMPOSTER", "aLL sECRET wORDS hAVE bEEN sENT!"))
    await interaction.followup.send(embed=nova_embed("iMPOSTER", "gAME sTARTED! cHECK yOUR dMS!"), ephemeral=True)
    

@bot.command()
async def warn(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("wARN", "yOU dON'T hAVE pERMISSION!"))
        return
    if member is None:
        await ctx.send("Usage: ?warn @user [reason] - Warns a member. Only mods/admins can use this.")
        return
    try:
        # Add infraction to user's record
        user_id = str(member.id)
        if user_id not in INFRACTIONS:
            INFRACTIONS[user_id] = []
        
        INFRACTIONS[user_id].append({
            "type": "warning",
            "reason": reason,
            "date": datetime.now(dt_timezone.utc).isoformat(),
            "moderator": str(ctx.author)
        })
        save_infractions()
        
        # Log the warning
        log_case(ctx.guild.id, "Warn", ctx.author, ctx.channel, datetime.now(dt_timezone.utc))
        # Log to mod logs channel
        await log_mod_action(ctx.guild, "warn", ctx.author, member, reason)
        # DM the user
        try:
            await member.send(embed=nova_embed("wARNED bY nOVA", f"yOU wERE wARNED iN {ctx.guild.name} bY {ctx.author.mention} fOR: {reason}"))
        except Exception:
            pass  # Ignore if DMs are closed
        
        warning_count = len(INFRACTIONS[user_id])
        await ctx.send(embed=nova_embed("wARN", f"{member.mention} wAS wARNED fOR: {reason}\n\ntOTAL wARNINGS: {warning_count}"))
    except Exception as e:
        await ctx.send(embed=nova_embed("wARN", f"cOULD nOT wARN: {e}"))

# Slash command version of warn
@bot.tree.command(name="warn", description="Warn a member (mods only)")
@app_commands.describe(member="The member to warn", reason="Reason for warning")
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("wARN", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    try:
        log_case(interaction.guild.id, "Warn", interaction.user, interaction.channel, datetime.now(dt_timezone.utc))
        # Log to mod logs channel
        await log_mod_action(interaction.guild, "warn", interaction.user, member, reason)
        try:
            await member.send(embed=nova_embed("wARNED bY nOVA", f"yOU wERE wARNED iN {interaction.guild.name} bY {interaction.user.mention} fOR: {reason}"))
        except Exception:
            pass
        await interaction.response.send_message(embed=nova_embed("wARN", f"{member.mention} wAS wARNED fOR: {reason}"))
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("wARN", f"cOULD nOT wARN: {e}"), ephemeral=True)

# =========================
# Support Ticket System
# =========================

# Global variables for ticket system
TICKET_CATEGORY_ID = None
SUPPORT_ROLE_ID = None
TICKET_LOGS_CHANNEL_ID = None
ticket_counter = 1

class TicketModal(discord.ui.Modal, title='Create Support Ticket'):
    def __init__(self):
        super().__init__()
        
    subject = discord.ui.TextInput(
        label='Subject',
        placeholder='Brief description of your issue...',
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label='Description',
        placeholder='Detailed description of your issue...',
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )
    
    priority = discord.ui.TextInput(
        label='Priority (Low/Normal/High/Urgent)',
        placeholder='Normal',
        default='Normal',
        max_length=10,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter
        
        # Create ticket channel
        guild = interaction.guild
        category = None
        if TICKET_CATEGORY_ID:
            category = guild.get_channel(TICKET_CATEGORY_ID)
        
        # Create channel with unique name
        channel_name = f"ticket-{ticket_counter:04d}-{interaction.user.name}"
        ticket_counter += 1
        
        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add support role if set
        if SUPPORT_ROLE_ID:
            support_role = guild.get_role(SUPPORT_ROLE_ID)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )
            
            # Validate and format priority
            priority_input = self.priority.value.strip().lower() if self.priority.value else 'normal'
            priority_emojis = {
                'low': '🟢 Low',
                'normal': '🔵 Normal', 
                'high': '🟠 High',
                'urgent': '🔴 Urgent'
            }
            
            # Default to normal if invalid priority
            if priority_input not in priority_emojis:
                priority_input = 'normal'
            
            priority_display = priority_emojis[priority_input]
            
            # Create ticket embed
            embed = nova_embed(
                "🎫 sUPPORT tICKET",
                f"**Subject:** {self.subject.value}\n**Description:** {self.description.value}\n\n**Created by:** {interaction.user.mention}"
            )
            embed.add_field(name="Status", value="🟢 Open", inline=True)
            embed.add_field(name="Priority", value=priority_display, inline=True)
            
            # Create close butto
            view = TicketCloseView()
            
            await ticket_channel.send(embed=embed, view=view)
            
            # Mention support role if exists
            if SUPPORT_ROLE_ID:
                support_role = guild.get_role(SUPPORT_ROLE_ID)
                if support_role:
                    await ticket_channel.send(f"{support_role.mention} New ticket created!")
            
            await interaction.response.send_message(
                embed=nova_embed("✅ tICKET cREATED", f"Your ticket has been created: {ticket_channel.mention}"),
                ephemeral=True
            )
            
            # Log ticket creation to ticket logs channel
            if TICKET_LOGS_CHANNEL_ID:
                logs_channel = guild.get_channel(TICKET_LOGS_CHANNEL_ID)
                if logs_channel:
                    log_embed = nova_embed(
                        "🎫 tICKET cREATED",
                        f"**Channel:** {ticket_channel.mention}\n**Creator:** {interaction.user.mention}\n**Subject:** {self.subject.value}\n**Priority:** {priority_display}\n**Description:** {self.description.value}"
                    )
                    log_embed.timestamp = datetime.now(dt_timezone.utc)
                    await logs_channel.send(embed=log_embed)
            
        except Exception as e:
            await interaction.response.send_message(
                embed=nova_embed("❌ eRROR", f"Failed to create ticket: {e}"),
                ephemeral=True
            )

class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Create Ticket', style=discord.ButtonStyle.primary, emoji='🎫')
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, emoji='🔒')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has permission to close ticket
        channel = interaction.channel
        if not (interaction.user.guild_permissions.manage_channels or 
                channel.name.endswith(interaction.user.name) or
                (SUPPORT_ROLE_ID and SUPPORT_ROLE_ID in [role.id for role in interaction.user.roles])):
            await interaction.response.send_message(
                embed=nova_embed("❌ nO pERMISSION", "You don't have permission to close this ticket!"),
                ephemeral=True
            )
            return
        
        # Create transcript
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            if not message.author.bot or message.embeds:
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = message.content if message.content else "[Embed/Attachment]"
                messages.append(f"[{timestamp}] {message.author}: {content}")
        
        transcript = "\n".join(messages)
        
        # Send transcript to user via DM and logs channel
        try:
            transcript_file = discord.File(
                io.StringIO(transcript), 
                filename=f"ticket-transcript-{channel.name}.txt"
            )
            
            # Find the ticket creator
            creator_name = channel.name.split('-')[-1]
            creator = discord.utils.get(interaction.guild.members, name=creator_name)
            
            if creator:
                await creator.send(
                    embed=nova_embed("📄 tICKET tRANSCRIPT", f"Your ticket **{channel.name}** has been closed."),
                    file=transcript_file
                )
            
            # Log ticket closure to ticket logs channel
            if TICKET_LOGS_CHANNEL_ID:
                logs_channel = interaction.guild.get_channel(TICKET_LOGS_CHANNEL_ID)
                if logs_channel:
                    # Create a new file object for the logs channel
                    logs_transcript_file = discord.File(
                        io.StringIO(transcript), 
                        filename=f"ticket-transcript-{channel.name}.txt"
                    )
                    
                    log_embed = nova_embed(
                        "🔒 tICKET cLOSED",
                        f"**Channel:** {channel.name}\n**Closed by:** {interaction.user.mention}\n**Creator:** {creator.mention if creator else 'Unknown'}"
                    )
                    log_embed.timestamp = datetime.now(dt_timezone.utc)
                    await logs_channel.send(embed=log_embed, file=logs_transcript_file)
                    
        except Exception as e:
            print(f"Failed to send transcript: {e}")
        
        # Close the ticket
        await interaction.response.send_message(
            embed=nova_embed("🔒 tICKET cLOSED", "This ticket will be deleted in 5 seconds...")
        )
        
        await asyncio.sleep(5)
        await channel.delete(reason="Ticket closed")

@bot.command()
async def ticket(ctx):
    """Create a support ticket panel"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("tICKET", "Only mods/admins can create ticket panels!"))
        return
    
    embed = nova_embed(
        "🎫 sUPPORT tICKETS",
        "Need help? Click the button below to create a support ticket!\n\n"
        "📋 Please provide a clear subject and description\n"
        "⏱️ Our team will respond as soon as possible\n"
        "🔒 Only you and staff can see your ticket"
    )
    
    view = TicketCreateView()
    await ctx.send(embed=embed, view=view)
    await ctx.message.delete()

@bot.tree.command(name="ticket", description="Create a support ticket panel (mods only)")
async def ticket_slash(interaction: discord.Interaction):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(
            embed=nova_embed("tICKET", "Only mods/admins can create ticket panels!"),
            ephemeral=True
        )
        return
    
    embed = nova_embed(
        "🎫 sUPPORT tICKETS",
        "Need help? Click the button below to create a support ticket!\n\n"
        "📋 Please provide a clear subject and description\n"
        "⏱️ Our team will respond as soon as possible\n"
        "🔒 Only you and staff can see your ticket"
    )
    
    view = TicketCreateView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.command()
async def setticketcategory(ctx, category: discord.CategoryChannel = None):
    """Set the category for support tickets"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET tICKET cATEGORY", "Only mods/admins can set ticket category!"))
        return
    
    global TICKET_CATEGORY_ID
    if category is None:
        TICKET_CATEGORY_ID = None
        await ctx.send(embed=nova_embed("sET tICKET cATEGORY", "Ticket category cleared! Tickets will be created in the main channel list."))
    else:
        TICKET_CATEGORY_ID = category.id
        await ctx.send(embed=nova_embed("sET tICKET cATEGORY", f"Ticket category set to: {category.name}"))
    save_config()

@bot.command()
async def setsupportrole(ctx, role: discord.Role = None):
    """Set the support role for tickets"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET sUPPORT rOLE", "Only mods/admins can set support role!"))
        return
    
    global SUPPORT_ROLE_ID
    if role is None:
        SUPPORT_ROLE_ID = None
        await ctx.send(embed=nova_embed("sET sUPPORT rOLE", "Support role cleared!"))
    else:
        SUPPORT_ROLE_ID = role.id
        await ctx.send(embed=nova_embed("sET sUPPORT rOLE", f"Support role set to: {role.name}"))
    save_config()

@bot.command()
async def setticketlogs(ctx, channel: discord.TextChannel = None):
    """Set the ticket logs channel"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET tICKET lOGS", "Only mods/admins can set ticket logs channel!"))
        return
    
    global TICKET_LOGS_CHANNEL_ID
    if channel is None:
        TICKET_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET tICKET lOGS", "Ticket logs channel cleared!"))
    else:
        TICKET_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET tICKET lOGS", f"Ticket logs channel set to: {channel.mention}"))
    save_config()

@bot.tree.command(name="setticketlogs", description="Set the ticket logs channel (mods only)")
@app_commands.describe(channel="The channel to log ticket activity")
async def setticketlogs_slash(interaction: discord.Interaction, channel: discord.TextChannel = None):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(
            embed=nova_embed("sET tICKET lOGS", "Only mods/admins can set ticket logs channel!"),
            ephemeral=True
        )
        return
    
    global TICKET_LOGS_CHANNEL_ID
    if channel is None:
        TICKET_LOGS_CHANNEL_ID = None
        await interaction.response.send_message(
            embed=nova_embed("sET tICKET lOGS", "Ticket logs channel cleared!"),
            ephemeral=True
        )
    else:
        TICKET_LOGS_CHANNEL_ID = channel.id
        await interaction.response.send_message(
            embed=nova_embed("sET tICKET lOGS", f"Ticket logs channel set to: {channel.mention}"),
            ephemeral=True
        )
    save_config()

# Temporary debug command to get emoji IDs
@bot.command()
async def getemojis(ctx):
    """Debug command to get all custom emoji IDs"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("gET eMOJIS", "Only mods/admins can use this command!"))
        return
    
    guild = ctx.guild
    if not guild:
        await ctx.send("This command must be used in a server.")
        return
    
    emoji_list = []
    for emoji in guild.emojis:
        emoji_list.append(f"{emoji.name}: `<:{emoji.name}:{emoji.id}>`")
    
    if not emoji_list:
        await ctx.send(embed=nova_embed("gET eMOJIS", "No custom emojis found in this server."))
        return
    
    # Split into chunks if too many emojis
    chunk_size = 10
    for i in range(0, len(emoji_list), chunk_size):
        chunk = emoji_list[i:i+chunk_size]
        embed = nova_embed(
            f"cUSTOM eMOJIS ({i+1}-{min(i+chunk_size, len(emoji_list))} of {len(emoji_list)})",
            "\n".join(chunk)
        )
        await ctx.send(embed=embed)

# =========================
# New Feature Commands
# =========================

# Global variables for new features
BLACKLIST_WORDS = set()
PET_DATA = {}  # user_id: {"name": str, "type": str, "level": int, "xp": int, "hunger": int, "cleanliness": int, "happiness": int, "changed_pet": bool}
FOCUS_SESSIONS = {}  # user_id: {"start_time": datetime, "duration": int, "breaks": int}
LOTTERY_PARTICIPANTS = set()  # user_ids
INFRACTIONS = {}  # user_id: [{"type": str, "reason": str, "date": datetime, "moderator": str}]

# Load data files for new features
def load_blacklist():
    global BLACKLIST_WORDS
    try:
        with open("blacklist.json", "r") as f:
            BLACKLIST_WORDS = set(json.load(f))
    except FileNotFoundError:
        BLACKLIST_WORDS = set()

def save_blacklist():
    with open("blacklist.json", "w") as f:
        json.dump(list(BLACKLIST_WORDS), f)

def load_auto_reactions():
    global AUTO_REACTIONS
    try:
        with open("auto_reactions.json", "r") as f:
            AUTO_REACTIONS = json.load(f)
    except FileNotFoundError:
        AUTO_REACTIONS = {}

def load_pets():
    global PET_DATA
    try:
        with open("pets.json", "r") as f:
            PET_DATA = json.load(f)
    except FileNotFoundError:
        PET_DATA = {}

def save_pets():
    with open("pets.json", "w") as f:
        json.dump(PET_DATA, f)

def load_infractions():
    global INFRACTIONS
    try:
        with open("infractions.json", "r") as f:
            content = f.read().strip()
            if not content:  # Handle empty file
                INFRACTIONS = {}
                return
            
            data = json.loads(content)
            # Convert date strings back to datetime objects
            for user_id, infractions in data.items():
                for infraction in infractions:
                    if isinstance(infraction.get("date"), str):
                        try:
                            infraction["date"] = datetime.fromisoformat(infraction["date"])
                        except ValueError:
                            # If date parsing fails, use current time
                            infraction["date"] = datetime.now(dt_timezone.utc)
            INFRACTIONS = data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load infractions.json ({e}). Starting with empty infractions.")
        INFRACTIONS = {}
        # Create a fresh infractions file
        save_infractions()

def save_infractions():
    with open("infractions.json", "w") as f:
        # Convert datetime objects to strings for JSON serialization
        data = {}
        for user_id, infractions in INFRACTIONS.items():
            data[user_id] = []
            for infraction in infractions:
                infraction_copy = infraction.copy()
                # Handle both datetime objects and strings
                if hasattr(infraction["date"], 'isoformat'):
                    infraction_copy["date"] = infraction["date"].isoformat()
                else:
                    infraction_copy["date"] = str(infraction["date"])
                data[user_id].append(infraction_copy)
        json.dump(data, f)

def add_infraction(user_id, infraction_type, reason, moderator):
    user_id = str(user_id)
    if user_id not in INFRACTIONS:
        INFRACTIONS[user_id] = []
    INFRACTIONS[user_id].append({
        "type": infraction_type,
        "reason": reason,
        "date": datetime.now(),
        "moderator": moderator
    })
    save_infractions()

# Load all new feature data on startup
load_blacklist()
load_auto_reactions()
load_pets()
load_infractions()

# Drama command
@bot.command()
async def drama(ctx):
    """Nova spills random fake tea between server members"""
    members = [m for m in ctx.guild.members if not m.bot and m != ctx.author]
    if len(members) < 2:
        await ctx.send(embed=nova_embed("dRAMA", "nOT eNOUGH mEMBERS fOR dRAMA!"))
        return
    
    member1, member2 = random.sample(members, 2)
    
    drama_scenarios = [
        f"i hEARD {member1.mention} sAID {member2.mention}'S fAVORITE pIZZA tOPPING iS pINEAPPLE...",
        f"{member1.mention} aPPARENTLY tHINKS {member2.mention} pUTS mILK bEFORE cEREAL... sCANDALOUS!",
        f"rUMOR hAS iT {member2.mention} tOLD eVERYONE tHAT {member1.mention} sTILL sLEEPS wITH a tEDDY bEAR!",
        f"i cAN'T bELIEVE {member1.mention} sAID {member2.mention} uNIRONICALLY lIKES nICKELBACK!",
        f"{member2.mention} aPPARENTLY cAUGHT {member1.mention} tALKING tO tHEIR pLANTS... aGAIN!",
        f"wORD oN tHE sTREET iS {member1.mention} tHINKS {member2.mention} aCTUALLY eNJOYS mONDAYS...",
        f"{member1.mention} rEPORTEDLY sAW {member2.mention} eATING pIZZA wITH a fORK aND kNIFE...",
        f"i hEARD {member2.mention} tOLD eVERYONE tHAT {member1.mention} likes cougars..."
    ]
    
    drama_text = random.choice(drama_scenarios)
    embed = nova_embed("☕ tEA tIME ☕", drama_text)
    await ctx.send(embed=embed)

# Server info command
@bot.command()
async def serverinfo(ctx):
    """Shows server information"""
    guild = ctx.guild
    
    # Count different member types
    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    online = len([m for m in guild.members if m.status != discord.Status.offline])
    
    # Get creation date
    created = guild.created_at.strftime("%B %d, %Y")
    
    # Get owner
    owner = guild.owner
    
    embed = nova_embed(
        f"📊 {guild.name} iNFO",
        f"**mEMBERS:** {total_members} ({humans} hUMANS, {bots} bOTS)\n"
        f"**oNLINE:** {online}\n"
        f"**cREATED:** {created}\n"
        f"**oWNER:** {owner.mention if owner else 'uNKNOWN'}\n"
        f"**cHANNELS:** {len(guild.channels)}\n"
        f"**rOLES:** {len(guild.roles)}\n"
        f"**bOOST lEVEL:** {guild.premium_tier}\n"
        f"**bOOSTS:** {guild.premium_subscription_count}"
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

# Blacklist command
@bot.command()
async def blacklist(ctx, *, word=None):
    """Add or remove words from the blacklist (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bLACKLIST", "Only mods/admins can manage the blacklist!"))
        return
    
    if word is None:
        if not BLACKLIST_WORDS:
            await ctx.send(embed=nova_embed("bLACKLIST", "nO wORDS aRE cURRENTLY bLACKLISTED."))
        else:
            word_list = "\n".join([f"• {w}" for w in sorted(BLACKLIST_WORDS)])
            embed = nova_embed("bLACKLIST", f"cURRENT bLACKLISTED wORDS:\n{word_list}")
            await ctx.send(embed=embed)
        return
    
    word = word.lower()
    
    if word in BLACKLIST_WORDS:
        BLACKLIST_WORDS.remove(word)
        save_blacklist()
        await ctx.send(embed=nova_embed("bLACKLIST", f"rEMOVED '{word}' fROM bLACKLIST."))
    else:
        BLACKLIST_WORDS.add(word)
        save_blacklist()
        await ctx.send(embed=nova_embed("bLACKLIST", f"aDDED '{word}' tO bLACKLIST."))

# Focus timer command
@bot.command()
async def focus(ctx, duration: int = 25):
    """Start a Pomodoro-style focus timer"""
    if duration < 1 or duration > 120:
        await ctx.send(embed=nova_embed("fOCUS", "dURATION mUST bE bETWEEN 1-120 mINUTES!"))
        return
    
    user_id = ctx.author.id
    
    if user_id in FOCUS_SESSIONS:
        await ctx.send(embed=nova_embed("fOCUS", "yOU aLREADY hAVE aN aCTIVE fOCUS sESSION!"))
        return
    
    FOCUS_SESSIONS[user_id] = {
        "start_time": datetime.now(),
        "duration": duration,
        "breaks": 0
    }
    
    embed = nova_embed(
        "🎯 fOCUS sESSION sTARTED",
        f"fOCUSING fOR {duration} mINUTES!\n"
        f"i'LL pING yOU wHEN iT'S tIME fOR a bREAK!"
    )
    await ctx.send(embed=embed)
    
    # Wait for the duration and then notify
    await asyncio.sleep(duration * 60)
    
    if user_id in FOCUS_SESSIONS:
        FOCUS_SESSIONS[user_id]["breaks"] += 1
        breaks = FOCUS_SESSIONS[user_id]["breaks"]
        
        break_duration = 15 if breaks % 4 != 0 else 30  # Long break every 4 sessions
        
        embed = nova_embed(
            "⏰ fOCUS sESSION cOMPLETE!",
            f"gREAT jOB! tAKE a {break_duration}-mINUTE bREAK! 🎉\n"
            f"sESSIONS cOMPLETED: {breaks}"
        )
        await ctx.send(f"{ctx.author.mention}", embed=embed)
        
        # Remove session after break
        await asyncio.sleep(break_duration * 60)
        if user_id in FOCUS_SESSIONS:
            del FOCUS_SESSIONS[user_id]

# Lottery command (owner only)
@bot.command()
async def lottery(ctx, action=None, price: int = None):
    """Manage the weekly server lottery (owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("🎰 lOTTERY", "Only the owner can manage the lottery!"))
        return
    
    if action is None:
        # Show current lottery status
        embed = nova_embed(
            "🎰 lOTTERY sTATUS",
            f"pARTICIPANTS: {len(LOTTERY_PARTICIPANTS)}\n"
            f"cURRENT eNTRY cOST: {config.get('lottery_price', 100)} {CURRENCY_NAME}\n\n"
            f"cOMMANDS:\n"
            f"`?lottery start [price]` - Start new lottery with optional price\n"
            f"`?lottery draw` - Draw winner and end current lottery\n"
            f"`?lottery reset` - Reset current lottery\n"
            f"`?lottery price [amount]` - Set entry price"
        )
        await ctx.send(embed=embed)
        return
    
    if action.lower() == "start":
        if price is not None:
            config['lottery_price'] = price
            save_config()
        
        LOTTERY_PARTICIPANTS.clear()
        entry_cost = config.get('lottery_price', 100)
        
        embed = nova_embed(
            "🎰 nEW lOTTERY sTARTED!",
            f"eNTRY cOST: {entry_cost} {CURRENCY_NAME}\n"
            f"uSE `?joinlottery` tO pARTICIPATE!"
        )
        await ctx.send(embed=embed)
    
    elif action.lower() == "draw":
        if not LOTTERY_PARTICIPANTS:
            await ctx.send(embed=nova_embed("🎰 lOTTERY", "nO pARTICIPANTS iN cURRENT lOTTERY!"))
            return
        
        winner_id = random.choice(list(LOTTERY_PARTICIPANTS))
        winner = ctx.guild.get_member(winner_id)
        entry_cost = config.get('lottery_price', 100)
        prize = len(LOTTERY_PARTICIPANTS) * entry_cost
        
        change_balance(winner_id, prize)
        
        embed = nova_embed(
            "🎉 lOTTERY wINNER!",
            f"cONGRATULATIONS {winner.mention}!\n"
            f"yOU wON {prize} {CURRENCY_NAME}!\n\n"
            f"pARTICIPANTS: {len(LOTTERY_PARTICIPANTS)}"
        )
        await ctx.send(embed=embed)
        
        LOTTERY_PARTICIPANTS.clear()
    
    elif action.lower() == "reset":
        LOTTERY_PARTICIPANTS.clear()
        await ctx.send(embed=nova_embed("🎰 lOTTERY", "lOTTERY rESET!"))
    
    elif action.lower() == "price":
        if price is None:
            await ctx.send(embed=nova_embed("🎰 lOTTERY", "pLEASE sPECIFY a pRICE!"))
            return
        
        config['lottery_price'] = price
        save_config()
        await ctx.send(embed=nova_embed("🎰 lOTTERY", f"eNTRY pRICE sET tO {price} {CURRENCY_NAME}!"))
    
    else:
        await ctx.send(embed=nova_embed("🎰 lOTTERY", "iNVALID aCTION! uSE: start, draw, reset, or price"))

# Join lottery command (for regular users)
@bot.command()
async def joinlottery(ctx):
    """Join the current lottery"""
    user_id = ctx.author.id
    
    if user_id in LOTTERY_PARTICIPANTS:
        await ctx.send(embed=nova_embed("🎰 lOTTERY", "yOU'RE aLREADY iN tHIS lOTTERY!"))
        return
    
    entry_cost = config.get('lottery_price', 100)
    
    # Check if user has enough balance
    if get_balance(user_id) < entry_cost:
        await ctx.send(embed=nova_embed("🎰 lOTTERY", f"yOU nEED {entry_cost} {CURRENCY_NAME} tO jOIN tHE lOTTERY!"))
        return
    
    change_balance(user_id, -entry_cost)
    LOTTERY_PARTICIPANTS.add(user_id)
    
    embed = nova_embed(
        "🎰 lOTTERY eNTRY",
        f"yOU'VE jOINED tHIS wEEK'S lOTTERY!\n"
        f"pARTICIPANTS: {len(LOTTERY_PARTICIPANTS)}\n"
        f"pRIZE pOOL: {len(LOTTERY_PARTICIPANTS) * entry_cost} {CURRENCY_NAME}"
    )
    await ctx.send(embed=embed)

# Pet adoption system
class PetView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
    
    @discord.ui.button(label='fEED', style=discord.ButtonStyle.primary, emoji='🍖')
    async def feed_pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("tHIS iSN'T yOUR pET!", ephemeral=True)
            return
        
        user_id = str(self.user_id)
        if user_id not in PET_DATA:
            await interaction.response.send_message("yOU dON'T hAVE a pET!", ephemeral=True)
            return
        
        pet = PET_DATA[user_id]
        if pet["hunger"] >= 100:
            await interaction.response.send_message(f"{pet['name']} iS aLREADY fULL!", ephemeral=True)
            return
        
        pet["hunger"] = min(100, pet["hunger"] + 25)
        pet["happiness"] = min(100, pet["happiness"] + 10)
        pet["xp"] += 5
        
        # Check for level up
        new_level = pet["xp"] // 100 + 1
        level_up = new_level > pet["level"]
        pet["level"] = new_level
        
        save_pets()
        
        message = f"yOU fED {pet['name']}! 🍖\nhUNGER: {pet['hunger']}/100"
        if level_up:
            message += f"\n🎉 {pet['name']} lEVELED uP tO lEVEL {pet['level']}!"
        
        await interaction.response.send_message(message, ephemeral=True)
    
    @discord.ui.button(label='cLEAN', style=discord.ButtonStyle.secondary, emoji='🧽')
    async def clean_pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("tHIS iSN'T yOUR pET!", ephemeral=True)
            return
        
        user_id = str(self.user_id)
        if user_id not in PET_DATA:
            await interaction.response.send_message("yOU dON'T hAVE a pET!", ephemeral=True)
            return
        
        pet = PET_DATA[user_id]
        if pet["cleanliness"] >= 100:
            await interaction.response.send_message(f"{pet['name']} iS aLREADY cLEAN!", ephemeral=True)
            return
        
        pet["cleanliness"] = min(100, pet["cleanliness"] + 30)
        pet["happiness"] = min(100, pet["happiness"] + 15)
        pet["xp"] += 8
        
        # Check for level up
        new_level = pet["xp"] // 100 + 1
        level_up = new_level > pet["level"]
        pet["level"] = new_level
        
        save_pets()
        
        message = f"yOU cLEANED {pet['name']}! 🧽\ncLEANLINESS: {pet['cleanliness']}/100"
        if level_up:
            message += f"\n🎉 {pet['name']} lEVELED uP tO lEVEL {pet['level']}!"
        
        await interaction.response.send_message(message, ephemeral=True)
    
    @discord.ui.button(label='pET', style=discord.ButtonStyle.success, emoji='❤️')
    async def pet_pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("tHIS iSN'T yOUR pET!", ephemeral=True)
            return
        
        user_id = str(self.user_id)
        if user_id not in PET_DATA:
            await interaction.response.send_message("yOU dON'T hAVE a pET!", ephemeral=True)
            return
        
        pet = PET_DATA[user_id]
        pet["happiness"] = min(100, pet["happiness"] + 20)
        pet["xp"] += 3
        
        # Check for level up
        new_level = pet["xp"] // 100 + 1
        level_up = new_level > pet["level"]
        pet["level"] = new_level
        
        save_pets()
        
        responses = [
            f"{pet['name']} pURRS hAPPILY!",
            f"{pet['name']} wAGS tHEIR tAIL!",
            f"{pet['name']} nUZZLES yOU!",
            f"{pet['name']} lOOKS vERY hAPPY!"
        ]
        
        message = random.choice(responses) + f"\nhAPPINESS: {pet['happiness']}/100"
        if level_up:
            message += f"\n🎉 {pet['name']} lEVELED uP tO lEVEL {pet['level']}!"
        
        await interaction.response.send_message(message, ephemeral=True)

@bot.command()
async def adoptpet(ctx):
    """Adopt a virtual pet"""
    user_id = str(ctx.author.id)
    
    if user_id in PET_DATA:
        await ctx.send(embed=nova_embed("aDOPT pET", f"yOU aLREADY hAVE a pET nAMED {PET_DATA[user_id]['name']}!"))
        return
    
    animals = ["Cat", "Dog", "Red Panda", "Raven", "Octopus", "Goldfish", "Tortoise", "Owl", "Lizard", "Bat", "Dove", "Fox"]
    animal_emojis = {"Cat": "🐱", "Dog": "🐶", "Red Panda": "🐼", "Raven": "🐦‍⬛", "Octopus": "🐙", 
                    "Goldfish": "🐠", "Tortoise": "🐢", "Owl": "🦉", "Lizard": "🦎", "Bat": "🦇", "Dove": "🕊️", "Fox": "🦊"}
    
    animal_list = "\n".join([f"{animal_emojis[animal]} {animal}" for animal in animals])
    
    embed = nova_embed(
        "🏠 aDOPT a pET",
        f"cHOOSE yOUR pET:\n{animal_list}\n\ntYPE tHE aNIMAL nAME tO aDOPT!"
    )
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.title() in animals
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        chosen_animal = msg.content.title()
        
        await ctx.send(embed=nova_embed("nAME yOUR pET", f"wHAT wOULD yOU lIKE tO nAME yOUR {chosen_animal}?"))
        
        def name_check(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) <= 20
        
        name_msg = await bot.wait_for('message', check=name_check, timeout=30.0)
        pet_name = name_msg.content
        
        # Create pet data
        PET_DATA[user_id] = {
            "name": pet_name,
            "type": chosen_animal,
            "level": 1,
            "xp": 0,
            "hunger": 100,
            "cleanliness": 100,
            "happiness": 100,
            "changed_pet": False
        }
        save_pets()
        
        embed = nova_embed(
            "🎉 aDOPTION sUCCESSFUL!",
            f"cONGRATULATIONS! yOU aDOPTED {pet_name} tHE {chosen_animal}!\n"
            f"uSE `?pet` tO iNTERACT wITH yOUR nEW fRIEND!"
        )
        embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send(embed=nova_embed("aDOPT pET", "aDOPTION tIMED oUT! tRY aGAIN lATER."))

@bot.command()
async def petname(ctx, *, new_name: str = None):
    """Change your pet's name"""
    user_id = str(ctx.author.id)
    
    if user_id not in PET_DATA:
        await ctx.send(embed=nova_embed("pET nAME", "yOU dON'T hAVE a pET! uSE `?adoptpet` fIRST."))
        return
    
    if not new_name:
        await ctx.send(embed=nova_embed("pET nAME", "pLEASE pROVIDE a nEW nAME fOR yOUR pET!\n\nuSAGE: `?petname <new name>`"))
        return
    
    if len(new_name) > 20:
        await ctx.send(embed=nova_embed("pET nAME", "pET nAME mUST bE 20 cHARACTERS oR lESS!"))
        return
    
    old_name = PET_DATA[user_id]["name"]
    PET_DATA[user_id]["name"] = new_name
    save_pets()
    
    await ctx.send(embed=nova_embed(
        "🏷️ pET nAME cHANGED!",
        f"yOUR pET's nAME hAS bEEN cHANGED fROM **{old_name}** tO **{new_name}**!"
    ))

@bot.command()
async def changepet(ctx):
    """Change your pet type (only once, resets all stats)"""
    user_id = str(ctx.author.id)
    
    if user_id not in PET_DATA:
        await ctx.send(embed=nova_embed("cHANGE pET", "yOU dON'T hAVE a pET! uSE `?adoptpet` fIRST."))
        return
    
    if PET_DATA[user_id].get("changed_pet", False):
        await ctx.send(embed=nova_embed(
            "cHANGE pET", 
            "yOU hAVE aLREADY cHANGED yOUR pET oNCE! yOU cANNOT cHANGE iT aGAIN."
        ))
        return
    
    current_pet = PET_DATA[user_id]
    animals = ["Cat", "Dog", "Red Panda", "Raven", "Octopus", "Goldfish", "Tortoise", "Owl", "Lizard", "Bat", "Dove", "Fox"]
    animal_emojis = {"Cat": "🐱", "Dog": "🐶", "Red Panda": "🐼", "Raven": "🐦‍⬛", "Octopus": "🐙", 
                    "Goldfish": "🐠", "Tortoise": "🐢", "Owl": "🦉", "Lizard": "🦎", "Bat": "🦇", "Dove": "🕊️", "Fox": "🦊"}
    
    animal_list = "\n".join([f"{animal_emojis[animal]} {animal}" for animal in animals])
    
    embed = nova_embed(
        "⚠️ cHANGE pET",
        f"**wARNING:** cHANGING yOUR pET wILL rESET aLL sTATS!\n\n"
        f"cURRENT pET: {current_pet['name']} tHE {current_pet['type']} (lEVEL {current_pet['level']})\n\n"
        f"cHOOSE yOUR nEW pET:\n{animal_list}\n\n"
        f"tYPE tHE aNIMAL nAME tO cONFIRM! (yOU cAN oNLY dO tHIS oNCE)"
    )
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.title() in animals
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        chosen_animal = msg.content.title()
        
        if chosen_animal == current_pet['type']:
            await ctx.send(embed=nova_embed("cHANGE pET", "yOU aLREADY hAVE tHAT tYPE oF pET!"))
            return
        
        # Reset pet with new type but keep name
        PET_DATA[user_id] = {
            "name": current_pet['name'],
            "type": chosen_animal,
            "level": 1,
            "xp": 0,
            "hunger": 100,
            "cleanliness": 100,
            "happiness": 100,
            "changed_pet": True
        }
        save_pets()
        
        embed = nova_embed(
            "🔄 pET cHANGED!",
            f"yOUR pET {current_pet['name']} iS nOW a {chosen_animal}!\n"
            f"aLL sTATS hAVE bEEN rESET tO lEVEL 1.\n\n"
            f"⚠️ yOU cANNOT cHANGE yOUR pET tYPE aGAIN!"
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send(embed=nova_embed("cHANGE pET", "pET cHANGE tIMED oUT! tRY aGAIN lATER."))

@bot.command()
async def pet(ctx):
    """Interact with your pet"""
    user_id = str(ctx.author.id)
    
    if user_id not in PET_DATA:
        await ctx.send(embed=nova_embed("pET", "yOU dON'T hAVE a pET! uSE `?adoptpet` tO aDOPT oNE!"))
        return
    
    pet = PET_DATA[user_id]
    
    # Decrease stats over time (basic simulation)
    import time
    current_time = time.time()
    if "last_update" not in pet:
        pet["last_update"] = current_time
    
    time_diff = (current_time - pet["last_update"]) / 3600  # Hours
    if time_diff > 1:  # Only update if more than 1 hour passed
        pet["hunger"] = max(0, pet["hunger"] - int(time_diff * 5))
        pet["cleanliness"] = max(0, pet["cleanliness"] - int(time_diff * 3))
        pet["happiness"] = max(0, pet["happiness"] - int(time_diff * 2))
        pet["last_update"] = current_time
        save_pets()
    
    # Create status bars
    def create_bar(value, max_val=100):
        filled = int((value / max_val) * 10)
        return "█" * filled + "░" * (10 - filled)
    
    embed = nova_embed(
        f"{pet['name']} tHE {pet['type']}",
        f"**lEVEL:** {pet['level']} (XP: {pet['xp']}/100)\n"
        f"**hUNGER:** {create_bar(pet['hunger'])} {pet['hunger']}/100\n"
        f"**cLEANLINESS:** {create_bar(pet['cleanliness'])} {pet['cleanliness']}/100\n"
        f"**hAPPINESS:** {create_bar(pet['happiness'])} {pet['happiness']}/100"
    )
    
    view = PetView(ctx.author.id)
    await ctx.send(embed=embed, view=view)



# =========================
# New Logging System Commands
# =========================

# Join/Leave logs setup
@bot.command()
async def setjoinleavelogs(ctx, channel: discord.TextChannel = None):
    """Set the join/leave logs channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET jOIN/lEAVE lOGS", "Only mods/admins can set join/leave logs channel!"))
        return
    
    global JOIN_LEAVE_LOGS_CHANNEL_ID
    if channel is None:
        JOIN_LEAVE_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET jOIN/lEAVE lOGS", "Join/leave logs channel cleared!"))
    else:
        JOIN_LEAVE_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET jOIN/lEAVE lOGS", f"Join/leave logs channel set to: {channel.mention}"))
    save_config()

# Server logs setup
@bot.command()
async def setserverlogs(ctx, channel: discord.TextChannel = None):
    """Set the server logs channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET sERVER lOGS", "Only mods/admins can set server logs channel!"))
        return
    
    global SERVER_LOGS_CHANNEL_ID
    if channel is None:
        SERVER_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET sERVER lOGS", "Server logs channel cleared!"))
    else:
        SERVER_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET sERVER lOGS", f"Server logs channel set to: {channel.mention}"))
    save_config()

# Mod logs setup
@bot.command()
async def setmodlogs(ctx, channel: discord.TextChannel = None):
    """Set the mod logs channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET mOD lOGS", "Only mods/admins can set mod logs channel!"))
        return
    
    global MOD_LOGS_CHANNEL_ID
    if channel is None:
        MOD_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET mOD lOGS", "Mod logs channel cleared!"))
    else:
        MOD_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET mOD lOGS", f"Mod logs channel set to: {channel.mention}"))
    save_config()

@bot.command()
async def setlogs(ctx, category_name: str = "📋 Logs"):
    """Automatically create all standard log channels (Admin/Mod only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET lOGS", "Only admins/mods can set up logging channels!"))
        return
    
    guild = ctx.guild
    if not guild:
        await ctx.send(embed=nova_embed("sET lOGS", "This command can only be used in a server!"))
        return
    
    # Send initial status
    status_embed = nova_embed(
        "🔄 sETTING uP lOGGING",
        "Creating standard log channels..."
    )
    status_msg = await ctx.send(embed=status_embed)
    
    try:
        # Create or find logs category
        logs_category = discord.utils.get(guild.categories, name=category_name)
        if not logs_category:
            logs_category = await guild.create_category(
                name=category_name,
                reason=f"Auto-created by {ctx.author} for logging setup"
            )
        
        created_channels = []
        updated_configs = []
        
        # Define standard log channels to create
        log_channels = [
            {
                'name': 'chat-logs',
                'topic': 'Deleted and edited messages',
                'config_var': 'CHAT_LOGS_CHANNEL_ID',
                'config_key': 'chat_logs_channel_id'
            },
            {
                'name': 'join-leave-logs', 
                'topic': 'Member joins and leaves',
                'config_var': 'JOIN_LEAVE_LOGS_CHANNEL_ID',
                'config_key': 'join_leave_logs_channel_id'
            },
            {
                'name': 'server-logs',
                'topic': 'Server changes and member updates', 
                'config_var': 'SERVER_LOGS_CHANNEL_ID',
                'config_key': 'server_logs_channel_id'
            },
            {
                'name': 'mod-logs',
                'topic': 'Moderation actions (bans, kicks, warnings)',
                'config_var': 'MOD_LOGS_CHANNEL_ID', 
                'config_key': 'mod_logs_channel_id'
            },
            {
                'name': 'ticket-logs',
                'topic': 'Ticket system logs',
                'config_var': 'TICKET_LOGS_CHANNEL_ID',
                'config_key': 'ticket_logs_channel_id'
            }
        ]
        
        global CHAT_LOGS_CHANNEL_ID, JOIN_LEAVE_LOGS_CHANNEL_ID, SERVER_LOGS_CHANNEL_ID, MOD_LOGS_CHANNEL_ID, TICKET_LOGS_CHANNEL_ID
        
        # Create each log channel
        for channel_info in log_channels:
            # Check if channel already exists
            existing_channel = discord.utils.get(guild.channels, name=channel_info['name'])
            
            if existing_channel:
                # Channel exists, just update config
                if channel_info['config_var'] == 'CHAT_LOGS_CHANNEL_ID':
                    CHAT_LOGS_CHANNEL_ID = existing_channel.id
                elif channel_info['config_var'] == 'JOIN_LEAVE_LOGS_CHANNEL_ID':
                    JOIN_LEAVE_LOGS_CHANNEL_ID = existing_channel.id
                elif channel_info['config_var'] == 'SERVER_LOGS_CHANNEL_ID':
                    SERVER_LOGS_CHANNEL_ID = existing_channel.id
                elif channel_info['config_var'] == 'MOD_LOGS_CHANNEL_ID':
                    MOD_LOGS_CHANNEL_ID = existing_channel.id
                elif channel_info['config_var'] == 'TICKET_LOGS_CHANNEL_ID':
                    TICKET_LOGS_CHANNEL_ID = existing_channel.id
                
                config[channel_info['config_key']] = existing_channel.id
                updated_configs.append(f"✅ {existing_channel.mention} (existing)")
            else:
                # Create new channel
                new_channel = await guild.create_text_channel(
                    name=channel_info['name'],
                    category=logs_category,
                    topic=channel_info['topic'],
                    reason=f"Auto-created by {ctx.author} for logging setup"
                )
                
                # Update global variables and config
                if channel_info['config_var'] == 'CHAT_LOGS_CHANNEL_ID':
                    CHAT_LOGS_CHANNEL_ID = new_channel.id
                elif channel_info['config_var'] == 'JOIN_LEAVE_LOGS_CHANNEL_ID':
                    JOIN_LEAVE_LOGS_CHANNEL_ID = new_channel.id
                elif channel_info['config_var'] == 'SERVER_LOGS_CHANNEL_ID':
                    SERVER_LOGS_CHANNEL_ID = new_channel.id
                elif channel_info['config_var'] == 'MOD_LOGS_CHANNEL_ID':
                    MOD_LOGS_CHANNEL_ID = new_channel.id
                elif channel_info['config_var'] == 'TICKET_LOGS_CHANNEL_ID':
                    TICKET_LOGS_CHANNEL_ID = new_channel.id
                
                config[channel_info['config_key']] = new_channel.id
                created_channels.append(f"🆕 {new_channel.mention}")
        
        # Save configuration
        save_config()
        
        # Send completion message
        completion_embed = nova_embed(
            "✅ lOGGING sETUP cOMPLETE!",
            f"**Category:** {logs_category.mention}\n\n"
            f"**Created Channels:**\n{chr(10).join(created_channels) if created_channels else 'None (all existed)'}\n\n"
            f"**Configured Channels:**\n{chr(10).join(updated_configs)}\n\n"
            f"All standard logging is now active!"
        )
        completion_embed.add_field(
            name="📋 Available Log Types",
            value="• **Chat Logs** - Deleted/edited messages\n"
                  "• **Join/Leave Logs** - Member activity\n"
                  "• **Server Logs** - Server changes & member updates\n"
                  "• **Mod Logs** - Moderation actions\n"
                  "• **Ticket Logs** - Ticket system activity",
            inline=False
        )
        completion_embed.set_footer(text=f"Set up by {ctx.author}")
        await status_msg.edit(embed=completion_embed)
        
    except discord.Forbidden:
        await status_msg.edit(embed=nova_embed(
            "❌ pERMISSION eRROR",
            "I don't have permission to create channels or categories!\n"
            "Please give me **Manage Channels** permission."
        ))
    except Exception as e:
        await status_msg.edit(embed=nova_embed(
            "❌ sETUP fAILED",
            f"An error occurred: {str(e)}"
        ))
        print(f"Error in setlogs command: {e}")
        import traceback
        traceback.print_exc()

@bot.command()
async def scanhistory(ctx):
    """Scan server message history to build comprehensive activity stats (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("sCAN hISTORY", "oNLY tHE oWNER cAN rUN tHIS cOMMAND!"))
        return
    
    if not ctx.guild:
        await ctx.send(embed=nova_embed("sCAN hISTORY", "tHIS cOMMAND cAN oNLY bE uSED iN sERVERS!"))
        return
    
    guild = ctx.guild
    guild_id = guild.id
    
    # Send initial status
    status_embed = nova_embed(
        "🔍 sCAN hISTORY",
        f"Scanning message history for **{guild.name}**...\n"
        f"This may take several minutes for large servers."
    )
    status_msg = await ctx.send(embed=status_embed)
    
    try:
        # Initialize or clear existing data for this server
        MESSAGE_ACTIVITY[guild_id] = {}
        
        total_messages = 0
        total_channels = 0
        processed_channels = 0
        
        # Get all text channels
        text_channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]
        total_channels = len(text_channels)
        
        # Update status
        await status_msg.edit(embed=nova_embed(
            "🔍 sCAN hISTORY",
            f"Found {total_channels} text channels to scan...\n"
            f"Starting historical scan from server creation: {guild.created_at.strftime('%B %d, %Y')}"
        ))
        
        for channel in text_channels:
            try:
                processed_channels += 1
                channel_messages = 0
                
                # Update progress every few channels
                if processed_channels % 5 == 0 or processed_channels == total_channels:
                    progress_embed = nova_embed(
                        "🔍 sCAN hISTORY",
                        f"**Progress:** {processed_channels}/{total_channels} channels\n"
                        f"**Current:** #{channel.name}\n"
                        f"**Total Messages:** {total_messages:,}\n"
                        f"**Channel Messages:** {channel_messages:,}"
                    )
                    await status_msg.edit(embed=progress_embed)
                
                # Scan messages in this channel (from oldest to newest)
                async for message in channel.history(limit=None, oldest_first=True):
                    # Skip bot messages
                    if message.author.bot:
                        continue
                    
                    user_id = message.author.id
                    message_date = message.created_at
                    
                    # Initialize user data if needed
                    if user_id not in MESSAGE_ACTIVITY[guild_id]:
                        MESSAGE_ACTIVITY[guild_id][user_id] = []
                    
                    user_messages = MESSAGE_ACTIVITY[guild_id][user_id]
                    
                    # Check if we can batch with recent entry (within same day)
                    if (user_messages and 
                        user_messages[-1]["timestamp"].date() == message_date.date()):
                        # Update the most recent entry for this day
                        user_messages[-1]["count"] += 1
                        if message_date > user_messages[-1]["timestamp"]:
                            user_messages[-1]["timestamp"] = message_date
                    else:
                        # Create a new entry for this day
                        user_messages.append({
                            "timestamp": message_date,
                            "count": 1
                        })
                    
                    total_messages += 1
                    channel_messages += 1
                    
                    # Save periodically to avoid memory issues
                    if total_messages % 10000 == 0:
                        save_message_activity()
                        await status_msg.edit(embed=nova_embed(
                            "🔍 sCAN hISTORY",
                            f"**Progress:** {processed_channels}/{total_channels} channels\n"
                            f"**Current:** #{channel.name}\n"
                            f"**Total Messages:** {total_messages:,}\n"
                            f"**Saving progress...**"
                        ))
                
            except discord.Forbidden:
                # Skip channels we can't access
                continue
            except Exception as e:
                print(f"Error scanning channel {channel.name}: {e}")
                continue
        
        # Final save
        save_message_activity()
        
        # Calculate some stats
        unique_users = len(MESSAGE_ACTIVITY[guild_id])
        
        # Send completion message
        completion_embed = nova_embed(
            "✅ hISTORY sCAN cOMPLETE!",
            f"**Server:** {guild.name}\n"
            f"**Scanned Period:** {guild.created_at.strftime('%B %d, %Y')} - Today\n"
            f"**Total Messages:** {total_messages:,}\n"
            f"**Unique Users:** {unique_users:,}\n"
            f"**Channels Scanned:** {processed_channels}/{total_channels}\n\n"
            f"?mostactive now shows true lifetime stats!"
        )
        completion_embed.set_footer(text=f"Scan completed by {ctx.author}")
        await status_msg.edit(embed=completion_embed)
        
    except Exception as e:
        await status_msg.edit(embed=nova_embed(
            "❌ sCAN fAILED",
            f"An error occurred during the scan: {str(e)}\n\n"
            f"Progress: {processed_channels}/{total_channels} channels\n"
            f"Messages scanned: {total_messages:,}"
        ))
        print(f"Error in scanhistory command: {e}")
        import traceback
        traceback.print_exc()

# Helper function to log mod actions
async def log_mod_action(guild, action, moderator, target, reason=None, duration=None):
    """Log moderation actions to mod logs channel"""
    mod_logs_channel_id = get_server_config(guild.id, "mod_logs_channel_id")
    if not mod_logs_channel_id:
        return
    
    channel = guild.get_channel(mod_logs_channel_id)
    if not channel:
        return
    
    # Add to infractions system
    if target:
        add_infraction(target.id, action, reason or "No reason provided", str(moderator))
    
    # Create mod log embed
    embed = discord.Embed(
        title=f"🔨 {action.upper()}",
        color=0xff6b6b,
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Moderator", value=moderator.mention, inline=True)
    if target:
        embed.add_field(name="Target", value=f"{target.mention}\n`{target.id}`", inline=True)
    embed.add_field(name="Action", value=action.title(), inline=True)
    
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
    
    if target and target.avatar:
        embed.set_thumbnail(url=target.avatar.url)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to send mod log: {e}")

# =========================
# Enhanced Event Handlers for Logging
# =========================

# Join/Leave logging
@bot.event
async def on_member_join(member):
    # Existing welcome message code
    if WELCOME_CHANNEL_ID:
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            # Get member count and calculate member number
            member_count = member.guild.member_count
            member_number = member_count  # The new member is the latest count
            
            # Create welcome message with specific rules channel
            description = f"wELCOME tO tHE sERVER, {member.mention}! 💖\n\n"
            description += f"📋 pLEASE rEAD <#1390109532851535962> tO gET sTARTED!\n"
            description += f"🎉 yOU aRE oUR {member_number}th mEMBER!\n\n"
            description += "mAKE yOURSELF aT hOME!"
            
            embed = nova_embed("👋 wELCOME!", description)
            await channel.send(embed=embed)
    
    # New join logging
    if JOIN_LEAVE_LOGS_CHANNEL_ID:
        channel = member.guild.get_channel(JOIN_LEAVE_LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="📥 User Joined",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="User", value=f"{member.mention}\n{member.display_name}", inline=True)
            embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="Members", value=f"{member.guild.member_count}", inline=True)
            
            embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
            embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            
            embed.set_footer(text=f"Member #{member.guild.member_count}")
            
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send join log: {e}")

@bot.event
async def on_member_remove(member):
    # Existing farewell message code
    if FAREWELL_CHANNEL_ID:
        channel = member.guild.get_channel(FAREWELL_CHANNEL_ID)
        if channel:
            embed = nova_embed(
                "👋 gOODBYE!",
                f"{member.display_name} hAS lEFT tHE sERVER. pAYOLA."
            )
            await channel.send(embed=embed)
    
    # New leave logging
    if JOIN_LEAVE_LOGS_CHANNEL_ID:
        channel = member.guild.get_channel(JOIN_LEAVE_LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="📤 User Left",
                color=0xff0000,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="User", value=f"{member.mention}\n{member.display_name}", inline=True)
            embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="Members", value=f"{member.guild.member_count}", inline=True)
            
            if member.joined_at:
                embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
            
            # Get roles (excluding @everyone)
            roles = [role.mention for role in member.roles[1:]] if len(member.roles) > 1 else ["None"]
            if roles and roles != ["None"]:
                embed.add_field(name="Roles", value=", ".join(roles[:10]), inline=False)
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send leave log: {e}")

# Server/Member update logging
@bot.event
async def on_member_update(before, after):
    """Log member profile changes"""
    # Use server-specific server logs channel
    server_logs_channel_id = get_server_config(before.guild.id, "server_logs_channel_id")
    print(f"DEBUG: Member update event triggered for {after.display_name}")
    print(f"DEBUG: Server {before.guild.id} server logs channel ID: {server_logs_channel_id}")
    
    if not server_logs_channel_id:
        print("DEBUG: No server logs channel configured for this server")
        return
    
    try:
        channel = before.guild.get_channel(server_logs_channel_id)
        if not channel:
            print(f"DEBUG: Could not find channel with ID {SERVER_LOGS_CHANNEL_ID}")
            return
        
        print(f"DEBUG: Found channel {channel.name}")
        changes = []
        
        # Check for nickname changes (display_name includes nickname or username)
        print(f"DEBUG: Checking display name changes - Before: '{before.display_name}', After: '{after.display_name}'")
        print(f"DEBUG: Checking nick changes - Before: '{before.nick}', After: '{after.nick}'")
        if before.nick != after.nick:
            print("DEBUG: Nickname change detected!")
            before_nick = before.nick if before.nick else "None"
            after_nick = after.nick if after.nick else "None"
            changes.append(f"**Nickname:**\nBefore: `{before_nick}`\nAfter: `{after_nick}`")
        
        # Check for role changes
        if before.roles != after.roles:
            print("DEBUG: Role change detected!")
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)
            
            if added_roles:
                role_mentions = [role.mention for role in added_roles]
                changes.append(f"**Roles Added:** {', '.join(role_mentions)}")
            
            if removed_roles:
                role_mentions = [role.mention for role in removed_roles]
                changes.append(f"**Roles Removed:** {', '.join(role_mentions)}")
        
        # Check for avatar changes
        print(f"DEBUG: Checking avatar changes - Before: {before.avatar}, After: {after.avatar}")
        if before.avatar != after.avatar:
            print("DEBUG: Avatar change detected!")
            before_avatar = before.avatar.url if before.avatar else "None"
            after_avatar = after.avatar.url if after.avatar else "None"
            changes.append(f"**Avatar:**\nBefore: {before_avatar}\nAfter: {after_avatar}")
        
        if changes:
            print(f"DEBUG: Sending member update log with {len(changes)} changes")
            embed = discord.Embed(
                title="👤 Member Updated",
                color=0xffaa00,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="User", value=f"{after.mention}\n`{after.id}`", inline=True)
            embed.add_field(name="Changes", value="\n".join(changes), inline=False)
            
            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)
            
            await channel.send(embed=embed)
            print("DEBUG: Member update log sent successfully")
        else:
            print("DEBUG: No changes detected for member update")
            
    except Exception as e:
        print(f"ERROR in on_member_update: {e}")
        import traceback
        traceback.print_exc()

@bot.event
async def on_user_update(before, after):
    """Log user profile changes (username, discriminator, avatar)"""
    print(f"DEBUG: User update event triggered for {after.name}")
    print(f"DEBUG: SERVER_LOGS_CHANNEL_ID = {SERVER_LOGS_CHANNEL_ID}")
    
    if not SERVER_LOGS_CHANNEL_ID:
        print("DEBUG: No server logs channel configured")
        return
    
    try:
        # Find mutual guilds to log in
        for guild in bot.guilds:
            if guild.get_member(after.id):
                channel = guild.get_channel(SERVER_LOGS_CHANNEL_ID)
                if not channel:
                    print(f"DEBUG: Could not find channel with ID {SERVER_LOGS_CHANNEL_ID} in guild {guild.name}")
                    continue
                
                print(f"DEBUG: Found channel {channel.name} in guild {guild.name}")
                changes = []
                
                # Check for username changes
                print(f"DEBUG: Checking username changes - Before: '{before.name}', After: '{after.name}'")
                if before.name != after.name:
                    print("DEBUG: Username change detected!")
                    changes.append(f"**Username:**\nBefore: `{before.name}`\nAfter: `{after.name}`")
                
                # Check for discriminator changes (if applicable)
                if hasattr(before, 'discriminator') and hasattr(after, 'discriminator'):
                    print(f"DEBUG: Checking discriminator changes - Before: '{before.discriminator}', After: '{after.discriminator}'")
                    if before.discriminator != after.discriminator:
                        print("DEBUG: Discriminator change detected!")
                        changes.append(f"**Discriminator:**\nBefore: `#{before.discriminator}`\nAfter: `#{after.discriminator}`")
                
                # Check for avatar changes
                print(f"DEBUG: Checking user avatar changes - Before: {before.avatar}, After: {after.avatar}")
                if before.avatar != after.avatar:
                    print("DEBUG: User avatar change detected!")
                    before_avatar = before.avatar.url if before.avatar else "None"
                    after_avatar = after.avatar.url if after.avatar else "None"
                    changes.append(f"**Avatar:**\nBefore: {before_avatar}\nAfter: {after_avatar}")
                
                if changes:
                    print(f"DEBUG: Sending user update log with {len(changes)} changes")
                    embed = discord.Embed(
                        title="🔄 User Profile Updated",
                        color=0x00aaff,
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(name="User", value=f"{after.mention}\n`{after.id}`", inline=True)
                    embed.add_field(name="Changes", value="\n".join(changes), inline=False)
                    
                    if after.avatar:
                        embed.set_thumbnail(url=after.avatar.url)
                    
                    await channel.send(embed=embed)
                    print("DEBUG: User update log sent successfully")
                else:
                    print("DEBUG: No changes detected for user update")
                
                break  # Only log once per user update
                
    except Exception as e:
        print(f"ERROR in on_user_update: {e}")
        import traceback
        traceback.print_exc()

# Test event to see if guild events work at all
@bot.event
async def on_guild_role_create(role):
    print(f"DEBUG: Role created event fired: {role.name}")

@bot.event
async def on_guild_update(before, after):
    """Log server changes"""
    print(f"DEBUG: Guild update event triggered for {after.name}")
    print(f"DEBUG: SERVER_LOGS_CHANNEL_ID = {SERVER_LOGS_CHANNEL_ID}")
    
    if not SERVER_LOGS_CHANNEL_ID:
        print("DEBUG: No server logs channel configured")
        return
    
    try:
        channel = bot.get_channel(SERVER_LOGS_CHANNEL_ID)
        if not channel:
            print(f"DEBUG: Could not find channel with ID {SERVER_LOGS_CHANNEL_ID}")
            return
        
        print(f"DEBUG: Found channel {channel.name}")
        changes = []
        
        # Check for server name changes
        print(f"DEBUG: Checking name changes - Before: '{before.name}', After: '{after.name}'")
        if before.name != after.name:
            print("DEBUG: Server name change detected!")
            changes.append(f"**Server Name:**\nBefore: `{before.name}`\nAfter: `{after.name}`")
        
        # Check for icon changes
        print(f"DEBUG: Checking icon changes - Before: {before.icon}, After: {after.icon}")
        if before.icon != after.icon:
            print("DEBUG: Server icon change detected!")
            before_icon = before.icon.url if before.icon else "None"
            after_icon = after.icon.url if after.icon else "None"
            changes.append(f"**Server Icon:**\nBefore: {before_icon}\nAfter: {after_icon}")
        
        # Check for description changes
        print(f"DEBUG: Checking description changes - Before: '{before.description}', After: '{after.description}'")
        if before.description != after.description:
            print("DEBUG: Description change detected!")
            before_desc = before.description or "None"
            after_desc = after.description or "None"
            changes.append(f"**Description:**\nBefore: `{before_desc}`\nAfter: `{after_desc}`")
        
        if changes:
            print(f"DEBUG: Sending server update log with {len(changes)} changes")
            embed = discord.Embed(
                title="🏠 Server Updated",
                color=0xaa00ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Changes", value="\n".join(changes), inline=False)
            
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            
            await channel.send(embed=embed)
            print("DEBUG: Server update log sent successfully")
        else:
            print("DEBUG: No changes detected for server update")
            
    except Exception as e:
        print(f"ERROR in on_guild_update: {e}")
        import traceback
        traceback.print_exc()

# =========================
# New Moderation Commands
# =========================

# Unwarn command - Remove the most recent warning from a user
@bot.command()
async def unwarn(ctx, member: discord.Member = None):
    """Remove the most recent warning from a member (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNWARN", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if member is None:
        await ctx.send("Usage: ?unwarn @user - Removes the most recent warning from a member. Only mods/admins can use this.")
        return
    
    user_id = str(member.id)
    
    if user_id not in INFRACTIONS or not INFRACTIONS[user_id]:
        await ctx.send(embed=nova_embed("uNWARN", f"{member.mention} hAS nO wARNINGS tO rEMOVE!"))
        return
    
    # Find and remove the most recent warning
    warnings = [inf for inf in INFRACTIONS[user_id] if inf['type'].lower() == 'warn']
    
    if not warnings:
        await ctx.send(embed=nova_embed("uNWARN", f"{member.mention} hAS nO wARNINGS tO rEMOVE!"))
        return
    
    # Remove the most recent warning
    most_recent_warning = max(warnings, key=lambda x: x['date'])
    INFRACTIONS[user_id].remove(most_recent_warning)
    
    # Clean up empty infraction lists
    if not INFRACTIONS[user_id]:
        del INFRACTIONS[user_id]
    
    save_infractions()
    
    # Log to mod logs channel
    await log_mod_action(ctx.guild, "unwarn", ctx.author, member, f"Removed warning: {most_recent_warning['reason']}")
    
    embed = nova_embed(
        "uNWARN", 
        f"rEMOVED mOST rECENT wARNING fROM {member.mention}\n"
        f"rEASON wAS: {most_recent_warning['reason']}"
    )
    await ctx.send(embed=embed)

# Slash command version of unwarn
@bot.tree.command(name="unwarn", description="Remove the most recent warning from a member (mods only)")
@app_commands.describe(member="The member to remove a warning from")
async def unwarn_slash(interaction: discord.Interaction, member: discord.Member):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("uNWARN", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    user_id = str(member.id)
    
    if user_id not in INFRACTIONS or not INFRACTIONS[user_id]:
        await interaction.response.send_message(embed=nova_embed("uNWARN", f"{member.mention} hAS nO wARNINGS tO rEMOVE!"), ephemeral=True)
        return
    
    # Find and remove the most recent warning
    warnings = [inf for inf in INFRACTIONS[user_id] if inf['type'].lower() == 'warn']
    
    if not warnings:
        await interaction.response.send_message(embed=nova_embed("uNWARN", f"{member.mention} hAS nO wARNINGS tO rEMOVE!"), ephemeral=True)
        return
    
    # Remove the most recent warning
    most_recent_warning = max(warnings, key=lambda x: x['date'])
    INFRACTIONS[user_id].remove(most_recent_warning)
    
    # Clean up empty infraction lists
    if not INFRACTIONS[user_id]:
        del INFRACTIONS[user_id]
    
    save_infractions()
    
    # Log to mod logs channel
    await log_mod_action(interaction.guild, "unwarn", interaction.user, member, f"Removed warning: {most_recent_warning['reason']}")
    
    embed = nova_embed(
        "uNWARN", 
        f"rEMOVED mOST rECENT wARNING fROM {member.mention}\n"
        f"rEASON wAS: {most_recent_warning['reason']}"
    )
    await interaction.response.send_message(embed=embed)

# Unban command - Unban a user by ID
@bot.command()
async def unban(ctx, user_id: int = None, *, reason="No reason provided"):
    """Unban a user by their ID (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNBAN", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if user_id is None:
        await ctx.send("Usage: ?unban <user_id> [reason] - Unbans a user by their ID. Only mods/admins can use this.")
        return
    
    try:
        # Get the banned user
        banned_users = [entry async for entry in ctx.guild.bans(limit=2000)]
        banned_user = None
        
        for ban_entry in banned_users:
            if ban_entry.user.id == user_id:
                banned_user = ban_entry.user
                break
        
        if banned_user is None:
            await ctx.send(embed=nova_embed("uNBAN", f"uSER wITH iD {user_id} iS nOT bANNED!"))
            return
        
        # Unban the user
        await ctx.guild.unban(banned_user, reason=reason)
        
        # Log the case
        log_case(ctx.guild.id, "Unban", ctx.author, ctx.channel, datetime.now(dt_timezone.utc))
        # Log to mod logs channel
        await log_mod_action(ctx.guild, "unban", ctx.author, banned_user, reason)
        
        embed = nova_embed(
            "uNBAN", 
            f"uNBANNED {banned_user.mention} ({banned_user.name})\n"
            f"rEASON: {reason}"
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(embed=nova_embed("uNBAN", f"fAILED tO uNBAN: {e}"))

# Slash command version of unban
@bot.tree.command(name="unban", description="Unban a user by their ID (mods only)")
@app_commands.describe(user_id="The ID of the user to unban", reason="Reason for unbanning")
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("uNBAN", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    try:
        user_id_int = int(user_id)
        
        # Get the banned user
        banned_users = [entry async for entry in interaction.guild.bans(limit=2000)]
        banned_user = None
        
        for ban_entry in banned_users:
            if ban_entry.user.id == user_id_int:
                banned_user = ban_entry.user
                break
        
        if banned_user is None:
            await interaction.response.send_message(embed=nova_embed("uNBAN", f"uSER wITH iD {user_id} iS nOT bANNED!"), ephemeral=True)
            return
        
        # Unban the user
        await interaction.guild.unban(banned_user, reason=reason)
        
        # Log the case
        log_case(interaction.guild.id, "Unban", interaction.user, interaction.channel, datetime.now(dt_timezone.utc))
        # Log to mod logs channel
        await log_mod_action(interaction.guild, "unban", interaction.user, banned_user, reason)
        
        embed = nova_embed(
            "uNBAN", 
            f"uNBANNED {banned_user.mention} ({banned_user.name})\n"
            f"rEASON: {reason}"
        )
        await interaction.response.send_message(embed=embed)
        
    except ValueError:
        await interaction.response.send_message(embed=nova_embed("uNBAN", "iNVALID uSER iD!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(embed=nova_embed("uNBAN", f"fAILED tO uNBAN: {e}"), ephemeral=True)

# Clear case command - Clear all infractions for a user
@bot.command()
async def clearcase(ctx, member: discord.Member = None):
    """Clear all infractions for a member (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("cLEAR cASE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if member is None:
        await ctx.send("Usage: ?clearcase @user - Clears all infractions for a member. Only mods/admins can use this.")
        return
    
    user_id = str(member.id)
    
    if user_id not in INFRACTIONS or not INFRACTIONS[user_id]:
        await ctx.send(embed=nova_embed("cLEAR cASE", f"{member.mention} hAS nO iNFRACTIONS tO cLEAR!"))
        return
    
    # Count infractions before clearing
    infraction_count = len(INFRACTIONS[user_id])
    
    # Clear all infractions
    del INFRACTIONS[user_id]
    save_infractions()
    
    # Log the case clearing
    log_case(ctx.guild.id, "Clear Case", ctx.author, ctx.channel, datetime.now(dt_timezone.utc))
    # Log to mod logs channel
    await log_mod_action(ctx.guild, "clearcase", ctx.author, member, f"Cleared {infraction_count} infractions")
    
    embed = nova_embed(
        "cLEAR cASE", 
        f"cLEARED aLL {infraction_count} iNFRACTIONS fOR {member.mention}\n"
        f"tHEIR rECORD iS nOW cLEAN! ✨"
    )
    await ctx.send(embed=embed)

# Slash command version of clearcase
@bot.tree.command(name="clearcase", description="Clear all infractions for a member (mods only)")
@app_commands.describe(member="The member to clear infractions for")
async def clearcase_slash(interaction: discord.Interaction, member: discord.Member):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("cLEAR cASE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    user_id = str(member.id)
    
    if user_id not in INFRACTIONS or not INFRACTIONS[user_id]:
        await interaction.response.send_message(embed=nova_embed("cLEAR cASE", f"{member.mention} hAS nO iNFRACTIONS tO cLEAR!"), ephemeral=True)
        return
    
    # Count infractions before clearing
    infraction_count = len(INFRACTIONS[user_id])
    
    # Clear all infractions
    del INFRACTIONS[user_id]
    save_infractions()
    
    # Log the case clearing
    log_case(interaction.guild.id, "Clear Case", interaction.user, interaction.channel, datetime.now(dt_timezone.utc))
    # Log to mod logs channel
    await log_mod_action(interaction.guild, "clearcase", interaction.user, member, f"Cleared {infraction_count} infractions")
    
    embed = nova_embed(
        "cLEAR cASE", 
        f"cLEARED aLL {infraction_count} iNFRACTIONS fOR {member.mention}\n"
        f"tHEIR rECORD iS nOW cLEAN! ✨"
    )
    await interaction.response.send_message(embed=embed)

# Helper function for slash command permission checking
def has_mod_or_admin_interaction(interaction):
    """Check if the user has mod or admin privileges, is the bot owner, or is the server owner for slash commands"""
    # Check if user is the bot owner
    if interaction.user.id == OWNER_ID:
        return True
    # Check if user is the server owner
    if interaction.guild and interaction.user.id == interaction.guild.owner_id:
        return True
    # Check if user has administrator permissions
    if interaction.user.guild_permissions.administrator:
        return True
    # Check for specific mod/admin roles
    mod_role_id = config.get('mod_role_id')
    admin_role_id = config.get('admin_role_id')
    
    user_role_ids = [role.id for role in interaction.user.roles]
    
    return (mod_role_id and mod_role_id in user_role_ids) or (admin_role_id and admin_role_id in user_role_ids)

# =========================
# BCA (Brabz Choice Awards) System
# =========================

# Setup Commands
@bot.command()
async def setbcanominations(ctx, channel: discord.TextChannel = None):
    """Set the BCA nominations channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_NOMINATIONS_CHANNEL_ID
    if channel is None:
        BCA_NOMINATIONS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS", "bCA nOMINATIONS cHANNEL dISABLED!"))
    else:
        BCA_NOMINATIONS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS", f"bCA nOMINATIONS cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.command()
async def setbcanominationslogs(ctx, channel: discord.TextChannel = None):
    """Set the BCA nominations logs channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS lOGS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_NOMINATIONS_LOGS_CHANNEL_ID
    if channel is None:
        BCA_NOMINATIONS_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS lOGS", "bCA nOMINATIONS lOGS cHANNEL dISABLED!"))
    else:
        BCA_NOMINATIONS_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET bCA nOMINATIONS lOGS", f"bCA nOMINATIONS lOGS cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.command()
async def setbcavotinglogs(ctx, channel: discord.TextChannel = None):
    """Set the BCA voting logs channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET bCA vOTING lOGS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_VOTING_LOGS_CHANNEL_ID
    if channel is None:
        BCA_VOTING_LOGS_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET bCA vOTING lOGS", "bCA vOTING lOGS cHANNEL dISABLED!"))
    else:
        BCA_VOTING_LOGS_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET bCA vOTING lOGS", f"bCA vOTING lOGS cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.command()
async def setbcavoting(ctx, channel: discord.TextChannel = None):
    """Set the BCA voting channel (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET bCA vOTING", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_VOTING_CHANNEL_ID
    if channel is None:
        BCA_VOTING_CHANNEL_ID = None
        await ctx.send(embed=nova_embed("sET bCA vOTING", "bCA vOTING cHANNEL dISABLED!"))
    else:
        BCA_VOTING_CHANNEL_ID = channel.id
        await ctx.send(embed=nova_embed("sET bCA vOTING", f"bCA vOTING cHANNEL sET tO {channel.mention}!"))
    save_config()

# BCA Deadline Management
@bot.command()
async def setbcanomdeadline(ctx, *, end_time: str = None):
    """Set nomination deadline (mods only). Format: YYYY-MM-DD HH:MM"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET nOM dEADLINE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_NOMINATION_DEADLINE
    
    if end_time is None:
        BCA_NOMINATION_DEADLINE = None
        await ctx.send(embed=nova_embed("sET nOM dEADLINE", "nOMINATION dEADLINE rEMOVED!"))
    else:
        try:
            # Parse time as EST
            est = pytz.timezone('US/Eastern')
            naive_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            est_datetime = est.localize(naive_datetime)
            # Convert to UTC for storage
            utc_datetime = est_datetime.astimezone(pytz.UTC)
            BCA_NOMINATION_DEADLINE = utc_datetime
            
            # Show confirmation in EST
            await ctx.send(embed=nova_embed("sET nOM dEADLINE", f"nOMINATION dEADLINE sET tO:\n{est_datetime.strftime('%Y-%m-%d at %H:%M EST')}"))
        except ValueError:
            await ctx.send(embed=nova_embed("sET nOM dEADLINE", "iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM (EST)\n\nExample: 2024-12-31 23:59"))
            return
    
    # Reset announcement tracker when deadline changes
    reset_announcement_tracker()
    save_config()

@bot.command()
async def setbcavotedeadline(ctx, *, end_time: str = None):
    """Set voting deadline (mods only). Format: YYYY-MM-DD HH:MM"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("sET vOTE dEADLINE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_VOTING_DEADLINE
    
    if end_time is None:
        BCA_VOTING_DEADLINE = None
        await ctx.send(embed=nova_embed("sET vOTE dEADLINE", "vOTING dEADLINE rEMOVED!"))
    else:
        try:
            # Parse time as EST
            est = pytz.timezone('US/Eastern')
            naive_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            est_datetime = est.localize(naive_datetime)
            # Convert to UTC for storage
            utc_datetime = est_datetime.astimezone(pytz.UTC)
            BCA_VOTING_DEADLINE = utc_datetime
            
            # Show confirmation in EST
            await ctx.send(embed=nova_embed("sET vOTE dEADLINE", f"vOTING dEADLINE sET tO:\n{est_datetime.strftime('%Y-%m-%d at %H:%M EST')}"))
        except ValueError:
            await ctx.send(embed=nova_embed("sET vOTE dEADLINE", "iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM (EST)\n\nExample: 2024-12-31 23:59"))
            return
    
    # Reset announcement tracker when deadline changes
    reset_announcement_tracker()
    save_config()

@bot.command()
async def bcadeadlines(ctx):
    """Show current BCA deadlines"""
    embed = discord.Embed(
        title="⏰ bCA dEADLINES",
        color=0xff69b4,
        timestamp=datetime.now()
    )
    
    if BCA_NOMINATION_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        now_utc = datetime.now(pytz.UTC)
        deadline_est = BCA_NOMINATION_DEADLINE.astimezone(est)
        
        time_diff = BCA_NOMINATION_DEADLINE - now_utc
        if time_diff.total_seconds() <= 0:
            nom_status = "cLOSED"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            nom_status = f"{days}d {hours}h {minutes}m remaining"
        
        embed.add_field(
            name="📝 nOMINATIONS",
            value=f"**Deadline:** {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n**Status:** {nom_status}",
            inline=False
        )
    else:
        embed.add_field(name="📝 nOMINATIONS", value="nO dEADLINE sET", inline=False)
    
    if BCA_VOTING_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        now_utc = datetime.now(pytz.UTC)
        deadline_est = BCA_VOTING_DEADLINE.astimezone(est)
        
        time_diff = BCA_VOTING_DEADLINE - now_utc
        if time_diff.total_seconds() <= 0:
            vote_status = "cLOSED"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            vote_status = f"{days}d {hours}h {minutes}m remaining"
        
        embed.add_field(
            name="🗺️ vOTING",
            value=f"**Deadline:** {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n**Status:** {vote_status}",
            inline=False
        )
    else:
        embed.add_field(name="🗳️ vOTING", value="nO dEADLINE sET", inline=False)
    
    await ctx.send(embed=embed)

# Category Management
@bot.command()
async def bcaaddcategory(ctx, *, category_name: str = None):
    """Add a BCA category (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA aDD cATEGORY", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if category_name is None:
        await ctx.send(embed=nova_embed("bCA aDD cATEGORY", "Usage: ?bcaaddcategory <category name>"))
        return
    
    global BCA_CATEGORIES
    category_name = category_name.lower()
    
    if category_name in BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA aDD cATEGORY", f"cATEGORY '{category_name}' aLREADY eXISTS!"))
        return
    
    BCA_CATEGORIES[category_name] = {"allow_self_nomination": False}
    save_bca_categories(BCA_CATEGORIES)
    
    await ctx.send(embed=nova_embed("bCA aDD cATEGORY", f"aDDED cATEGORY: {category_name}\n\nsELF-nOMINATION: dISABLED"))

@bot.command()
async def bcatoggleself(ctx, *, category_name: str = None):
    """Toggle self-nomination for a BCA category (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA tOGGLE sELF", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if category_name is None:
        await ctx.send(embed=nova_embed("bCA tOGGLE sELF", "Usage: ?bcatoggleself <category name>"))
        return
    
    global BCA_CATEGORIES
    category_name = category_name.lower()
    
    if category_name not in BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA tOGGLE sELF", f"cATEGORY '{category_name}' dOESN'T eXIST!"))
        return
    
    BCA_CATEGORIES[category_name]["allow_self_nomination"] = not BCA_CATEGORIES[category_name]["allow_self_nomination"]
    save_bca_categories(BCA_CATEGORIES)
    
    status = "eNABLED" if BCA_CATEGORIES[category_name]["allow_self_nomination"] else "dISABLED"
    await ctx.send(embed=nova_embed("bCA tOGGLE sELF", f"sELF-nOMINATION fOR '{category_name}': {status}"))

@bot.command()
async def bcacategories(ctx):
    """List all BCA categories"""
    global BCA_CATEGORIES
    
    if not BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA cATEGORIES", "nO cATEGORIES sET uP yET!"))
        return
    
    category_list = []
    for category, settings in BCA_CATEGORIES.items():
        self_nom = "✅" if settings["allow_self_nomination"] else "❌"
        category_list.append(f"**{category.title()}** - Self-nomination: {self_nom}")
    
    embed = discord.Embed(
        title="🏆 bCA cATEGORIES",
        description="\n".join(category_list),
        color=0xff69b4
    )
    await ctx.send(embed=embed)

@bot.command()
async def removebcacategory(ctx, *, category_name: str = None):
    """Remove a BCA category (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA rEMOVE cATEGORY", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if category_name is None:
        await ctx.send(embed=nova_embed("bCA rEMOVE cATEGORY", "Usage: ?removebcacategory <category name>"))
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS, BCA_VOTES
    category_name = category_name.lower()
    
    if category_name not in BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA rEMOVE cATEGORY", f"cATEGORY '{category_name}' dOESN'T eXIST!"))
        return
    
    # Remove category from all data structures
    del BCA_CATEGORIES[category_name]
    if category_name in BCA_NOMINATIONS:
        del BCA_NOMINATIONS[category_name]
    if category_name in BCA_VOTES:
        del BCA_VOTES[category_name]
    
    # Save all changes
    save_bca_categories(BCA_CATEGORIES)
    save_bca_nominations(BCA_NOMINATIONS)
    save_bca_votes(BCA_VOTES)
    
    await ctx.send(embed=nova_embed("bCA rEMOVE cATEGORY", f"🗑️ rEMOVED cATEGORY: {category_name.title()}\n\naLL nOMINATIONS aND vOTES fOR tHIS cATEGORY hAVE bEEN dELETED!"))

@bot.command()
async def resetnominations(ctx, *, category: str = None):
    """Reset nominations for a category or all categories (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rESET nOMINATIONS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_NOMINATIONS
    
    if category is None:
        # Reset all nominations
        BCA_NOMINATIONS = {}
        save_bca_nominations(BCA_NOMINATIONS)
        await ctx.send(embed=nova_embed("rESET nOMINATIONS", "🗑️ aLL nOMINATIONS hAVE bEEN rESET!"))
    else:
        category = category.lower()
        if category not in BCA_CATEGORIES:
            await ctx.send(embed=nova_embed("rESET nOMINATIONS", f"cATEGORY '{category}' dOESN'T eXIST!"))
            return
        
        # Reset nominations for specific category
        if category in BCA_NOMINATIONS:
            del BCA_NOMINATIONS[category]
            save_bca_nominations(BCA_NOMINATIONS)
            await ctx.send(embed=nova_embed("rESET nOMINATIONS", f"🗑️ nOMINATIONS fOR '{category.title()}' hAVE bEEN rESET!"))
        else:
            await ctx.send(embed=nova_embed("rESET nOMINATIONS", f"nO nOMINATIONS fOUND fOR '{category.title()}'!"))

@bot.command()
async def resetvotes(ctx, *, category: str = None):
    """Reset votes for a category or all categories (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("rESET vOTES", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_VOTES
    
    if category is None:
        # Reset all votes
        BCA_VOTES = {}
        save_bca_votes(BCA_VOTES)
        await ctx.send(embed=nova_embed("rESET vOTES", "🗑️ aLL vOTES hAVE bEEN rESET!"))
    else:
        category = category.lower()
        if category not in BCA_CATEGORIES:
            await ctx.send(embed=nova_embed("rESET vOTES", f"cATEGORY '{category}' dOESN'T eXIST!"))
            return
        
        # Reset votes for specific category
        if category in BCA_VOTES:
            del BCA_VOTES[category]
            save_bca_votes(BCA_VOTES)
            await ctx.send(embed=nova_embed("rESET vOTES", f"🗑️ vOTES fOR '{category.title()}' hAVE bEEN rESET!"))
        else:
            await ctx.send(embed=nova_embed("rESET vOTES", f"nO vOTES fOUND fOR '{category.title()}'!"))

@bot.command()
async def bcanominations(ctx):
    """Show all current nominations across all categories (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA nOMINATIONS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    
    if not BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA nOMINATIONS", "nO cATEGORIES sET uP yET!"))
        return
    
    embed = discord.Embed(
        title="🏆 bCA nOMINATIONS oVERVIEW",
        color=0xff69b4
    )
    
    total_nominations = 0
    categories_with_noms = 0
    
    for category in BCA_CATEGORIES.keys():
        if category in BCA_NOMINATIONS and BCA_NOMINATIONS[category]:
            # Count nominations for this category
            nominee_counts = {}
            for nominator_id, nomination_data in BCA_NOMINATIONS[category].items():
                nominee_id = nomination_data['nominee']
                if nominee_id not in nominee_counts:
                    nominee_counts[nominee_id] = 0
                nominee_counts[nominee_id] += 1
            
            # Sort by nomination count (descending)
            sorted_nominees = sorted(nominee_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Build category text
            category_text = []
            for nominee_id, count in sorted_nominees:
                member = ctx.guild.get_member(int(nominee_id))
                if member:
                    plural = "person" if count == 1 else "people"
                    category_text.append(f"• {member.mention} (nominated by {count} {plural})")
            
            if category_text:
                nom_count = len(BCA_NOMINATIONS[category])
                embed.add_field(
                    name=f"📝 {category.title()} ({nom_count} nominations)",
                    value="\n".join(category_text),
                    inline=False
                )
                total_nominations += nom_count
                categories_with_noms += 1
        else:
            # No nominations for this category
            embed.add_field(
                name=f"📝 {category.title()} (0 nominations)",
                value="• nO nOMINATIONS yET",
                inline=False
            )
    
    # Add summary footer
    if total_nominations > 0:
        embed.set_footer(text=f"tOTAL: {total_nominations} nominations across {categories_with_noms}/{len(BCA_CATEGORIES)} categories")
    else:
        embed.set_footer(text="nO nOMINATIONS yET")
    
    await ctx.send(embed=embed)

# Nomination System
@bot.command()
async def nominate(ctx, nominee: discord.Member = None, *, category: str = None):
    """Nominate someone for a BCA category"""
    # Delete the original message for privacy (even on errors)
    try:
        await ctx.message.delete()
    except discord.errors.NotFound:
        pass  # Message already deleted
    except discord.errors.Forbidden:
        pass  # No permission to delete
    
    if nominee is None or category is None:
        try:
            await ctx.author.send(embed=nova_embed("nOMINATE", "Usage: ?nominate @user <category name>\n\nExample: ?nominate @username Best Memer"))
        except discord.errors.Forbidden:
            await ctx.send(embed=nova_embed("nOMINATE", "Usage: ?nominate @user <category name>"), delete_after=10)
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    category = category.lower()
    
    # Check if nominations are still open
    if BCA_NOMINATION_DEADLINE and datetime.now(pytz.UTC) > BCA_NOMINATION_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        deadline_est = BCA_NOMINATION_DEADLINE.astimezone(est)
        try:
            await ctx.author.send(embed=nova_embed("nOMINATE", f"nOMINATIONS fOR '{category}' hAVE cLOSED!\n\nDeadline was: {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}"))
        except discord.errors.Forbidden:
            await ctx.send(embed=nova_embed("nOMINATE", f"nOMINATIONS fOR '{category}' hAVE cLOSED!"), delete_after=10)
        return
    
    # Check if category exists
    if category not in BCA_CATEGORIES:
        try:
            await ctx.author.send(embed=nova_embed("nOMINATE", f"cATEGORY '{category}' dOESN'T eXIST!\n\nUse ?bcacategories to see available categories."))
        except discord.errors.Forbidden:
            await ctx.send(embed=nova_embed("nOMINATE", f"cATEGORY '{category}' dOESN'T eXIST!"), delete_after=10)
        return
    
    # Check self-nomination rules
    if nominee == ctx.author and not BCA_CATEGORIES[category]["allow_self_nomination"]:
        try:
            await ctx.author.send(embed=nova_embed("nOMINATE", f"sELF-nOMINATION iS nOT aLLOWED fOR '{category}'!"))
        except discord.errors.Forbidden:
            await ctx.send(embed=nova_embed("nOMINATE", f"sELF-nOMINATION iS nOT aLLOWED fOR '{category}'!"), delete_after=10)
        return
    
    # Check if user already nominated in this category
    if category not in BCA_NOMINATIONS:
        BCA_NOMINATIONS[category] = {}
    
    # Check if user already nominated in this category - allow changes during deadline
    is_changing_nomination = str(ctx.author.id) in BCA_NOMINATIONS[category]
    if is_changing_nomination:
        current_nominee = BCA_NOMINATIONS[category][str(ctx.author.id)]["nominee"]
        current_member = ctx.guild.get_member(int(current_nominee))
        
        # If nominating the same person, just confirm
        if str(nominee.id) == current_nominee:
            try:
                await ctx.author.send(embed=nova_embed("nOMINATION cONFIRMED", f"yOU aLREADY nOMINATED {nominee.mention} fOR '{category.title()}'!\n\n🎆 yOUR nOMINATION sTANDS!"))
            except discord.errors.Forbidden:
                await ctx.send(embed=nova_embed("nOMINATION cONFIRMED", f"yOU aLREADY nOMINATED {nominee.mention} fOR '{category.title()}'!"), delete_after=10)
            return
    
    # Add nomination
    BCA_NOMINATIONS[category][str(ctx.author.id)] = {
        "nominee": str(nominee.id),
        "nominator": str(ctx.author.id)
    }
    save_bca_nominations(BCA_NOMINATIONS)
    
    # Send private confirmation to nominator via DM
    if is_changing_nomination:
        confirmation_title = "nOMINATION cHANGED"
        confirmation_msg = f"yOU cHANGED yOUR nOMINATION tO {nominee.mention} fOR '{category.title()}'!\n\n🔄 aNONYMOUS nOMINATION uPDATED!\n\n💡 You can change again during the deadline period."
    else:
        confirmation_title = "nOMINATION sUBMITTED"
        confirmation_msg = f"yOU nOMINATED {nominee.mention} fOR '{category.title()}'!\n\n🎆 aNONYMOUS nOMINATION sUBMITTED!\n\n💡 You can change your nomination during the deadline period."
    
    try:
        await ctx.author.send(embed=nova_embed(confirmation_title, confirmation_msg))
    except discord.errors.Forbidden:
        # Fallback to ephemeral message if DMs are disabled
        await ctx.send(embed=nova_embed(confirmation_title, confirmation_msg.replace(nominee.mention, nominee.display_name)), delete_after=10)
    
    # Log to nominations logs channel (mods can see who nominated who)
    if BCA_NOMINATIONS_LOGS_CHANNEL_ID:
        logs_channel = ctx.guild.get_channel(BCA_NOMINATIONS_LOGS_CHANNEL_ID)
        if logs_channel:
            embed = discord.Embed(
                title="🏆 bCA nOMINATION lOG",
                color=0xff69b4,
                timestamp=datetime.now()
            )
            embed.add_field(name="Nominator", value=f"{ctx.author.mention}\n`{ctx.author.id}`", inline=True)
            embed.add_field(name="Nominee", value=f"{nominee.mention}\n`{nominee.id}`", inline=True)
            embed.add_field(name="Category", value=category.title(), inline=True)
            embed.set_thumbnail(url=nominee.display_avatar.url)
            
            try:
                await logs_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send nomination log: {e}")
    
    # Ping nominee in nominations channel
    if BCA_NOMINATIONS_CHANNEL_ID:
        nominations_channel = ctx.guild.get_channel(BCA_NOMINATIONS_CHANNEL_ID)
        if nominations_channel:
            embed = discord.Embed(
                title="🎆 nEW nOMINATION!",
                description=f"{nominee.mention} hAS bEEN nOMINATED fOR **{category.title()}**!",
                color=0xff69b4
            )
            embed.set_thumbnail(url=nominee.display_avatar.url)
            
            try:
                await nominations_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send nomination ping: {e}")

@bot.tree.command(name="nominate", description="Nominate someone for a BCA category (anonymous)")
@app_commands.describe(nominee="The person to nominate", category="The BCA category")
async def nominate_slash(interaction: discord.Interaction, nominee: discord.Member, category: str):
    """Nominate someone for a BCA category (slash command version)"""
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    category = category.lower()
    
    # Check if nominations are still open
    if BCA_NOMINATION_DEADLINE and datetime.now(pytz.UTC) > BCA_NOMINATION_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        deadline_est = BCA_NOMINATION_DEADLINE.astimezone(est)
        await interaction.response.send_message(embed=nova_embed("nOMINATE", f"nOMINATIONS fOR '{category}' hAVE cLOSED!\n\nDeadline was: {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}"), ephemeral=True)
        return
    
    # Check if category exists
    if category not in BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("nOMINATE", f"cATEGORY '{category}' dOESN'T eXIST!\n\nUse /bcacategories to see available categories."), ephemeral=True)
        return
    
    # Check self-nomination rules
    if nominee == interaction.user and not BCA_CATEGORIES[category]["allow_self_nomination"]:
        await interaction.response.send_message(embed=nova_embed("nOMINATE", f"sELF-nOMINATION iS nOT aLLOWED fOR '{category}'!"), ephemeral=True)
        return
    
    # Check if user already nominated in this category
    if category not in BCA_NOMINATIONS:
        BCA_NOMINATIONS[category] = {}
    
    # Check if user already nominated in this category - allow changes during deadline
    is_changing_nomination = str(interaction.user.id) in BCA_NOMINATIONS[category]
    if is_changing_nomination:
        current_nominee = BCA_NOMINATIONS[category][str(interaction.user.id)]["nominee"]
        
        # If nominating the same person, just confirm
        if str(nominee.id) == current_nominee:
            await interaction.response.send_message(embed=nova_embed("nOMINATION cONFIRMED", f"yOU aLREADY nOMINATED {nominee.mention} fOR '{category.title()}'!\n\n🎆 yOUR nOMINATION sTANDS!"), ephemeral=True)
            return
    
    # Add nomination
    BCA_NOMINATIONS[category][str(interaction.user.id)] = {
        "nominee": str(nominee.id),
        "nominator": str(interaction.user.id)
    }
    save_bca_nominations(BCA_NOMINATIONS)
    
    # Send private confirmation to nominator
    if is_changing_nomination:
        confirmation_title = "nOMINATION cHANGED"
        confirmation_msg = f"yOU cHANGED yOUR nOMINATION tO {nominee.mention} fOR '{category.title()}'!\n\n🔄 aNONYMOUS nOMINATION uPDATED!\n\n💡 You can change again during the deadline period."
    else:
        confirmation_title = "nOMINATION sUBMITTED"
        confirmation_msg = f"yOU nOMINATED {nominee.mention} fOR '{category.title()}'!\n\n🎆 aNONYMOUS nOMINATION sUBMITTED!\n\n💡 You can change your nomination during the deadline period."
    
    await interaction.response.send_message(embed=nova_embed(confirmation_title, confirmation_msg), ephemeral=True)
    
    # Ping nominee in public nominations channel
    if BCA_NOMINATIONS_CHANNEL_ID:
        nominations_channel = interaction.guild.get_channel(BCA_NOMINATIONS_CHANNEL_ID)
        if nominations_channel:
            embed = discord.Embed(
                title="🎆 nEW nOMINATION!",
                description=f"{nominee.mention} hAS bEEN nOMINATED fOR **{category.title()}**!",
                color=0xff69b4
            )
            embed.set_thumbnail(url=nominee.display_avatar.url)
            
            try:
                await nominations_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send nomination ping: {e}")
    
    # Log to nominations logs channel (mods can see who nominated who)
    if BCA_NOMINATIONS_LOGS_CHANNEL_ID:
        logs_channel = interaction.guild.get_channel(BCA_NOMINATIONS_LOGS_CHANNEL_ID)
        if logs_channel:
            embed = discord.Embed(
                title="🏆 bCA nOMINATION lOG",
                color=0xff69b4,
                timestamp=datetime.now()
            )
            embed.add_field(name="Nominator", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=True)
            embed.add_field(name="Nominee", value=f"{nominee.mention}\n`{nominee.id}`", inline=True)
            embed.add_field(name="Category", value=f"'{category.title()}'", inline=True)
            
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            await logs_channel.send(embed=embed)





# Voting System
class VotingView(View):
    def __init__(self, category, nominees):
        super().__init__(timeout=300)  # 5 minute timeout
        self.category = category
        self.nominees = nominees
        
        # Add buttons for each nominee
        for i, (nominee_id, nominee_name) in enumerate(nominees):
            button = Button(
                label=nominee_name[:80],  # Discord button label limit
                style=discord.ButtonStyle.primary,
                custom_id=f"vote_{category}_{nominee_id}"
            )
            button.callback = self.vote_callback
            self.add_item(button)
    
    async def vote_callback(self, interaction):
        custom_id = interaction.data['custom_id']
        _, category, nominee_id = custom_id.split('_', 2)
        
        global BCA_VOTES
        
        # Check if user already voted in this category
        if category not in BCA_VOTES:
            BCA_VOTES[category] = {}
        
        if str(interaction.user.id) in BCA_VOTES[category]:
            await interaction.response.send_message(embed=nova_embed("vOTE", f"yOU aLREADY vOTED iN '{category}'!\n\nOnly 1 vote per category per member."), ephemeral=True)
            return
        
        # Add vote
        BCA_VOTES[category][str(interaction.user.id)] = nominee_id
        save_bca_votes(BCA_VOTES)
        
        nominee = interaction.guild.get_member(int(nominee_id))
        nominee_name = nominee.display_name if nominee else "Unknown User"
        
        await interaction.response.send_message(embed=nova_embed("vOTE cAST", f"yOU vOTED fOR {nominee_name} iN '{category.title()}'!\n\n🗳️ aNONYMOUS vOTE cAST!"), ephemeral=True)
        
        # Log to voting logs channel (mods can see who voted for who)
        if BCA_VOTING_LOGS_CHANNEL_ID:
            logs_channel = interaction.guild.get_channel(BCA_VOTING_LOGS_CHANNEL_ID)
            if logs_channel:
                embed = discord.Embed(
                    title="🗳️ bCA vOTE lOG",
                    color=0xff69b4,
                    timestamp=datetime.now()
                )
                embed.add_field(name="Voter", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=True)
                embed.add_field(name="Vote For", value=f"{nominee.mention if nominee else 'Unknown'}\n`{nominee_id}`", inline=True)
                embed.add_field(name="Category", value=category.title(), inline=True)
                
                try:
                    await logs_channel.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send voting log: {e}")

@bot.command()
async def bcavote(ctx, *, category: str = None):
    """Start a voting session for a BCA category (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA vOTE", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not BCA_VOTING_CHANNEL_ID:
        await ctx.send(embed=nova_embed("bCA vOTE", "nO vOTING cHANNEL sET! uSE ?setbcavoting #channel fIRST!"))
        return
    
    if category is None:
        await ctx.send(embed=nova_embed("bCA vOTE", "Usage: ?bcavote <category name>"))
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    category = category.lower()
    
    if category not in BCA_CATEGORIES:
        await ctx.send(embed=nova_embed("bCA vOTE", f"cATEGORY '{category}' dOESN'T eXIST!"))
        return
    
    if category not in BCA_NOMINATIONS or not BCA_NOMINATIONS[category]:
        await ctx.send(embed=nova_embed("bCA vOTE", f"nO nOMINATIONS fOR '{category}' yET!"))
        return
    
    # Get unique nominees
    nominees = set()
    for nomination_data in BCA_NOMINATIONS[category].values():
        nominees.add(nomination_data["nominee"])
    
    # Convert to list of (id, name) tuples
    nominee_list = []
    for nominee_id in nominees:
        member = ctx.guild.get_member(int(nominee_id))
        if member:
            nominee_list.append((nominee_id, member.display_name))
    
    if not nominee_list:
        await ctx.send(embed=nova_embed("bCA vOTE", f"nO vALID nOMINEES fOR '{category}'!"))
        return
    
    if len(nominee_list) > 25:  # Discord button limit
        await ctx.send(embed=nova_embed("bCA vOTE", f"tOO mANY nOMINEES ({len(nominee_list)})! mAXIMUM 25 aLLOWED."))
        return
    
    # Create voting embed
    embed = discord.Embed(
        title=f"🗳️ vOTE fOR {category.title()}",
        description=f"cLICK a bUTTON tO vOTE fOR yOUR fAVORITE iN '{category.title()}'!\n\n🔒 vOTING iS aNONYMOUS\n⚠️ oNLY 1 vOTE pER pERSON",
        color=0xff69b4
    )
    
    nominees_text = "\n".join([f"• {name}" for _, name in nominee_list])
    embed.add_field(name="nOMINEES", value=nominees_text, inline=False)
    
    # Get the voting channel
    voting_channel = ctx.guild.get_channel(BCA_VOTING_CHANNEL_ID)
    if not voting_channel:
        await ctx.send(embed=nova_embed("bCA vOTE", f"vOTING cHANNEL nOT fOUND! pLEASE rESET wITH ?setbcavoting #channel"))
        return
    
    view = VotingView(category, nominee_list)
    await voting_channel.send(embed=embed, view=view)
    
    # Confirm to mod in current channel
    await ctx.send(embed=nova_embed("bCA vOTE", f"vOTING sESSION fOR '{category.title()}' sTARTED iN {voting_channel.mention}!"))

@bot.tree.command(name="bcavote", description="Start a voting session for a BCA category (mods only)")
@app_commands.describe(category="Name of the BCA category to start voting for")
async def bcavote_slash(interaction: discord.Interaction, category: str):
    """Start a voting session for a BCA category (slash command version)"""
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    if not BCA_VOTING_CHANNEL_ID:
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", "nO vOTING cHANNEL sET! uSE /setbcavoting #channel fIRST!"), ephemeral=True)
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    category = category.lower()
    
    if category not in BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"cATEGORY '{category}' dOESN'T eXIST!"), ephemeral=True)
        return
    
    if category not in BCA_NOMINATIONS or not BCA_NOMINATIONS[category]:
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"nO nOMINATIONS fOR '{category}' yET!"), ephemeral=True)
        return
    
    # Get unique nominees
    nominees = set()
    for nomination_data in BCA_NOMINATIONS[category].values():
        nominees.add(nomination_data["nominee"])
    
    # Convert to list of (id, name) tuples
    nominee_list = []
    for nominee_id in nominees:
        member = interaction.guild.get_member(int(nominee_id))
        if member:
            nominee_list.append((nominee_id, member.display_name))
    
    if not nominee_list:
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"nO vALID nOMINEES fOR '{category}'!"), ephemeral=True)
        return
    
    if len(nominee_list) > 25:  # Discord button limit
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"tOO mANY nOMINEES ({len(nominee_list)})! mAXIMUM 25 aLLOWED."), ephemeral=True)
        return
    
    # Create voting embed
    embed = discord.Embed(
        title=f"🗳️ vOTE fOR {category.title()}",
        description=f"cLICK a bUTTON tO vOTE fOR yOUR fAVORITE iN '{category.title()}'!\n\n🔒 vOTING iS aNONYMOUS\n⚠️ oNLY 1 vOTE pER pERSON",
        color=0xff69b4
    )
    
    nominees_text = "\n".join([f"• {name}" for _, name in nominee_list])
    embed.add_field(name="nOMINEES", value=nominees_text, inline=False)
    
    # Get the voting channel
    voting_channel = interaction.guild.get_channel(BCA_VOTING_CHANNEL_ID)
    if not voting_channel:
        await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"vOTING cHANNEL nOT fOUND! pLEASE rESET wITH /setbcavoting #channel"), ephemeral=True)
        return
    
    view = VotingView(category, nominee_list)
    await voting_channel.send(embed=embed, view=view)
    
    # Confirm to mod in current channel
    await interaction.response.send_message(embed=nova_embed("bCA vOTE", f"vOTING sESSION fOR '{category.title()}' sTARTED iN {voting_channel.mention}!"), ephemeral=True)

# Countdown System
@bot.command()
async def addcountdown(ctx, event_name: str = None, date: str = None, time: str = None, *, description: str = None):
    """Add a countdown for an event (mods only). Format: ?addcountdown "Event Name" "YYYY-MM-DD" "HH:MM" "Description"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("aDD cOUNTDOWN", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if not event_name or not date:
        await ctx.send(embed=nova_embed("aDD cOUNTDOWN", 'Usage: ?addcountdown "Event Name" "YYYY-MM-DD" "HH:MM" "Description"\n\nSupported formats:\n• Date: "YYYY-MM-DD" (e.g., "2025-08-05")\n• Time: "HH:MM" (e.g., "22:04") - Optional, defaults to "00:00"\n• Description: Any text in quotes - Optional\n\nExamples:\n• ?addcountdown "BCA Voting" "2024-12-31" "23:59" "Voting ends soon!"\n• ?addcountdown "Event Name" "2025-08-05" "22:04" "With time and description"\n• ?addcountdown "Simple Event" "2025-08-04" "00:00" "Midnight event"'))
        return
    
    # Set default time if not provided
    if not time:
        time = "00:00"
        print(f"DEBUG: No time provided, defaulting to: {time}")
    
    # Combine date and time
    end_time = f"{date} {time}"
    print(f"DEBUG: Combined datetime string: '{end_time}'")
    
    # If description is None, use a default
    if description is None:
        description = "No description provided"
    
    try:
        print(f"DEBUG: Adding countdown - Event: '{event_name}', Time: '{end_time}', Description: '{description}'")
        
        # Parse the datetime and assume it's in EST
        est = pytz.timezone('US/Eastern')
        print(f"DEBUG: Attempting to parse time: '{end_time}'")
        
        # Clean the input and try multiple date formats - order matters! Try most specific first
        end_time = end_time.strip()  # Remove any leading/trailing whitespace
        end_datetime = None
        
        # Try to parse with time first
        if ' ' in end_time and ':' in end_time:
            # Has both space and colon, try time formats
            try:
                end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
                print(f"DEBUG: Successfully parsed with time format: {end_datetime}")
            except ValueError:
                pass
        
        # If time parsing failed, try other formats
        if end_datetime is None:
            formats_to_try = [
                "%Y-%m-%d %H%M",     # Full date and time without colon (2025-08-05 2204)
                "%Y-%m-%d %H.%M",    # Full date and time with dot (2025-08-05 22.04)
                "%Y-%m-%d",          # Date only (will default to midnight)
            ]
            
            for fmt in formats_to_try:
                try:
                    print(f"DEBUG: Trying format '{fmt}' with input '{end_time}'")
                    end_datetime = datetime.strptime(end_time, fmt)
                    print(f"DEBUG: Successfully parsed with format '{fmt}': {end_datetime}")
                    break
                except ValueError as fmt_error:
                    print(f"DEBUG: Format '{fmt}' failed: {fmt_error}")
                    continue
        
        if end_datetime:
            print(f"DEBUG: Final parsed datetime - Year: {end_datetime.year}, Month: {end_datetime.month}, Day: {end_datetime.day}, Hour: {end_datetime.hour}, Minute: {end_datetime.minute}")
        
        if end_datetime is None:
            raise ValueError(f"Could not parse '{end_time}' with any supported format")
        
        # Localize to EST timezone
        end_datetime = est.localize(end_datetime)
        print(f"DEBUG: Localized datetime (EST): {end_datetime}")
        print(f"DEBUG: Localized datetime hour: {end_datetime.hour}, minute: {end_datetime.minute}")
        
        # Test the strftime that will be used in footer
        test_footer = end_datetime.strftime('%Y-%m-%d at %H:%M EST')
        print(f"DEBUG: Test footer format: {test_footer}")
        
        global BCA_COUNTDOWNS
        guild_id = ctx.guild.id
        
        # Initialize guild countdowns if not exists
        if guild_id not in BCA_COUNTDOWNS:
            BCA_COUNTDOWNS[guild_id] = {}
            
        BCA_COUNTDOWNS[guild_id][event_name] = {
            "end_time": end_datetime,
            "description": description or "No description provided"
        }
        
        print(f"DEBUG: Saving countdown data for guild {guild_id}: {BCA_COUNTDOWNS[guild_id]}")
        try:
            save_bca_countdowns(BCA_COUNTDOWNS)
            print("DEBUG: Countdown saved successfully")
        except Exception as save_error:
            print(f"DEBUG: Error saving countdown: {save_error}")
            raise save_error
        
        # Calculate time remaining
        now = datetime.now(est)  # Get current time in EST
        print(f"DEBUG: Current EST time: {now}")
        print(f"DEBUG: Target EST time: {end_datetime}")
        print(f"DEBUG: Current EST timezone: {now.tzinfo}")
        print(f"DEBUG: Target EST timezone: {end_datetime.tzinfo}")
        
        time_diff = end_datetime - now
        print(f"DEBUG: Time difference: {time_diff}")
        print(f"DEBUG: Time difference in seconds: {time_diff.total_seconds()}")
        
        if time_diff.total_seconds() <= 0:
            time_str = "eVENT hAS pASSED!"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{days}d {hours}h {minutes}m"
        
        # Add verification info to help debug
        parsed_info = f"Parsed: {end_datetime.hour:02d}:{end_datetime.minute:02d} EST"
        
        embed = discord.Embed(
            title="⏰ cOUNTDOWN aDDED",
            description=f"**{event_name}**\n{description}\n\n⏱️ tIME rEMAINING: {time_str}\n\n🔍 {parsed_info}",
            color=0xff69b4
        )
        print(f"DEBUG: About to create footer with end_datetime: {end_datetime}")
        print(f"DEBUG: end_datetime hour: {end_datetime.hour}, minute: {end_datetime.minute}")
        footer_text = f"eNDS: {end_datetime.strftime('%Y-%m-%d at %H:%M EST')}"
        print(f"DEBUG: Footer text will be: {footer_text}")
        embed.set_footer(text=footer_text)
        await ctx.send(embed=embed)
        
    except ValueError as e:
        print(f"DEBUG: ValueError in addcountdown: {e}")
        await ctx.send(embed=nova_embed("aDD cOUNTDOWN", f"iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM\n\nExample: 2024-12-31 23:59\n\nYour input: '{end_time}'\nError: {str(e)}"))
    except Exception as e:
        print(f"DEBUG: Unexpected error in addcountdown: {e}")
        await ctx.send(embed=nova_embed("aDD cOUNTDOWN", f"aN uNEXPECTED eRROR oCCURRED: {str(e)}"))

@bot.command(name="countdown")
async def countdown(ctx, *, event_name: str = None):
    """Show countdown for an event"""
    global BCA_COUNTDOWNS
    guild_id = ctx.guild.id
    
    print(f"DEBUG: Countdown command called with event_name: {event_name} for guild {guild_id}")
    print(f"DEBUG: Current BCA_COUNTDOWNS: {BCA_COUNTDOWNS}")
    
    # Get countdowns for this server
    server_countdowns = BCA_COUNTDOWNS.get(guild_id, {})
    
    if not server_countdowns:
        await ctx.send(embed=nova_embed("cOUNTDOWN", "nO cOUNTDOWNS sET uP yET fOR tHIS sERVER!"))
        return
    
    try:
        if event_name is None:
            # Show all countdowns for this server
            countdown_list = []
            for event, data in server_countdowns.items():
                est = pytz.timezone('US/Eastern')
                now = datetime.now(est)
                time_diff = data["end_time"] - now
                
                if time_diff.total_seconds() <= 0:
                    time_str = "eNDED"
                else:
                    days = time_diff.days
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    # Live countdown with seconds
                    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
                
                countdown_list.append(f"**{event}** - {time_str}")
            
            embed = discord.Embed(
                title="⏰ aLL cOUNTDOWNS (lIVE)",
                description="\n".join(countdown_list),
                color=0xff69b4
            )
            embed.set_footer(text="🔴 lIVE cOUNTDOWN - rEFRESH fOR uPDATES")
            await ctx.send(embed=embed)
        else:
            # Show specific countdown
            if event_name not in server_countdowns:
                available_events = list(server_countdowns.keys())
                await ctx.send(embed=nova_embed("cOUNTDOWN", f"eVENT '{event_name}' nOT fOUND!\n\naVAILABLE eVENTS: {', '.join(available_events) if available_events else 'None'}"))
                return
        
        event_data = server_countdowns[event_name]
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        time_diff = event_data["end_time"] - now
        
        if time_diff.total_seconds() <= 0:
            time_str = "eVENT hAS eNDED!"
            color = 0x808080  # Gray for ended events
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
            color = 0xff69b4
        
        description = f"{event_data['description']}\n\n⏱️ **tIME rEMAINING:** **{time_str}**"
        message = await ctx.send(embed=nova_embed(f"⏰ {event_name}", description))
        
        # Track this message for live updates (only for specific countdowns, not "all" view)
        if time_diff.total_seconds() > 0:  # Only track if not ended
            global active_countdown_messages
            active_countdown_messages[message.id] = {
                'guild_id': guild_id,
                'channel_id': ctx.channel.id,
                'event_name': event_name,
                'message_obj': message
            }
            
    except Exception as e:
        print(f"ERROR in countdown command: {e}")
        await ctx.send(embed=nova_embed("cOUNTDOWN", "aN eRROR oCCURRED wHILE sHOWING cOUNTDOWN!"))

@bot.tree.command(name="countdown", description="Show countdown for an event")
@app_commands.describe(event_name="Name of the event to show countdown for (leave empty to show all)")
async def countdown_slash(interaction: discord.Interaction, event_name: str = None):
    """Show countdown for an event (slash command version)"""
    global BCA_COUNTDOWNS
    guild_id = interaction.guild.id
    
    print(f"DEBUG: Countdown slash command called with event_name: {event_name} for guild {guild_id}")
    print(f"DEBUG: Current BCA_COUNTDOWNS: {BCA_COUNTDOWNS}")
    
    # Get countdowns for this server
    server_countdowns = BCA_COUNTDOWNS.get(guild_id, {})
    
    if not server_countdowns:
        await interaction.response.send_message(embed=nova_embed("cOUNTDOWN", "nO cOUNTDOWNS sET uP yET fOR tHIS sERVER!"))
        return
    
    try:
        if event_name is None:
            # Show all countdowns for this server
            countdown_list = []
            for event, data in server_countdowns.items():
                est = pytz.timezone('US/Eastern')
                now = datetime.now(est)
                time_diff = data["end_time"] - now
                
                if time_diff.total_seconds() <= 0:
                    time_str = "eNDED"
                else:
                    days = time_diff.days
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    # Live countdown with seconds
                    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
                
                countdown_list.append(f"**{event}** - {time_str}")
            
            embed = discord.Embed(
                title="⏰ aLL cOUNTDOWNS (lIVE)",
                description="\n".join(countdown_list),
                color=0xff69b4
            )
            embed.set_footer(text="🔴 lIVE cOUNTDOWN - rEFRESH fOR uPDATES")
            await interaction.response.send_message(embed=embed)
        else:
            # Show specific countdown
            if event_name not in server_countdowns:
                available_events = list(server_countdowns.keys())
                await interaction.response.send_message(embed=nova_embed("cOUNTDOWN", f"eVENT '{event_name}' nOT fOUND!\n\naVAILABLE eVENTS: {', '.join(available_events) if available_events else 'None'}"))
                return
        
            event_data = server_countdowns[event_name]
            est = pytz.timezone('US/Eastern')
            now = datetime.now(est)
            time_diff = event_data["end_time"] - now
            
            if time_diff.total_seconds() <= 0:
                time_str = "eVENT hAS eNDED!"
                color = 0x808080  # Gray for ended events
            else:
                days = time_diff.days
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
                color = 0xff69b4
            
            description = f"{event_data['description']}\n\n⏱️ **tIME rEMAINING:** **{time_str}**"
            await interaction.response.send_message(embed=nova_embed(f"⏰ {event_name}", description))
            
            # Track this message for live updates (only for specific countdowns, not "all" view)
            if time_diff.total_seconds() > 0:  # Only track if not ended
                message = await interaction.original_response()
                global active_countdown_messages
                active_countdown_messages[message.id] = {
                    'guild_id': guild_id,
                    'channel_id': interaction.channel.id,
                    'event_name': event_name,
                    'message_obj': message
                }
                
    except Exception as e:
        print(f"ERROR in countdown slash command: {e}")
        await interaction.response.send_message(embed=nova_embed("cOUNTDOWN", "aN eRROR oCCURRED wHILE sHOWING cOUNTDOWN!"))

@bot.tree.command(name="addcountdown", description="Add a new countdown event (EST timezone)")
@app_commands.describe(
    event_name="Name of the event",
    end_time="End time in format YYYY-MM-DD HH:MM (EST timezone)",
    description="Description of the event"
)
async def addcountdown_slash(interaction: discord.Interaction, event_name: str, end_time: str, description: str = None):
    """Add a new countdown event (slash command version)"""
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("aDDcOUNTDOWN", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_COUNTDOWNS
    
    try:
        # Parse the datetime in EST timezone
        est = pytz.timezone('US/Eastern')
        end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        end_datetime = est.localize(end_datetime)
        
        # Check if event already exists
        if event_name in BCA_COUNTDOWNS:
            await interaction.response.send_message(embed=nova_embed("aDDcOUNTDOWN", f"eVENT '{event_name}' aLREADY eXISTS!"), ephemeral=True)
            return
        
        # Add the countdown
        BCA_COUNTDOWNS[event_name] = {
            "end_time": end_datetime,
            "description": description or "No description provided"
        }
        
        # Save to file
        save_bca_countdowns()
        
        # Calculate time remaining
        now = datetime.now(est)
        time_diff = end_datetime - now
        
        if time_diff.total_seconds() <= 0:
            time_str = "eVENT hAS aLREADY eNDED!"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
        
        embed = discord.Embed(
            title="✅ cOUNTDOWN aDDED!",
            description=f"**eVENT:** {event_name}\n**dESCRIPTION:** {description or 'No description'}\n**eNDS:** {end_datetime.strftime('%Y-%m-%d at %H:%M EST')}\n**tIME rEMAINING:** {time_str}",
            color=0xff69b4
        )
        
        await interaction.response.send_message(embed=embed)
        
    except ValueError as e:
        await interaction.response.send_message(embed=nova_embed("aDDcOUNTDOWN", f"iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM\neXAMPLE: 2024-12-25 18:00"), ephemeral=True)
    except Exception as e:
        print(f"ERROR in addcountdown slash command: {e}")
        await interaction.response.send_message(embed=nova_embed("aDDcOUNTDOWN", "aN eRROR oCCURRED wHILE aDDING cOUNTDOWN!"), ephemeral=True)

# Member Count Command
@bot.command()
async def membercount(ctx):
    """Show server member statistics"""
    guild = ctx.guild
    
    total_members = guild.member_count
    humans = sum(1 for member in guild.members if not member.bot)
    bots = sum(1 for member in guild.members if member.bot)
    
    embed = discord.Embed(
        title=f"📊 {guild.name} mEMBER cOUNT",
        color=0xff69b4
    )
    
    embed.add_field(name="👥 tOTAL mEMBERS", value=f"{total_members:,}", inline=True)
    embed.add_field(name="👤 hUMANS", value=f"{humans:,}", inline=True)
    embed.add_field(name="🤖 bOTS", value=f"{bots:,}", inline=True)
    
    # Add percentage breakdown
    if total_members > 0:
        human_percent = (humans / total_members) * 100
        bot_percent = (bots / total_members) * 100
        
        embed.add_field(
            name="📊 bREAKDOWN", 
            value=f"hUMANS: {human_percent:.1f}%\nbOTS: {bot_percent:.1f}%", 
            inline=False
        )
    
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text=f"sERVER cREATED: {guild.created_at.strftime('%B %d, %Y')}")
    
    await ctx.send(embed=embed)

@bot.command()
async def mostactive(ctx):
    """Show the most active users by message count for all time periods (Admin/Mod only)"""
    # Check permissions - only mods/admins can use this command
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("mOST aCTIVE", "yOU dON'T hAVE pERMISSION tO uSE tHIS cOMMAND!"))
        return
        
    if not ctx.guild:
        await ctx.send(embed=nova_embed("mOST aCTIVE", "tHIS cOMMAND cAN oNLY bE uSED iN sERVERS!"))
        return
    
    guild_id = ctx.guild.id
    
    # Check if we have data for this server
    if guild_id not in MESSAGE_ACTIVITY:
        await ctx.send(embed=nova_embed("mOST aCTIVE", "nO mESSAGE dATA fOUND fOR tHIS sERVER yET!"))
        return
    
    now = datetime.now(dt_timezone.utc)
    
    # Define all periods
    periods = [
        ("lAST mONTH", now - timedelta(days=30)),
        ("lAST 3 mONTHS", now - timedelta(days=90)),
        ("lAST yEAR", now - timedelta(days=365)),
        ("lIFETIME", datetime.min.replace(tzinfo=dt_timezone.utc))
    ]
    
    embed = nova_embed("📊 mOST aCTIVE uSERS", "")
    
    for period_name, cutoff in periods:
        # Calculate message counts for each user for this period
        user_counts = {}
        for user_id, messages in MESSAGE_ACTIVITY[guild_id].items():
            total_count = 0
            for msg_data in messages:
                if msg_data["timestamp"] >= cutoff:
                    total_count += msg_data["count"]
            
            if total_count > 0:
                user_counts[user_id] = total_count
        
        if user_counts:
            # Sort users by message count (descending) and get top 3
            sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Create leaderboard for this period
            leaderboard = []
            for i, (user_id, count) in enumerate(sorted_users, 1):
                member = ctx.guild.get_member(user_id)
                if member:
                    # Add medal emojis for top 3
                    if i == 1:
                        emoji = "🥇"
                    elif i == 2:
                        emoji = "🥈"
                    elif i == 3:
                        emoji = "🥉"
                    
                    leaderboard.append(f"{emoji} **{member.display_name}** - {count:,}")
                else:
                    # User left the server
                    leaderboard.append(f"{i}. *[User Left]* - {count:,}")
            
            embed.add_field(
                name=f"**{period_name}**",
                value="\n".join(leaderboard) if leaderboard else "nO dATA",
                inline=True
            )
        else:
            embed.add_field(
                name=f"**{period_name}**",
                value="nO dATA",
                inline=True
            )
    
    embed.set_footer(text=f"dATA sTARTS fROM sERVER cREATION • sHOWING tOP 3 pER pERIOD")
    
    await ctx.send(embed=embed)

@bot.tree.command(name="mostactive", description="Show the most active users by message count for all time periods (Admin/Mod only)")
async def mostactive_slash(interaction: discord.Interaction):
    """Show the most active users by message count for all time periods (slash command version)"""
    # Check permissions - only mods/admins can use this command
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("mOST aCTIVE", "yOU dON'T hAVE pERMISSION tO uSE tHIS cOMMAND!"), ephemeral=True)
        return
        
    if not interaction.guild:
        await interaction.response.send_message(embed=nova_embed("mOST aCTIVE", "tHIS cOMMAND cAN oNLY bE uSED iN sERVERS!"), ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    
    # Check if we have data for this server
    if guild_id not in MESSAGE_ACTIVITY:
        await interaction.response.send_message(embed=nova_embed("mOST aCTIVE", "nO mESSAGE dATA fOUND fOR tHIS sERVER yET!"), ephemeral=True)
        return
    
    now = datetime.now(dt_timezone.utc)
    
    # Define all periods
    periods = [
        ("lAST mONTH", now - timedelta(days=30)),
        ("lAST 3 mONTHS", now - timedelta(days=90)),
        ("lAST yEAR", now - timedelta(days=365)),
        ("lIFETIME", datetime.min.replace(tzinfo=dt_timezone.utc))
    ]
    
    embed = nova_embed("📊 mOST aCTIVE uSERS", "")
    
    for period_name, cutoff in periods:
        # Calculate message counts for each user for this period
        user_counts = {}
        for user_id, messages in MESSAGE_ACTIVITY[guild_id].items():
            total_count = 0
            for msg_data in messages:
                if msg_data["timestamp"] >= cutoff:
                    total_count += msg_data["count"]
            
            if total_count > 0:
                user_counts[user_id] = total_count
        
        if user_counts:
            # Sort users by message count (descending) and get top 3
            sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Create leaderboard for this period
            leaderboard = []
            for i, (user_id, count) in enumerate(sorted_users, 1):
                member = interaction.guild.get_member(user_id)
                if member:
                    # Add medal emojis for top 3
                    if i == 1:
                        emoji = "🥇"
                    elif i == 2:
                        emoji = "🥈"
                    elif i == 3:
                        emoji = "🥉"
                    
                    leaderboard.append(f"{emoji} **{member.display_name}** - {count:,}")
                else:
                    # User left the server
                    leaderboard.append(f"{i}. *[User Left]* - {count:,}")
            
            embed.add_field(
                name=f"**{period_name}**",
                value="\n".join(leaderboard) if leaderboard else "nO dATA",
                inline=True
            )
        else:
            embed.add_field(
                name=f"**{period_name}**",
                value="nO dATA",
                inline=True
            )
    
    embed.set_footer(text=f"dATA sTARTS fROM sERVER cREATION • sHOWING tOP 3 pER pERIOD")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="membercount", description="Show server member statistics")
async def membercount_slash(interaction: discord.Interaction):
    """Show server member statistics (slash command version)"""
    guild = interaction.guild
    
    total_members = guild.member_count
    humans = sum(1 for member in guild.members if not member.bot)
    bots = sum(1 for member in guild.members if member.bot)
    
    embed = discord.Embed(
        title=f"📊 {guild.name} mEMBER cOUNT",
        color=0xff69b4
    )
    
    embed.add_field(name="👥 tOTAL mEMBERS", value=f"{total_members:,}", inline=True)
    embed.add_field(name="👤 hUMANS", value=f"{humans:,}", inline=True)
    embed.add_field(name="🤖 bOTS", value=f"{bots:,}", inline=True)
    
    # Add percentage breakdown
    if total_members > 0:
        human_percent = (humans / total_members) * 100
        bot_percent = (bots / total_members) * 100
        
        embed.add_field(
            name="📊 bREAKDOWN", 
            value=f"hUMANS: {human_percent:.1f}%\nbOTS: {bot_percent:.1f}%", 
            inline=False
        )
    
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text=f"sERVER cREATED: {guild.created_at.strftime('%B %d, %Y')}")
    
    await interaction.response.send_message(embed=embed)

# BCA Results Command
@bot.command()
async def bcaresults(ctx, *, category: str = None):
    """Show BCA voting results for a category (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("bCA rESULTS", "yOU dON'T hAVE pERMISSION!"))
        return
    
    if category is None:
        await ctx.send(embed=nova_embed("bCA rESULTS", "Usage: ?bcaresults <category name>"))
        return
    
    global BCA_VOTES
    category = category.lower()
    
    if category not in BCA_VOTES or not BCA_VOTES[category]:
        await ctx.send(embed=nova_embed("bCA rESULTS", f"nO vOTES fOR '{category}' yET!"))
        return
    
    # Count votes for each nominee
    vote_counts = {}
    for voter_id, nominee_id in BCA_VOTES[category].items():
        if nominee_id not in vote_counts:
            vote_counts[nominee_id] = 0
        vote_counts[nominee_id] += 1
    
    # Sort by vote count (descending)
    sorted_results = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Create results embed
    embed = discord.Embed(
        title=f"🏆 bCA rESULTS: {category.title()}",
        color=0xff69b4
    )
    
    results_text = []
    total_votes = sum(vote_counts.values())
    
    for i, (nominee_id, votes) in enumerate(sorted_results[:10]):  # Top 10
        member = ctx.guild.get_member(int(nominee_id))
        if member:
            percentage = (votes / total_votes) * 100 if total_votes > 0 else 0
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            results_text.append(f"{medal} **{member.display_name}** - {votes} votes ({percentage:.1f}%)")
    
    embed.description = "\n".join(results_text) if results_text else "nO rESULTS tO sHOW"
    embed.set_footer(text=f"tOTAL vOTES: {total_votes}")
    
    await ctx.send(embed=embed)

# =========================
# BCA Slash Commands
# =========================

# BCA Setup Slash Commands
@bot.tree.command(name="setbcanominations", description="Set the BCA nominations channel (mods only)")
@app_commands.describe(channel="The channel for BCA nominations")
async def slash_setbcanominations(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET bCA nOMINATIONS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_NOMINATIONS_CHANNEL_ID
    if channel is None:
        BCA_NOMINATIONS_CHANNEL_ID = None
        await interaction.response.send_message(embed=nova_embed("sET bCA nOMINATIONS", "bCA nOMINATIONS cHANNEL dISABLED!"))
    else:
        BCA_NOMINATIONS_CHANNEL_ID = channel.id
        await interaction.response.send_message(embed=nova_embed("sET bCA nOMINATIONS", f"bCA nOMINATIONS cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.tree.command(name="setbcanominationslogs", description="Set the BCA nominations logs channel (mods only)")
@app_commands.describe(channel="The channel for BCA nomination logs")
async def slash_setbcanominationslogs(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET bCA nOM lOGS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_NOMINATIONS_LOGS_CHANNEL_ID
    if channel is None:
        BCA_NOMINATIONS_LOGS_CHANNEL_ID = None
        await interaction.response.send_message(embed=nova_embed("sET bCA nOM lOGS", "bCA nOMINATIONS lOGS cHANNEL dISABLED!"))
    else:
        BCA_NOMINATIONS_LOGS_CHANNEL_ID = channel.id
        await interaction.response.send_message(embed=nova_embed("sET bCA nOM lOGS", f"bCA nOMINATIONS lOGS cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.tree.command(name="setbcavoting", description="Set the BCA voting channel (mods only)")
@app_commands.describe(channel="The channel for BCA voting")
async def slash_setbcavoting(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_VOTING_CHANNEL_ID
    if channel is None:
        BCA_VOTING_CHANNEL_ID = None
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING", "bCA vOTING cHANNEL dISABLED!"))
    else:
        BCA_VOTING_CHANNEL_ID = channel.id
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING", f"bCA vOTING cHANNEL sET tO {channel.mention}!"))
    save_config()

@bot.tree.command(name="setbcavotinglogs", description="Set the BCA voting logs channel (mods only)")
@app_commands.describe(channel="The channel for BCA voting logs")
async def slash_setbcavotinglogs(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING lOGS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_VOTING_LOGS_CHANNEL_ID
    if channel is None:
        BCA_VOTING_LOGS_CHANNEL_ID = None
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING lOGS", "bCA vOTING lOGS cHANNEL dISABLED!"))
    else:
        BCA_VOTING_LOGS_CHANNEL_ID = channel.id
        await interaction.response.send_message(embed=nova_embed("sET bCA vOTING lOGS", f"bCA vOTING lOGS cHANNEL sET tO {channel.mention}!"))
    save_config()

# BCA Deadline Slash Commands
@bot.tree.command(name="setbcanomdeadline", description="Set nomination deadline (mods only). Format: YYYY-MM-DD HH:MM EST")
@app_commands.describe(end_time="Deadline in format: YYYY-MM-DD HH:MM (EST timezone)")
async def slash_setbcanomdeadline(interaction: discord.Interaction, end_time: str = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET nOM dEADLINE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_NOMINATION_DEADLINE
    
    if end_time is None:
        BCA_NOMINATION_DEADLINE = None
        await interaction.response.send_message(embed=nova_embed("sET nOM dEADLINE", "nOMINATION dEADLINE rEMOVED!"))
    else:
        try:
            # Parse time as EST
            est = pytz.timezone('US/Eastern')
            naive_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            est_datetime = est.localize(naive_datetime)
            # Convert to UTC for storage
            utc_datetime = est_datetime.astimezone(pytz.UTC)
            BCA_NOMINATION_DEADLINE = utc_datetime
            
            # Show confirmation in EST
            await interaction.response.send_message(embed=nova_embed("sET nOM dEADLINE", f"nOMINATION dEADLINE sET tO:\n{est_datetime.strftime('%Y-%m-%d at %H:%M EST')}"))
        except ValueError:
            await interaction.response.send_message(embed=nova_embed("sET nOM dEADLINE", "iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM (EST)\n\nExample: 2024-12-31 23:59"), ephemeral=True)
            return
    
    # Reset announcement tracker when deadline changes
    reset_announcement_tracker()
    save_config()

@bot.tree.command(name="setbcavotedeadline", description="Set voting deadline (mods only). Format: YYYY-MM-DD HH:MM EST")
@app_commands.describe(end_time="Deadline in format: YYYY-MM-DD HH:MM (EST timezone)")
async def slash_setbcavotedeadline(interaction: discord.Interaction, end_time: str = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("sET vOTE dEADLINE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_VOTING_DEADLINE
    
    if end_time is None:
        BCA_VOTING_DEADLINE = None
        await interaction.response.send_message(embed=nova_embed("sET vOTE dEADLINE", "vOTING dEADLINE rEMOVED!"))
    else:
        try:
            # Parse time as EST
            est = pytz.timezone('US/Eastern')
            naive_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            est_datetime = est.localize(naive_datetime)
            # Convert to UTC for storage
            utc_datetime = est_datetime.astimezone(pytz.UTC)
            BCA_VOTING_DEADLINE = utc_datetime
            
            # Show confirmation in EST
            await interaction.response.send_message(embed=nova_embed("sET vOTE dEADLINE", f"vOTING dEADLINE sET tO:\n{est_datetime.strftime('%Y-%m-%d at %H:%M EST')}"))
        except ValueError:
            await interaction.response.send_message(embed=nova_embed("sET vOTE dEADLINE", "iNVALID dATE fORMAT! uSE: YYYY-MM-DD HH:MM (EST)\n\nExample: 2024-12-31 23:59"), ephemeral=True)
            return
    
    # Reset announcement tracker when deadline changes
    reset_announcement_tracker()
    save_config()

@bot.tree.command(name="bcadeadlines", description="Show current BCA deadlines")
async def slash_bcadeadlines(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⏰ bCA dEADLINES",
        color=0xff69b4,
        timestamp=datetime.now()
    )
    
    if BCA_NOMINATION_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        now_utc = datetime.now(pytz.UTC)
        deadline_est = BCA_NOMINATION_DEADLINE.astimezone(est)
        
        time_diff = BCA_NOMINATION_DEADLINE - now_utc
        if time_diff.total_seconds() <= 0:
            nom_status = "cLOSED"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            nom_status = f"{days}d {hours}h {minutes}m remaining"
        
        embed.add_field(
            name="📝 nOMINATIONS",
            value=f"**Deadline:** {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n**Status:** {nom_status}",
            inline=False
        )
    else:
        embed.add_field(name="📝 nOMINATIONS", value="nO dEADLINE sET", inline=False)
    
    if BCA_VOTING_DEADLINE:
        # Convert UTC deadline to EST for display
        est = pytz.timezone('US/Eastern')
        now_utc = datetime.now(pytz.UTC)
        deadline_est = BCA_VOTING_DEADLINE.astimezone(est)
        
        time_diff = BCA_VOTING_DEADLINE - now_utc
        if time_diff.total_seconds() <= 0:
            vote_status = "cLOSED"
        else:
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            vote_status = f"{days}d {hours}h {minutes}m remaining"
        
        embed.add_field(
            name="🗳️ vOTING",
            value=f"**Deadline:** {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n**Status:** {vote_status}",
            inline=False
        )
    else:
        embed.add_field(name="🗳️ vOTING", value="nO dEADLINE sET", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.command()
async def endimposter(ctx):
    """End the current imposter game (mods only)"""
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("eND iMPOSTER", "yOU dON'T hAVE pERMISSION!"))
        return
    
    # This is a simple implementation - in a real scenario you'd track active games
    await ctx.send(embed=nova_embed(
        "🛑 iMPOSTER gAME eNDED",
        "tHE cURRENT iMPOSTER gAME hAS bEEN eNDED bY a mODERATOR!"
    ))

@bot.tree.command(name="endimposter", description="End the current imposter game (mods only)")
async def endimposter_slash(interaction: discord.Interaction):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("eND iMPOSTER", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    await interaction.response.send_message(embed=nova_embed(
        "🛑 iMPOSTER gAME eNDED",
        "tHE cURRENT iMPOSTER gAME hAS bEEN eNDED bY a mODERATOR!"
    ))

# BCA Category Management Slash Commands
@bot.tree.command(name="bcaaddcategory", description="Add a BCA category (mods only)")
@app_commands.describe(category_name="Name of the category to add")
async def slash_bcaaddcategory(interaction: discord.Interaction, category_name: str):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA aDD cATEGORY", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_CATEGORIES
    category_name = category_name.lower()
    
    if category_name in BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA aDD cATEGORY", f"cATEGORY '{category_name}' aLREADY eXISTS!"), ephemeral=True)
        return
    
    BCA_CATEGORIES[category_name] = {"allow_self_nomination": False}
    save_bca_categories(BCA_CATEGORIES)
    
    await interaction.response.send_message(embed=nova_embed("bCA aDD cATEGORY", f"aDDED cATEGORY: {category_name}\n\nsELF-nOMINATION: dISABLED"))

@bot.tree.command(name="bcatoggleself", description="Toggle self-nomination for a BCA category (mods only)")
@app_commands.describe(category_name="Name of the category to toggle")
async def slash_bcatoggleself(interaction: discord.Interaction, category_name: str):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA tOGGLE sELF", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_CATEGORIES
    category_name = category_name.lower()
    
    if category_name not in BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA tOGGLE sELF", f"cATEGORY '{category_name}' dOESN'T eXIST!"), ephemeral=True)
        return
    
    BCA_CATEGORIES[category_name]["allow_self_nomination"] = not BCA_CATEGORIES[category_name]["allow_self_nomination"]
    save_bca_categories(BCA_CATEGORIES)
    
    status = "eNABLED" if BCA_CATEGORIES[category_name]["allow_self_nomination"] else "dISABLED"
    await interaction.response.send_message(embed=nova_embed("bCA tOGGLE sELF", f"sELF-nOMINATION fOR '{category_name}': {status}"))

@bot.tree.command(name="bcacategories", description="List all BCA categories")
async def slash_bcacategories(interaction: discord.Interaction):
    global BCA_CATEGORIES
    
    if not BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA cATEGORIES", "nO cATEGORIES sET uP yET!"))
        return
    
    category_list = []
    for category, settings in BCA_CATEGORIES.items():
        self_nom = "✅" if settings["allow_self_nomination"] else "❌"
        category_list.append(f"**{category.title()}** - Self-nomination: {self_nom}")
    
    embed = discord.Embed(
        title="🏆 bCA cATEGORIES",
        description="\n".join(category_list),
        color=0xff69b4
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removebcacategory", description="Remove a BCA category (mods only)")
@app_commands.describe(category_name="Name of the category to remove")
async def slash_removebcacategory(interaction: discord.Interaction, category_name: str):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA rEMOVE cATEGORY", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS, BCA_VOTES
    category_name = category_name.lower()
    
    if category_name not in BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA rEMOVE cATEGORY", f"cATEGORY '{category_name}' dOESN'T eXIST!"), ephemeral=True)
        return
    
    # Remove category from all data structures
    del BCA_CATEGORIES[category_name]
    if category_name in BCA_NOMINATIONS:
        del BCA_NOMINATIONS[category_name]
    if category_name in BCA_VOTES:
        del BCA_VOTES[category_name]
    
    # Save all changes
    save_bca_categories(BCA_CATEGORIES)
    save_bca_nominations(BCA_NOMINATIONS)
    save_bca_votes(BCA_VOTES)
    
    await interaction.response.send_message(embed=nova_embed("bCA rEMOVE cATEGORY", f"🗑️ rEMOVED cATEGORY: {category_name.title()}\n\naLL nOMINATIONS aND vOTES fOR tHIS cATEGORY hAVE bEEN dELETED!"))

# BCA Reset Slash Commands
@bot.tree.command(name="resetnominations", description="Reset nominations for a category or all categories (mods only)")
@app_commands.describe(category="Category to reset (leave empty to reset all)")
async def slash_resetnominations(interaction: discord.Interaction, category: str = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("rESET nOMINATIONS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_NOMINATIONS
    
    if category is None:
        # Reset all nominations
        BCA_NOMINATIONS = {}
        save_bca_nominations(BCA_NOMINATIONS)
        await interaction.response.send_message(embed=nova_embed("rESET nOMINATIONS", "🗑️ aLL nOMINATIONS hAVE bEEN rESET!"))
    else:
        category = category.lower()
        if category not in BCA_CATEGORIES:
            await interaction.response.send_message(embed=nova_embed("rESET nOMINATIONS", f"cATEGORY '{category}' dOESN'T eXIST!"), ephemeral=True)
            return
        
        # Reset nominations for specific category
        if category in BCA_NOMINATIONS:
            del BCA_NOMINATIONS[category]
            save_bca_nominations(BCA_NOMINATIONS)
            await interaction.response.send_message(embed=nova_embed("rESET nOMINATIONS", f"🗑️ nOMINATIONS fOR '{category.title()}' hAVE bEEN rESET!"))
        else:
            await interaction.response.send_message(embed=nova_embed("rESET nOMINATIONS", f"nO nOMINATIONS fOUND fOR '{category.title()}'!"))

@bot.tree.command(name="resetvotes", description="Reset votes for a category or all categories (mods only)")
@app_commands.describe(category="Category to reset (leave empty to reset all)")
async def slash_resetvotes(interaction: discord.Interaction, category: str = None):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("rESET vOTES", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_VOTES
    
    if category is None:
        # Reset all votes
        BCA_VOTES = {}
        save_bca_votes(BCA_VOTES)
        await interaction.response.send_message(embed=nova_embed("rESET vOTES", "🗑️ aLL vOTES hAVE bEEN rESET!"))
    else:
        category = category.lower()
        if category not in BCA_CATEGORIES:
            await interaction.response.send_message(embed=nova_embed("rESET vOTES", f"cATEGORY '{category}' dOESN'T eXIST!"), ephemeral=True)
            return
        
        # Reset votes for specific category
        if category in BCA_VOTES:
            del BCA_VOTES[category]
            save_bca_votes(BCA_VOTES)
            await interaction.response.send_message(embed=nova_embed("rESET vOTES", f"🗑️ vOTES fOR '{category.title()}' hAVE bEEN rESET!"))
        else:
            await interaction.response.send_message(embed=nova_embed("rESET vOTES", f"nO vOTES fOUND fOR '{category.title()}'!"))

# BCA Overview Slash Commands
@bot.tree.command(name="bcanominations", description="Show all current nominations across all categories (mods only)")
async def slash_bcanominations(interaction: discord.Interaction):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA nOMINATIONS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_CATEGORIES, BCA_NOMINATIONS
    
    if not BCA_CATEGORIES:
        await interaction.response.send_message(embed=nova_embed("bCA nOMINATIONS", "nO cATEGORIES sET uP yET!"))
        return
    
    embed = discord.Embed(
        title="🏆 bCA nOMINATIONS oVERVIEW",
        color=0xff69b4
    )
    
    total_nominations = 0
    categories_with_noms = 0
    
    for category in BCA_CATEGORIES.keys():
        if category in BCA_NOMINATIONS and BCA_NOMINATIONS[category]:
            # Count nominations for this category
            nominee_counts = {}
            for nominator_id, nomination_data in BCA_NOMINATIONS[category].items():
                nominee_id = nomination_data['nominee']
                if nominee_id not in nominee_counts:
                    nominee_counts[nominee_id] = 0
                nominee_counts[nominee_id] += 1
            
            # Sort by nomination count (descending)
            sorted_nominees = sorted(nominee_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Build category text
            category_text = []
            for nominee_id, count in sorted_nominees:
                member = interaction.guild.get_member(int(nominee_id))
                if member:
                    plural = "person" if count == 1 else "people"
                    category_text.append(f"• {member.mention} (nominated by {count} {plural})")
            
            if category_text:
                nom_count = len(BCA_NOMINATIONS[category])
                embed.add_field(
                    name=f"📝 {category.title()} ({nom_count} nominations)",
                    value="\n".join(category_text),
                    inline=False
                )
                total_nominations += nom_count
                categories_with_noms += 1
        else:
            # No nominations for this category
            embed.add_field(
                name=f"📝 {category.title()} (0 nominations)",
                value="• nO nOMINATIONS yET",
                inline=False
            )
    
    # Add summary footer
    if total_nominations > 0:
        embed.set_footer(text=f"tOTAL: {total_nominations} nominations across {categories_with_noms}/{len(BCA_CATEGORIES)} categories")
    else:
        embed.set_footer(text="nO nOMINATIONS yET")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bcaresults", description="Show BCA voting results for a category (mods only)")
@app_commands.describe(category="Category to show results for")
async def slash_bcaresults(interaction: discord.Interaction, category: str):
    if not has_mod_or_admin_interaction(interaction):
        await interaction.response.send_message(embed=nova_embed("bCA rESULTS", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    
    global BCA_VOTES
    category = category.lower()
    
    if category not in BCA_VOTES or not BCA_VOTES[category]:
        await interaction.response.send_message(embed=nova_embed("bCA rESULTS", f"nO vOTES fOR '{category}' yET!"))
        return
    
    # Count votes for each nominee
    vote_counts = {}
    for voter_id, nominee_id in BCA_VOTES[category].items():
        if nominee_id not in vote_counts:
            vote_counts[nominee_id] = 0
        vote_counts[nominee_id] += 1
    
    # Sort by vote count (descending)
    sorted_results = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Create results embed
    embed = discord.Embed(
        title=f"🏆 bCA rESULTS: {category.title()}",
        color=0xff69b4
    )
    
    results_text = []
    total_votes = sum(vote_counts.values())
    
    for i, (nominee_id, votes) in enumerate(sorted_results[:10]):  # Top 10
        member = interaction.guild.get_member(int(nominee_id))
        if member:
            percentage = (votes / total_votes) * 100 if total_votes > 0 else 0
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            results_text.append(f"{medal} **{member.display_name}** - {votes} votes ({percentage:.1f}%)")
    
    embed.description = "\n".join(results_text) if results_text else "nO rESULTS tO sHOW"
    embed.set_footer(text=f"tOTAL vOTES: {total_votes}")
    
    await interaction.response.send_message(embed=embed)

# =========================
# Background Task System for Deadline Monitoring
# =========================

# Track which announcements have been sent to avoid duplicates
announcement_tracker = {
    'nomination_1h_warning': False,
    'nomination_closed': False,
    'voting_1h_warning': False,
    'voting_closed': False,
    'voting_opened': False
}

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    
    # Load all data
    load_config()
    load_balances()
    load_xp()
    load_birthdays()
    load_afk()
    
    # Start the live countdown update loop - THIS IS THE CRITICAL PART!
    try:
        bot.loop.create_task(countdown_update_loop())
        print("🚀 LIVE COUNTDOWN UPDATE LOOP STARTED SUCCESSFULLY!")
        print("🔴 Countdown messages will now auto-edit every second!")
    except Exception as e:
        print(f"❌ Error starting countdown update loop: {e}")
    
    # Start the deadline monitoring task
    deadline_monitor.start()

from discord.ext import tasks

@tasks.loop(minutes=5)  # Check every 5 minutes
async def deadline_monitor():
    """Monitor deadlines and send automatic announcements"""
    try:
        global BCA_NOMINATION_DEADLINE, BCA_VOTING_DEADLINE, announcement_tracker
        
        # Get current time in UTC
        now_utc = datetime.now(pytz.UTC)
        est = pytz.timezone('US/Eastern')
        
        # Find announcement channels
        nomination_channel = None
        if BCA_NOMINATIONS_CHANNEL_ID:
            nomination_channel = bot.get_channel(BCA_NOMINATIONS_CHANNEL_ID)
        
        # === NOMINATION DEADLINE MONITORING ===
        if BCA_NOMINATION_DEADLINE:
            time_until_nom_deadline = BCA_NOMINATION_DEADLINE - now_utc
            
            # 1 hour warning for nominations
            if (3540 <= time_until_nom_deadline.total_seconds() <= 3660 and 
                not announcement_tracker['nomination_1h_warning']):
                
                if nomination_channel:
                    deadline_est = BCA_NOMINATION_DEADLINE.astimezone(est)
                    embed = discord.Embed(
                        title="⚠️ nOMINATION dEADLINE wARNING!",
                        description=f"⏰ **1 hOUR lEFT tO nOMINATE!**\n\nDeadline: {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n\nUse `?nominate @user <category>` to submit your nominations!",
                        color=0xffaa00
                    )
                    await nomination_channel.send(embed=embed)
                    announcement_tracker['nomination_1h_warning'] = True
            
            # Nominations closed announcement
            elif (time_until_nom_deadline.total_seconds() <= 0 and 
                  not announcement_tracker['nomination_closed']):
                
                if nomination_channel:
                    embed = discord.Embed(
                        title="📝 nOMINATIONS cLOSED!",
                        description="📝 **nOMINATIONS fOR aLL cATEGORIES hAVE cLOSED!**\n\n🗳️ vOTING wILL oPEN sOON!",
                        color=0xff0000
                    )
                    await nomination_channel.send(embed=embed)
                    announcement_tracker['nomination_closed'] = True
                    announcement_tracker['voting_opened'] = False  # Reset for voting announcement
        
        # === VOTING DEADLINE MONITORING ===
        if BCA_VOTING_DEADLINE:
            time_until_vote_deadline = BCA_VOTING_DEADLINE - now_utc
            
            # 1 hour warning for voting
            if (3540 <= time_until_vote_deadline.total_seconds() <= 3660 and 
                not announcement_tracker['voting_1h_warning']):
                
                voting_channel = bot.get_channel(BCA_VOTING_CHANNEL_ID) if BCA_VOTING_CHANNEL_ID else nomination_channel
                if voting_channel:
                    deadline_est = BCA_VOTING_DEADLINE.astimezone(est)
                    embed = discord.Embed(
                        title="⚠️ vOTING dEADLINE wARNING!",
                        description=f"⏰ **1 hOUR lEFT tO vOTE!**\n\nDeadline: {deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n\nMods can use `?bcavote <category>` to create voting sessions!",
                        color=0xffaa00
                    )
                    await voting_channel.send(embed=embed)
                    announcement_tracker['voting_1h_warning'] = True
            
            # Voting closed announcement
            elif (time_until_vote_deadline.total_seconds() <= 0 and 
                  not announcement_tracker['voting_closed']):
                
                voting_channel = bot.get_channel(BCA_VOTING_CHANNEL_ID) if BCA_VOTING_CHANNEL_ID else nomination_channel
                if voting_channel:
                    embed = discord.Embed(
                        title="🗳️ vOTING cLOSED!",
                        description="🗳️ **vOTING fOR aLL cATEGORIES hAS cLOSED!**\n\n🏆 rESULTS wILL bE aNNOUNCED sOON!",
                        color=0xff0000
                    )
                    await voting_channel.send(embed=embed)
                    announcement_tracker['voting_closed'] = True
        
        # === VOTING OPENED ANNOUNCEMENT ===
        # Announce when nominations are closed but voting hasn't started yet
        if (BCA_NOMINATION_DEADLINE and BCA_VOTING_DEADLINE and 
            now_utc > BCA_NOMINATION_DEADLINE and now_utc < BCA_VOTING_DEADLINE and 
            not announcement_tracker['voting_opened']):
            
            voting_channel = bot.get_channel(BCA_VOTING_CHANNEL_ID) if BCA_VOTING_CHANNEL_ID else nomination_channel
            if voting_channel:
                vote_deadline_est = BCA_VOTING_DEADLINE.astimezone(est)
                embed = discord.Embed(
                    title="🗳️ vOTING iS nOW oPEN!",
                    description=f"🗳️ **vOTING iS nOW oPEN!**\n\nVoting deadline: {vote_deadline_est.strftime('%Y-%m-%d at %H:%M EST')}\n\nMods can use `?bcavote <category>` to create voting sessions!",
                    color=0x00ff00
                )
                await voting_channel.send(embed=embed)
                announcement_tracker['voting_opened'] = True
    
    except Exception as e:
        print(f"Error in deadline_monitor: {e}")
        import traceback
        traceback.print_exc()

# Reset announcement tracker when deadlines are changed
def reset_announcement_tracker():
    """Reset announcement tracker when deadlines change"""
    global announcement_tracker
    announcement_tracker = {
        'nomination_1h_warning': False,
        'nomination_closed': False,
        'voting_1h_warning': False,
        'voting_closed': False,
        'voting_opened': False
    }

# =========================
# Centralized Logging Configuration Commands
# =========================

@bot.command()
async def setcentrallogging(ctx, guild_id: int = None, overview_channel: discord.TextChannel = None, archive_category: discord.CategoryChannel = None):
    """Set up centralized logging system (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "oNLY tHE oWNER cAN sET tHIS uP!"))
        return
    
    if not guild_id or not overview_channel or not archive_category:
        await ctx.send(embed=nova_embed(
            "cENTRAL lOGGING sETUP",
            "Usage: `?setcentrallogging <guild_id> #overview_channel #archive_category`\n\n"
            "**guild_id:** ID of your logging server\n"
            "**overview_channel:** Channel for join/leave notifications\n"
            "**archive_category:** Category for archived server logs"
        ))
        return
    
    global CENTRAL_LOG_GUILD_ID, CENTRAL_OVERVIEW_CHANNEL_ID, CENTRAL_ARCHIVE_CATEGORY_ID
    CENTRAL_LOG_GUILD_ID = guild_id
    CENTRAL_OVERVIEW_CHANNEL_ID = overview_channel.id
    CENTRAL_ARCHIVE_CATEGORY_ID = archive_category.id
    
    # Save to config
    config["central_log_guild_id"] = CENTRAL_LOG_GUILD_ID
    config["central_overview_channel_id"] = CENTRAL_OVERVIEW_CHANNEL_ID
    config["central_archive_category_id"] = CENTRAL_ARCHIVE_CATEGORY_ID
    save_config()
    
    # Test the setup
    test_guild = bot.get_guild(guild_id)
    if not test_guild:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "⚠️ wARNING: cANNOT aCCESS lOGGING sERVER!"))
        return
    
    embed = nova_embed(
        "✅ cENTRAL lOGGING sETUP cOMPLETE!",
        f"**Logging Server:** {test_guild.name}\n"
        f"**Overview Channel:** {overview_channel.mention}\n"
        f"**Archive Category:** {archive_category.name}\n\n"
        f"Nova will now auto-create logging categories for each server!"
    )
    await ctx.send(embed=embed)
    
    # Send test message to overview channel
    test_embed = discord.Embed(
        title="🔧 Centralized Logging System Activated",
        description="Nova's centralized logging system is now active!",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    test_embed.add_field(
        name="📋 Features",
        value="• Auto-create categories for new servers\n"
              "• Individual log channels per server\n"
              "• Archive logs when leaving servers\n"
              "• Master overview of all joins/leaves",
        inline=False
    )
    test_embed.set_footer(text="System configured by " + str(ctx.author))
    await overview_channel.send(embed=test_embed)

@bot.command()
async def backfillcentrallogging(ctx):
    """Create logging categories for all servers Nova is already in (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "oNLY tHE oWNER cAN rUN tHIS!"))
        return
    
    if not CENTRAL_LOG_GUILD_ID:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "❌ cENTRAL lOGGING nOT cONFIGURED yET!"))
        return
    
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    if not central_guild:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "❌ cANNOT aCCESS lOGGING sERVER!"))
        return
    
    # Get all servers Nova is in (excluding the logging server itself)
    target_servers = [guild for guild in bot.guilds if guild.id != CENTRAL_LOG_GUILD_ID]
    
    if not target_servers:
        await ctx.send(embed=nova_embed("bACKFILL cOMPLETE", "nO sERVERS tO bACKFILL!"))
        return
    
    # Send initial status
    status_embed = nova_embed(
        "🔄 bACKFILLING cENTRAL lOGGING",
        f"Creating logging categories for {len(target_servers)} existing servers..."
    )
    status_msg = await ctx.send(embed=status_embed)
    
    created_count = 0
    skipped_count = 0
    failed_count = 0
    
    for guild in target_servers:
        try:
            # Check if category already exists
            category_name = f"{sanitize_server_name(guild.name)}-logs"
            existing_category = discord.utils.get(central_guild.categories, name=category_name)
            
            if existing_category:
                skipped_count += 1
                continue
            
            # Create logging setup for this server
            guild_info = {
                'name': guild.name,
                'id': guild.id,
                'member_count': guild.member_count,
                'created_at': guild.created_at
            }
            
            logging_setup = await create_server_logging_category(guild_info)
            
            if logging_setup:
                created_count += 1
                
                # Send welcome message to server logs channel
                server_logs_channel = logging_setup['channels']['server-logs']
                welcome_embed = discord.Embed(
                    title="📋 Backfilled Logging Setup",
                    description=f"Logging category created for **{guild.name}**",
                    color=0x00ff00,
                    timestamp=datetime.now()
                )
                welcome_embed.add_field(
                    name="📊 Server Info",
                    value=f"**Members:** {guild.member_count:,}\n"
                          f"**Created:** {guild.created_at.strftime('%B %d, %Y')}\n"
                          f"**ID:** {guild.id}",
                    inline=False
                )
                welcome_embed.set_footer(text="Backfilled by centralized logging system")
                await server_logs_channel.send(embed=welcome_embed)
            else:
                failed_count += 1
                
        except Exception as e:
            print(f"Failed to backfill logging for {guild.name}: {e}")
            failed_count += 1
    
    # Send completion status
    completion_embed = nova_embed(
        "✅ bACKFILL cOMPLETE!",
        f"**Created:** {created_count} new logging categories\n"
        f"**Skipped:** {skipped_count} (already exist)\n"
        f"**Failed:** {failed_count}\n\n"
        f"All existing servers now have centralized logging!"
    )
    await status_msg.edit(embed=completion_embed)
    
    # Log to overview channel if configured
    if CENTRAL_OVERVIEW_CHANNEL_ID:
        overview_channel = central_guild.get_channel(CENTRAL_OVERVIEW_CHANNEL_ID)
        if overview_channel:
            overview_embed = discord.Embed(
                title="🔄 Centralized Logging Backfill Complete",
                description=f"Processed {len(target_servers)} existing servers",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            overview_embed.add_field(
                name="📊 Results",
                value=f"✅ Created: {created_count}\n"
                      f"⏭️ Skipped: {skipped_count}\n"
                      f"❌ Failed: {failed_count}",
                inline=False
            )
            overview_embed.set_footer(text=f"Backfill initiated by {ctx.author}")
            await overview_channel.send(embed=overview_embed)

@bot.command()
async def listservers(ctx):
    """List all servers Nova is currently in (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("sERVER lIST", "oNLY tHE oWNER cAN vIEW tHIS!"))
        return
    
    servers = bot.guilds
    total_members = sum(guild.member_count for guild in servers)
    
    # Create main embed
    embed = discord.Embed(
        title="🏠 Nova's Server List",
        description=f"Nova is currently in **{len(servers)}** servers with **{total_members:,}** total members",
        color=0xff69b4,
        timestamp=datetime.now()
    )
    
    # Sort servers by member count (largest first)
    sorted_servers = sorted(servers, key=lambda g: g.member_count, reverse=True)
    
    # Split into chunks for multiple embeds if needed
    chunk_size = 10
    chunks = [sorted_servers[i:i + chunk_size] for i in range(0, len(sorted_servers), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            current_embed = embed
        else:
            current_embed = discord.Embed(
                title=f"🏠 Nova's Server List (Page {i+1})",
                color=0xff69b4,
                timestamp=datetime.now()
            )
        
        server_list = ""
        for guild in chunk:
            # Get join date
            join_date = "Unknown"
            if guild.me and guild.me.joined_at:
                join_date = guild.me.joined_at.strftime("%b %d, %Y")
            
            # Server info
            server_info = f"**{guild.name}**\n"
            server_info += f"├ Members: {guild.member_count:,}\n"
            server_info += f"├ ID: `{guild.id}`\n"
            server_info += f"├ Joined: {join_date}\n"
            server_info += f"└ Owner: {guild.owner.mention if guild.owner else 'Unknown'}\n\n"
            
            # Check if adding this server would exceed field limit
            if len(server_list + server_info) > 1024:
                current_embed.add_field(
                    name=f"📋 Servers {i*chunk_size + 1}-{i*chunk_size + len(server_list.split('**')) - 1}",
                    value=server_list,
                    inline=False
                )
                await ctx.send(embed=current_embed)
                
                # Start new embed
                current_embed = discord.Embed(
                    title=f"🏠 Nova's Server List (Continued)",
                    color=0xff69b4,
                    timestamp=datetime.now()
                )
                server_list = server_info
            else:
                server_list += server_info
        
        if server_list:
            current_embed.add_field(
                name=f"📋 Servers",
                value=server_list,
                inline=False
            )
        
        current_embed.set_footer(text=f"Total: {len(servers)} servers • {total_members:,} members")
        await ctx.send(embed=current_embed)

@bot.command()
async def leaveserver(ctx, server_id: int = None):
    """Make Nova leave a specific server (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("lEAVE sERVER", "oNLY tHE oWNER cAN dO tHIS!"))
        return
    
    if not server_id:
        await ctx.send(embed=nova_embed(
            "lEAVE sERVER",
            "Usage: `?leaveserver <server_id>`\n\nUse `?listservers` to see all servers and their IDs."
        ))
        return
    
    guild = bot.get_guild(server_id)
    if not guild:
        await ctx.send(embed=nova_embed("lEAVE sERVER", "❌ sERVER nOT fOUND!"))
        return
    
    # Confirm before leaving
    confirm_embed = nova_embed(
        "⚠️ cONFIRM lEAVE sERVER",
        f"Are you sure you want Nova to leave **{guild.name}**?\n\n"
        f"**Server Info:**\n"
        f"├ Members: {guild.member_count:,}\n"
        f"├ ID: `{guild.id}`\n"
        f"└ Owner: {guild.owner.mention if guild.owner else 'Unknown'}\n\n"
        f"React with ✅ to confirm or ❌ to cancel."
    )
    
    msg = await ctx.send(embed=confirm_embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
    
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        
        if str(reaction.emoji) == "✅":
            guild_name = guild.name
            await guild.leave()
            
            success_embed = nova_embed(
                "✅ lEFT sERVER",
                f"Nova has successfully left **{guild_name}**!"
            )
            await msg.edit(embed=success_embed)
            
        else:
            cancel_embed = nova_embed(
                "❌ cANCELLED",
                "Server leave cancelled."
            )
            await msg.edit(embed=cancel_embed)
            
    except asyncio.TimeoutError:
        timeout_embed = nova_embed(
            "⏰ tIMEOUT",
            "Confirmation timed out. Server leave cancelled."
        )
        await msg.edit(embed=timeout_embed)

@bot.command()
async def centralloggingstatus(ctx):
    """Check centralized logging system status (Owner only)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING", "oNLY tHE oWNER cAN vIEW tHIS!"))
        return
    
    if not CENTRAL_LOG_GUILD_ID:
        await ctx.send(embed=nova_embed("cENTRAL lOGGING sTATUS", "❌ nOT cONFIGURED yET!"))
        return
    
    # Check if all components are accessible
    central_guild = bot.get_guild(CENTRAL_LOG_GUILD_ID)
    overview_channel = central_guild.get_channel(CENTRAL_OVERVIEW_CHANNEL_ID) if central_guild else None
    archive_category = central_guild.get_channel(CENTRAL_ARCHIVE_CATEGORY_ID) if central_guild else None
    
    embed = discord.Embed(
        title="📊 Centralized Logging Status",
        color=0xff69b4,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="🏠 Logging Server",
        value=f"**Name:** {central_guild.name if central_guild else 'Not Found'}\n"
              f"**ID:** {CENTRAL_LOG_GUILD_ID}\n"
              f"**Status:** {'✅ Connected' if central_guild else '❌ Not Found'}",
        inline=False
    )
    
    embed.add_field(
        name="📢 Overview Channel",
        value=f"**Channel:** {overview_channel.mention if overview_channel else 'Not Found'}\n"
              f"**ID:** {CENTRAL_OVERVIEW_CHANNEL_ID}\n"
              f"**Status:** {'✅ Accessible' if overview_channel else '❌ Not Found'}",
        inline=True
    )
    
    embed.add_field(
        name="📦 Archive Category",
        value=f"**Category:** {archive_category.name if archive_category else 'Not Found'}\n"
              f"**ID:** {CENTRAL_ARCHIVE_CATEGORY_ID}\n"
              f"**Status:** {'✅ Accessible' if archive_category else '❌ Not Found'}",
        inline=True
    )
    
    embed.add_field(
        name="📈 Statistics",
        value=f"**Total Servers:** {len(bot.guilds)}\n"
              f"**Active Categories:** {len([cat for cat in central_guild.categories if cat.name.endswith('-logs')]) if central_guild else 0}\n"
              f"**Archived Channels:** {len(archive_category.channels) if archive_category else 0}",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Load config and initialize bot before running
load_config()
init_bot()

bot.run(TOKEN)