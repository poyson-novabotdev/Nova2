# =========================
# Imports and Setup
# =========================
import discord
from discord.ext import commands
import json
import random
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from discord import app_commands
import time
import requests
import re
import asyncio

# =========================
# Intents and Bot Instance
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

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

balances = {}
user_xp = {}
config = {}

beg_cooldowns = {}
work_cooldowns = {}
daily_cooldowns = {}

OWNER_ID = 755846396208218174

ROLE_MESSAGE_ID = None
EMOJI_TO_ROLE = {
    "💙": "mALE",
    "💗": "fEMALE",
    "🤍": "oTHER (AKS)"
}

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

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
}

INTERNATIONAL_DAYS.update({
    "01-03": "zERO dISCRIMINATION dAY",
    "03-03": "wORLD wILDLIFE dAY",
    "05-03": "iNTERNATIONAL dAY fOR dISARMAMENT aND nON-pROLIFERATION aWARENESS",
    "08-03": "iNTERNATIONAL wOMEN'S dAY",
    "10-03": "iNTERNATIONAL dAY oF wOMEN jUDGES",
    "15-03": "iNTERNATIONAL dAY tO cOMBAT iSLAMOPHOBIA",
    "20-03": "iNTERNATIONAL dAY oF hAPPINESS",
    "21-03": "wORLD dAY fOR gLACIERS",
    "21-03": "iNTERNATIONAL dAY fOR tHE eLIMINATION oF rACIAL dISCRIMINATION",
    "21-03": "iNTERNATIONAL dAY oF fORESTS",
    "21-03": "wORLD pOETRY dAY",
    "21-03": "iNTERNATIONAL dAY oF nOWRUZ",
    "21-03": "wORLD dOWN sYNDROME dAY",
    "22-03": "wORLD wATER dAY",
    "23-03": "wORLD mETEOROLOGICAL dAY",
    "24-03": "wORLD tUBERCULOSIS dAY",
    "24-03": "iNTERNATIONAL dAY fOR tHE rIGHT tO tHE tRUTH cONCERNING gROSS hUMAN rIGHTS vIOLATIONS aND fOR tHE dIGNITY oF vICTIMS",
    "25-03": "iNTERNATIONAL dAY oF rEMEMBRANCE oF tHE vICTIMS oF sLAVERY aND tHE tRANSATLANTIC sLAVE tRADE",
    "25-03": "iNTERNATIONAL dAY oF sOLIDARITY wITH dETAINED aND mISSING sTAFF mEMBERS",
    "30-03": "iNTERNATIONAL dAY oF zERO wASTE",
    "02-04": "wORLD aUTISM aWARENESS dAY",
    "04-04": "iNTERNATIONAL dAY fOR mINE aWARENESS aND aSSISTANCE iN mINE aCTION",
    "05-04": "iNTERNATIONAL dAY oF cONSCIENCE",
    "06-04": "iNTERNATIONAL dAY oF sPORT fOR dEVELOPMENT aND pEACE",
    "07-04": "wORLD hEALTH dAY",
    "07-04": "iNTERNATIONAL dAY oF rEFLECTION oN tHE 1994 gENOCIDE aGAINST tHE tUTSI iN rWANDA",
    "12-04": "iNTERNATIONAL dAY oF hUMAN sPACE fLIGHT",
    "14-04": "wORLD cHAGAS dISEASE dAY",
    "20-04": "cHINESE lANGUAGE dAY",
    "21-04": "wORLD cREATIVITY aND iNNOVATION dAY",
    "22-04": "iNTERNATIONAL mOTHER eARTH dAY",
    "23-04": "wORLD bOOK aND cOPYRIGHT dAY",
    "23-04": "eNGLISH lANGUAGE dAY",
    "23-04": "sPANISH lANGUAGE dAY",
    "24-04": "iNTERNATIONAL gIRLS iN iCT dAY",
    "24-04": "wORLD iMMUNIZATION wEEK",
    "24-04": "iNTERNATIONAL dAY oF mULTILATERALISM aND dIPLOMACY fOR pEACE",
    "25-04": "wORLD mALARIA dAY",
    "25-04": "iNTERNATIONAL dELEGATE'S dAY",
    "26-04": "iNTERNATIONAL cHERNOBYL dISASTER rEMEMBRANCE dAY",
    "26-04": "wORLD iNTELLECTUAL pROPERTY dAY",
    "28-04": "wORLD dAY fOR sAFETY aND hEALTH aT wORK",
    "29-04": "iNTERNATIONAL dAY iN mEMORY oF tHE vICTIMS oF eARTHQUAKES",
    "30-04": "iNTERNATIONAL jAZZ dAY",
    "02-05": "wORLD tUNA dAY",
    "03-05": "wORLD pRESS fREEDOM dAY",
    "05-05": "wORLD pORTUGUESE lANGUAGE dAY",
    "08-05": "tIME oF rEMEMBRANCE aND rECONCILIATION fOR tHOSE wHO lOST tHEIR lIVES dURING tHE sECOND wORLD wAR",
    "10-05": "iNTERNATIONAL dAY oF aRGANIA",
    "10-05": "wORLD mIGRATORY bIRD dAY",
    "10-05": "iNTERNATIONAL dAY oF pLANT hEALTH",
    "12-05": "uN gLOBAL rOAD sAFETY wEEK",
    "12-05": "vESAK, tHE dAY oF tHE fULL mOON",
    "12-05": "iNTERNATIONAL dAY oF fAMILIES",
    "15-05": "iNTERNATIONAL dAY oF lIVING tOGETHER iN pEACE",
    "16-05": "iNTERNATIONAL dAY oF lIGHT",
    "16-05": "wORLD tELECOMMUNICATION aND iNFORMATION sOCIETY dAY",
    "17-05": "wORLD fAIR pLAY dAY",
    "19-05": "wORLD bEE dAY",
    "20-05": "iNTERNATIONAL tEA dAY",
    "21-05": "wORLD dAY fOR cULTURAL dIVERSITY fOR dIALOGUE aND dEVELOPMENT",
    "22-05": "iNTERNATIONAL dAY fOR bIOLOGICAL dIVERSITY",
    "23-05": "iNTERNATIONAL dAY tO eND oBSTETRIC fISTULA",
    "24-05": "iNTERNATIONAL dAY oF tHE mARKHOR",
    "25-05": "wORLD fOOTBALL dAY",
    "25-05": "wEEK oF sOLIDARITY wITH tHE pEOPLES oF nON-sELF-gOVERNING tERRITORIES",
    "29-05": "iNTERNATIONAL dAY oF uN pEACEKEEPERS",
    "30-05": "iNTERNATIONAL dAY oF pOTATO",
    "31-05": "wORLD nO-tOBACCO dAY",
    "01-06": "gLOBAL dAY oF pARENTS",
    "03-06": "wORLD bICYCLE dAY",
    "04-06": "iNTERNATIONAL dAY oF iNNOCENT cHILDREN vICTIMS oF aGGRESSION",
    "05-06": "wORLD eNVIRONMENT dAY",
    "05-06": "iNTERNATIONAL dAY fOR tHE fIGHT aGAINST iLLEGAL, uNREPORTED aND uNREGULATED fISHING",
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
    "18-06": "iNTERNATIONAL dAY fOR cOUNTERING hATE sPEECH",
    "19-06": "iNTERNATIONAL dAY fOR tHE eLIMINATION oF sEXUAL vIOLENCE iN cONFLICT",
    "20-06": "wORLD rEFUGEE dAY",
    "21-06": "iNTERNATIONAL dAY oF yOGA",
    "21-06": "iNTERNATIONAL dAY oF tHE cELEBRATION oF tHE sOLSTICE",
    "23-06": "uN pUBLIC sERVICE dAY",
    "23-06": "iNTERNATIONAL wIDOWS' dAY",
    "24-06": "iNTERNATIONAL dAY oF wOMEN iN dIPLOMACY",
    "25-06": "dAY oF tHE sEAFARER",
    "26-06": "iNTERNATIONAL dAY aGAINST dRUG aBUSE aND iLLICIT tRAFFICKING",
    "26-06": "uN iNTERNATIONAL dAY iN sUPPORT oF vICTIMS oF tORTURE",
    "27-06": "iNTERNATIONAL dAY oF dEAFBLINDNESS",
    "27-06": "mICRO-, sMALL aND mEDIUM-sIZED eNTERPRISES dAY",
    "29-06": "iNTERNATIONAL dAY oF tHE tROPICS",
    "30-06": "iNTERNATIONAL aSTEROID dAY",
    "30-06": "iNTERNATIONAL dAY oF pARLIAMENTARISM",
    "05-07": "iNTERNATIONAL dAY oF cOOPERATIVES",
    "06-07": "wORLD rURAL dEVELOPMENT dAY",
    "07-07": "wORLD kISWAHILI lANGUAGE dAY",
    "11-07": "wORLD hORSE dAY",
    "11-07": "iNTERNATIONAL dAY oF rEFLECTION aND cOMMEMORATION oF tHE 1995 gENOCIDE iN sREBRENICA",
    "11-07": "wORLD pOPULATION dAY",
    "12-07": "iNTERNATIONAL dAY oF cOMbATING sAND aND dUST sTORMS",
    "12-07": "iNTERNATIONAL dAY oF hOPE",
    "12-07": "wORLD yOUTH sKILLS dAY",
    "15-07": "nELSON mANDELA iNTERNATIONAL dAY",
    "18-07": "wORLD cHESS dAY",
    "20-07": "iNTERNATIONAL mOON dAY",
    "20-07": "iNTERNATIONAL dAY oF wOMEN aND gIRLS oF aFRICAN dESCENT",
    "25-07": "wORLD dROWNING pREVENTION dAY",
    "25-07": "iNTERNATIONAL dAY oN jUDICIAL wELL-bEING",
    "28-07": "wORLD hEPATITIS dAY",
    "30-07": "iNTERNATIONAL dAY oF fRIENDSHIP",
    "30-07": "wORLD dAY aGAINST tRAFFICKING iN pERSONS",
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
    # November
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
    "20-11": "aFRICA iNDUSTRIALIZATION dAY",
    "20-11": "wORLD cHILDREN'S dAY",
    "20-11": "wORLD tELEVISION dAY",
    "21-11": "wORLD cONJOINED tWINS dAY",
    "24-11": "iNTERNATIONAL dAY fOR tHE eLIMINATION oF vIOLENCE aGAINST wOMEN",
    "25-11": "wORLD sUSTAINABLE tRANSPORT dAY",
    "26-11": "iNTERNATIONAL dAY oF sOLIDARITY wITH tHE pALESTINIAN pEOPLE",
    "29-11": "dAY oF rEMEMBRANCE fOR aLL vICTIMS oF cHEMICAL wARFARE",
    "30-11": "iNTERNATIONAL dAY 334",
    # December
    "01-12": "wORLD aIDS dAY",
    "02-12": "iNTERNATIONAL dAY fOR tHE aBOLITION oF sLAVERY",
    "03-12": "iNTERNATIONAL dAY oF pERSONS wITH dISABILITIES",
    "04-12": "iNTERNATIONAL dAY oF bANKS",
    "05-12": "iNTERNATIONAL dAY aGAINST uNILATERAL cOERCIVE mEASURES",
    "05-12": "iNTERNATIONAL vOLUNTEER dAY fOR eCONOMIC aND sOCIAL dEVELOPMENT",
    "07-12": "wORLD sOIL dAY",
    "07-12": "iNTERNATIONAL cIVIL aVIATION dAY",
    "09-12": "iNTERNATIONAL dAY oF cOMMEMORATION aND dIGNITY oF tHE vICTIMS oF tHE cRIME oF gENOCIDE aND oF tHE pREVENTION oF tHIS cRIME",
    "09-12": "iNTERNATIONAL aNTI-cORRUPTION dAY",
    "10-12": "hUMAN rIGHTS dAY",
    "11-12": "iNTERNATIONAL mOUNTAIN dAY",
    "12-12": "iNTERNATIONAL dAY oF nEUTRALITY",
    "12-12": "iNTERNATIONAL uNIVERSAL hEALTH cOVERAGE dAY",
    "18-12": "iNTERNATIONAL mIGRANTS dAY",
    "18-12": "aRABIC lANGUAGE dAY",
    "20-12": "iNTERNATIONAL hUMAN sOLIDARITY dAY",
    "21-12": "wORLD mEDITATION dAY",
    "21-12": "wORLD bASKETBALL dAY",
    "27-12": "iNTERNATIONAL dAY oF ePIDEMIC pREPAREDNESS",
    "25-12": "cHRISTMAS dAY"
})

# =========================
# Helper Functions
# =========================

def load_config():
    """Load configuration from CONFIG_FILE into the global config dict."""
    global config
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {"mod_role_id": None, "admin_role_id": None}

def save_config():
    """Save the current config dict to CONFIG_FILE."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_balances():
    """Load user balances from DATA_FILE into the global balances dict."""
    global balances
    try:
        with open(DATA_FILE, "r") as f:
            balances = json.load(f)
    except FileNotFoundError:
        balances = {}

def save_balances():
    """Save the current balances dict to DATA_FILE."""
    with open(DATA_FILE, "w") as f:
        json.dump(balances, f)

def get_balance(user_id):
    """Get the balance for a user by their ID."""
    return balances.get(str(user_id), 0)

def change_balance(user_id, amount):
    """Change a user's balance by a given amount. Prevents negative balances."""
    user_id = str(user_id)
    balances[user_id] = balances.get(user_id, 0) + amount
    if balances[user_id] < 0:
        balances[user_id] = 0
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
    """Check if the user has mod or admin privileges or is the owner."""
    if ctx.author.id == OWNER_ID:
        return True
    mod_role_id = config.get("mod_role_id")
    admin_role_id = config.get("admin_role_id")
    user_role_ids = [role.id for role in ctx.author.roles]
    return (mod_role_id and mod_role_id in user_role_ids) or (admin_role_id and admin_role_id in user_role_ids)

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

# Example usage in commands:
# await ctx.send(embed=nova_embed("TITLE", "description"))
# await interaction.response.send_message(embed=nova_embed("TITLE", "description"))

# =========================
# Event Handlers
# =========================

@bot.event
async def on_ready():
    """Event: Called when the bot is ready."""
    load_config()
    load_balances()
    load_xp()
    print(f"{bot.user} is online and ready!")

@bot.event
async def on_message(message):
    """Event: Called on every message. Adds XP and processes commands."""
    if message.author.bot:
        return
    # AFK auto-return
    if message.author.id in AFK_STATUS:
        del AFK_STATUS[message.author.id]
        await message.channel.send(embed=nova_embed("aFK", f"wELCOME bACK, {message.author.display_name}!"))
    # AFK mention check
    mentioned_ids = [user.id for user in message.mentions]
    for uid in mentioned_ids:
        if uid in AFK_STATUS:
            reason = AFK_STATUS[uid]
            member = message.guild.get_member(uid)
            if member:
                await message.channel.send(embed=nova_embed("aFK", f"{member.display_name} iS aFK: {reason}"))
    add_xp(message.author.id, random.randint(5, 15))
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
    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    """Event: Called when a reaction is added. Handles role assignment."""
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
    """Event: Called when a reaction is removed. Handles role removal."""
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
async def help(ctx):
    help_text = """
Prefix & Slash Commands:
/balance, /beg, /daily, /work, /pay, /shop, /buy, /inventory
/setbday, /birthday, /birthdays, /today, /welcome, /rules, /ping, /about, /uptime
/marry, /divorce, /adopt, /emancipate, /familytree, /kiss, /slap, /whoasked, /afk
/mute, /unmute, /case, /snipe, /edsnipe, /slowmode, /lock, /unlock
/reactionroles, /nicki, /level, /leaderboard, /spotify
"""
    await ctx.send(embed=nova_embed("nOVA'S cOMMANDS", help_text))

@bot.tree.command(name="help", description="Show all Nova commands")
async def help_slash(interaction: discord.Interaction):
    help_text = """
Prefix & Slash Commands:
/balance, /beg, /daily, /work, /pay, /shop, /buy, /inventory
/setbday, /birthday, /birthdays, /today, /welcome, /rules, /ping, /about, /uptime
/marry, /divorce, /adopt, /emancipate, /familytree, /kiss, /slap, /whoasked, /afk
/mute, /unmute, /case, /snipe, /edsnipe, /slowmode, /lock, /unlock
/reactionroles, /nicki, /level, /leaderboard, /spotify
"""
    await interaction.response.send_message(embed=nova_embed("nOVA'S cOMMANDS", help_text))

@bot.command()
async def balance(ctx):
    """Check your dOLLARIANAS balance."""
    bal = get_balance(ctx.author.id)
    await ctx.send(f"{ctx.author.mention}, you have {bal} {CURRENCY_NAME}.")

# Slash command version of balance
@bot.tree.command(name="balance", description="Check your dOLLARIANAS balance (slash command)")
async def balance_slash(interaction: discord.Interaction):
    bal = get_balance(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}, you have {bal} {CURRENCY_NAME}.")

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
    lyric = random.choice(lyrics)
    embed = discord.Embed(
        title="nICKI mINAJ lYRIC",
        description=lyric,
        color=0xff69b4
    )
    embed.set_footer(text="nOVA sAYS: sLAY! 💅")
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
            await ctx.send(embed=embed)
            return
    await ctx.send(f"{member.display_name} is not listening to Spotify right now.")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is online and commands synced!")

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
    now = datetime.now(timezone.utc)
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

# Slash command version of daily
@bot.tree.command(name="daily", description="Claim daily reward (24h cooldown)")
async def daily_slash(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    user_id = interaction.user.id
    last = daily_cooldowns.get(user_id)
    if last and now - last < timedelta(hours=24):
        rem = timedelta(hours=24) - (now - last)
        await interaction.response.send_message(f"{interaction.user.mention}, you can claim your daily reward in {str(rem).split('.')[0]}", ephemeral=True)
        return
    change_balance(user_id, 100)
    daily_cooldowns[user_id] = now
    await interaction.response.send_message(f"{interaction.user.mention}, you claimed your daily 100 {CURRENCY_NAME}!")

# Slash command version of work
@bot.tree.command(name="work", description="Work a job to earn money (20 min cooldown)")
async def work_slash(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
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

# Slash command version of clear
@bot.tree.command(name="clear", description="Delete messages (mods only)")
@app_commands.describe(amount="Number of messages to delete (default 5)")
async def clear_slash(interaction: discord.Interaction, amount: int = 5):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"Cleared {len(deleted)} messages", ephemeral=True)

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
            await interaction.response.send_message(embed=embed)
            return
    await interaction.response.send_message(f"{member.display_name} is not listening to Spotify right now.")

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
    key = f"adopted:{ctx.author.id}"
    if key in relationships:
        await ctx.send(embed=nova_embed("aDOPT", "yOU'VE aLREADY aDOPTED sOMEONE!"))
        return
    if user.id in pending_adoptions:
        await ctx.send(embed=nova_embed("aDOPT", "tHAT uSER aLREADY hAS a pENDING aDOPTION!"))
        return
    pending_adoptions[user.id] = ctx.author.id
    await ctx.send(embed=nova_embed("aDOPT", f"🍼 {ctx.author.display_name} wANTS tO aDOPT {user.display_name}! {user.mention}, tYPE `?acceptadopt` tO aCCEPT. yOU hAVE 30 sECONDS!"))
    async def expire():
        await asyncio.sleep(30)
        if user.id in pending_adoptions and pending_adoptions[user.id] == ctx.author.id:
            del pending_adoptions[user.id]
            await ctx.send(embed=nova_embed("aDOPT", f"{user.display_name} dIDN'T rESPOND iN tIME! tRY aGAIN lATER."))
    ctx.bot.loop.create_task(expire())

@bot.tree.command(name="adopt", description="Adopt a user (fun roleplay)")
@app_commands.describe(user="The user to adopt")
async def adopt_slash(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message(embed=nova_embed("aDOPT", "yOU cAN'T aDOPT yOURSELF!"))
        return
    relationships = load_relationships()
    key = f"adopted:{interaction.user.id}"
    if key in relationships:
        await interaction.response.send_message(embed=nova_embed("aDOPT", "yOU'VE aLREADY aDOPTED sOMEONE!"))
        return
    if user.id in pending_adoptions:
        await interaction.response.send_message(embed=nova_embed("aDOPT", "tHAT uSER aLREADY hAS a pENDING aDOPTION!"))
        return
    pending_adoptions[user.id] = interaction.user.id
    await interaction.response.send_message(embed=nova_embed("aDOPT", f"🍼 {interaction.user.display_name} wANTS tO aDOPT {user.display_name}! {user.mention}, uSE `/acceptadopt` tO aCCEPT. yOU hAVE 30 sECONDS!"))
    async def expire():
        await asyncio.sleep(30)
        if user.id in pending_adoptions and pending_adoptions[user.id] == interaction.user.id:
            del pending_adoptions[user.id]
            await interaction.followup.send(embed=nova_embed("aDOPT", f"{user.display_name} dIDN'T rESPOND iN tIME! tRY aGAIN lATER."))
    interaction.client.loop.create_task(expire())

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

# AFK
AFK_STATUS = {}

@bot.command()
async def afk(ctx, *, reason: str = "aFK"): 
    AFK_STATUS[ctx.author.id] = reason
    await ctx.send(embed=nova_embed("aFK", f"{ctx.author.display_name} iS nOW aFK: {reason}"))

@bot.tree.command(name="afk", description="Set your AFK status with an optional message")
@app_commands.describe(reason="Why are you AFK?")
async def afk_slash(interaction: discord.Interaction, reason: str = "aFK"):
    AFK_STATUS[interaction.user.id] = reason
    await interaction.response.send_message(embed=nova_embed("aFK", f"{interaction.user.display_name} iS nOW aFK: {reason}"), ephemeral=True)

@bot.event
async def on_mention(message):
    if message.author.bot:
        return
    mentioned_ids = [user.id for user in message.mentions]
    for uid in mentioned_ids:
        if uid in AFK_STATUS:
            reason = AFK_STATUS[uid]
            member = message.guild.get_member(uid)
            if member:
                await message.channel.send(embed=nova_embed("aFK", f"{member.display_name} iS aFK: {reason}"))

# Moderation
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
    overwrite = ctx.channel.overwrites_for(member)
    if overwrite.send_messages is False:
        await ctx.send(embed=nova_embed("mUTE", f"{member.mention} iS aLREADY mUTED hERE!"))
        return
    overwrite.send_messages = False
    await ctx.channel.set_permissions(member, overwrite=overwrite)
    await ctx.send(embed=nova_embed("mUTE", f"{member.mention} hAS bEEN mUTED iN {ctx.channel.mention}!"))

@bot.tree.command(name="mute", description="Mute a member in this channel (admin only)")
@app_commands.describe(member="Member to mute")
async def mute_slash(interaction: discord.Interaction, member: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("mUTE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message(embed=nova_embed("mUTE", "nICE tRY, bUT yOU cAN'T mUTE yOURSELF!"), ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(member)
    if overwrite.send_messages is False:
        await interaction.response.send_message(embed=nova_embed("mUTE", f"{member.mention} iS aLREADY mUTED hERE!"), ephemeral=True)
        return
    overwrite.send_messages = False
    await interaction.channel.set_permissions(member, overwrite=overwrite)
    await interaction.response.send_message(embed=nova_embed("mUTE", f"{member.mention} hAS bEEN mUTED iN {interaction.channel.mention}!"))

@bot.command()
async def unmute(ctx, member: discord.Member = None):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("uNMUTE", "yOU dON'T hAVE pERMISSION!"))
        return
    if not member:
        await ctx.send(embed=nova_embed("uNMUTE", "yOU nEED tO mENTION sOMEONE!"))
        return
    overwrite = ctx.channel.overwrites_for(member)
    if overwrite.send_messages is not False:
        await ctx.send(embed=nova_embed("uNMUTE", f"{member.mention} iS nOT mUTED hERE!"))
        return
    overwrite.send_messages = None
    await ctx.channel.set_permissions(member, overwrite=overwrite)
    await ctx.send(embed=nova_embed("uNMUTE", f"{member.mention} hAS bEEN uNMUTED iN {ctx.channel.mention}!"))

@bot.tree.command(name="unmute", description="Unmute a member in this channel (admin only)")
@app_commands.describe(member="Member to unmute")
async def unmute_slash(interaction: discord.Interaction, member: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("uNMUTE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(member)
    if overwrite.send_messages is not False:
        await interaction.response.send_message(embed=nova_embed("uNMUTE", f"{member.mention} iS nOT mUTED hERE!"), ephemeral=True)
        return
    overwrite.send_messages = None
    await interaction.channel.set_permissions(member, overwrite=overwrite)
    await interaction.response.send_message(embed=nova_embed("uNMUTE", f"{member.mention} hAS bEEN uNMUTED iN {interaction.channel.mention}!"))

@bot.command()
async def case(ctx):
    cases = mod_cases.get(ctx.guild.id, [])
    if not cases:
        await ctx.send(embed=nova_embed("cASES", "nO mOD cASES yET!"))
        return
    desc = ""
    for i, c in enumerate(cases, 1):
        desc += f"**{i}.** `{c['action']}` by {c['user']} in {c['channel']} • {c['time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    await ctx.send(embed=nova_embed("cASES", desc))

@bot.tree.command(name="case", description="Show all moderation actions in this server (up to 20)")
async def case_slash(interaction: discord.Interaction):
    cases = mod_cases.get(interaction.guild.id, [])
    if not cases:
        await interaction.response.send_message(embed=nova_embed("cASES", "nO mOD cASES yET!"), ephemeral=True)
        return
    desc = ""
    for i, c in enumerate(cases, 1):
        desc += f"**{i}.** `{c['action']}` by {c['user']} in {c['channel']} • {c['time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    await interaction.response.send_message(embed=nova_embed("cASES", desc))

@bot.command()
async def snipe(ctx):
    data = snipes.get(ctx.channel.id)
    if not data:
        await ctx.send(embed=nova_embed("sNIPE", "nOTHING tO sNIPE!"))
        return
    embed = nova_embed("sNIPE", data['content'])
    embed.set_footer(text=f"{data['author']} • {data['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    await ctx.send(embed=embed)

@bot.tree.command(name="snipe", description="Show the last deleted message in this channel")
async def snipe_slash(interaction: discord.Interaction):
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

@bot.tree.command(name="slowmode", description="Set slowmode in the current channel (admin only)")
@app_commands.describe(seconds="Number of seconds for slowmode")
async def slowmode_slash(interaction: discord.Interaction, seconds: int = 0):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("sLOWMODE", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=nova_embed("sLOWMODE", f"sLOWMODE sET tO {seconds} sECONDS iN {interaction.channel.mention}!"))

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
        await ctx.send(f"{user.display_name}'s birthday is {bday}!")
    else:
        await ctx.send(f"No birthday set for {user.display_name}.")

@bot.command()
async def bday(ctx, user: discord.Member = None, date: str = None):
    await ctx.send("Birthday shortcut feature coming soon!")

@bot.command()
async def setbday(ctx, date: str):
    """Set your birthday. Usage: ?setbday DD-MM"""
    # Basic validation
    try:
        day, month = map(int, date.split("-"))
        assert 1 <= month <= 12
        assert 1 <= day <= 31
    except Exception:
        await ctx.send("Please use the format DD-MM, e.g. 15-04 for April 15th.")
        return
    birthdays = load_birthdays()
    birthdays[str(ctx.author.id)] = date
    save_birthdays(birthdays)
    await ctx.send(f"Birthday set to {date}!")

@bot.command()
async def setbirthday(ctx, *, date: str):
    await ctx.send("Set birthday (alias) feature coming soon!")

@bot.command()
async def birthdays(ctx):
    """List all birthdays in the server."""
    birthdays = load_birthdays()
    if not birthdays:
        await ctx.send("No birthdays set yet!")
        return
    lines = []
    for user_id, date in birthdays.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            lines.append(f"{member.display_name}: {date}")
    if lines:
        await ctx.send("**Server Birthdays:**\n" + "\n".join(lines))
    else:
        await ctx.send("No birthdays set for current server members.")

@bot.command()
async def today(ctx):
    """Shows today's international day, Nova style, in a vibrant embed."""
    from datetime import datetime
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
async def jail(ctx, user: discord.Member):
    if not has_mod_or_admin(ctx):
        await ctx.send(embed=nova_embed("jAIL", "yOU dON'T hAVE pERMISSION!"))
        return
    if JAIL_CHANNEL_ID is None:
        await ctx.send(embed=nova_embed("jAIL", "jAIL cHANNEL nOT sET!"))
        return
    try:
        jail_channel = ctx.guild.get_channel(JAIL_CHANNEL_ID)
        if not jail_channel:
            await ctx.send(embed=nova_embed("jAIL", "cOULD nOT fIND tHE jAIL cHANNEL!"))
            return
        await user.move_to(jail_channel) if hasattr(user, 'move_to') else None
        overwrite = discord.PermissionOverwrite(send_messages=False, speak=False)
        await jail_channel.set_permissions(user, overwrite=overwrite)
        await ctx.send(embed=nova_embed("jAIL", f"{user.mention} hAS bEEN jAILED!"))
    except Exception:
        await ctx.send(embed=nova_embed("jAIL", "cOULD nOT jAIL tHAT uSER!"))

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
        await user.move_to(jail_channel) if hasattr(user, 'move_to') else None
        overwrite = discord.PermissionOverwrite(send_messages=False, speak=False)
        await jail_channel.set_permissions(user, overwrite=overwrite)
        await interaction.response.send_message(embed=nova_embed("jAIL", f"{user.mention} hAS bEEN jAILED!"))
    except Exception:
        await interaction.response.send_message(embed=nova_embed("jAIL", "cOULD nOT jAIL tHAT uSER!"), ephemeral=True)

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
    if JAIL_CHANNEL_ID is None:
        await ctx.send(embed=nova_embed("uNJAIL", "jAIL cHANNEL nOT sET!"))
        return
    try:
        jail_channel = ctx.guild.get_channel(JAIL_CHANNEL_ID)
        if not jail_channel:
            await ctx.send(embed=nova_embed("uNJAIL", "cOULD nOT fIND tHE jAIL cHANNEL!"))
            return
        await jail_channel.set_permissions(user, overwrite=None)
        await ctx.send(embed=nova_embed("uNJAIL", f"{user.mention} hAS bEEN uNJAILed!"))
    except Exception:
        await ctx.send(embed=nova_embed("uNJAIL", "cOULD nOT uNJAIL tHAT uSER!"))

@bot.tree.command(name="unjail", description="Remove a user from jail (admin/mod only)")
@app_commands.describe(user="The user to unjail")
async def unjail_slash(interaction: discord.Interaction, user: discord.Member):
    ctx = await bot.get_context(interaction)
    if not has_mod_or_admin(ctx):
        await interaction.response.send_message(embed=nova_embed("uNJAIL", "yOU dON'T hAVE pERMISSION!"), ephemeral=True)
        return
    if JAIL_CHANNEL_ID is None:
        await interaction.response.send_message(embed=nova_embed("uNJAIL", "jAIL cHANNEL nOT sET!"), ephemeral=True)
        return
    try:
        jail_channel = interaction.guild.get_channel(JAIL_CHANNEL_ID)
        if not jail_channel:
            await interaction.response.send_message(embed=nova_embed("uNJAIL", "cOULD nOT fIND tHE jAIL cHANNEL!"), ephemeral=True)
            return
        await jail_channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=nova_embed("uNJAIL", f"{user.mention} hAS bEEN uNJAILed!"))
    except Exception:
        await interaction.response.send_message(embed=nova_embed("uNJAIL", "cOULD nOT uNJAIL tHAT uSER!"), ephemeral=True)

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

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    snipes[message.channel.id] = {
        'content': message.content,
        'author': str(message.author),
        'time': message.created_at
    }

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    edsnipes[before.channel.id] = {
        'content': before.content,
        'author': str(before.author),
        'time': before.edited_at or before.created_at
    }

# Store moderation cases per guild
mod_cases = {}

def log_case(guild_id, action, user, channel, time):
    if guild_id not in mod_cases:
        mod_cases[guild_id] = []
    mod_cases[guild_id].insert(0, {
        'action': action,
        'user': str(user),
        'channel': str(channel),
        'time': time
    })
    if len(mod_cases[guild_id]) > 20:
        mod_cases[guild_id] = mod_cases[guild_id][:20]

bot.run(TOKEN)
