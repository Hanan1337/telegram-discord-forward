import os
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Variabel global
API_ID = None
API_HASH = None
PHONE = None
ADMINS = []
TARGET_CHANNEL = None
GOOGLE_API_KEY = None
DISCORD_AUTH_TOKEN = None
DISCORD_THREAD_ID = None

FILTERED_CHANNELS = []
UNFILTERED_CHANNELS = []
VIP_CHANNELS = []
SUMMARY_CHANNELS = []
KEYWORDS = []
SUMMARY_KEYWORDS = []  # Tambahkan variabel untuk keyword khusus summary

def load_env():
    """Memuat variabel lingkungan dari file .env."""
    global API_ID, API_HASH, PHONE, ADMINS, TARGET_CHANNEL, GOOGLE_API_KEY, DISCORD_AUTH_TOKEN, DISCORD_THREAD_ID
    load_dotenv()
    
    api_id_str = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    admins = os.getenv('ADMINS', '')
    target_channel = os.getenv('TARGET_CHANNEL')
    google_api_key = os.getenv('GOOGLE_API_KEY')
    discord_auth_token = os.getenv('DISCORD_AUTH_TOKEN')
    discord_thread_id = os.getenv('DISCORD_THREAD_ID')
    
    required_vars = {
        'TELEGRAM_API_ID': api_id_str,
        'TELEGRAM_API_HASH': api_hash,
        'TELEGRAM_PHONE': phone,
        'TARGET_CHANNEL': target_channel,
        'DISCORD_AUTH_TOKEN': discord_auth_token,
        'DISCORD_THREAD_ID': discord_thread_id
    }
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Variabel wajib berikut kosong di .env: {', '.join(missing_vars)}")
    
    try:
        API_ID = int(api_id_str)
    except (ValueError, TypeError):
        raise ValueError("TELEGRAM_API_ID harus berupa angka integer.")
    
    API_HASH = api_hash
    PHONE = phone
    ADMINS = [admin.strip() for admin in admins.split(',') if admin.strip()]
    TARGET_CHANNEL = target_channel
    GOOGLE_API_KEY = google_api_key
    DISCORD_AUTH_TOKEN = discord_auth_token
    DISCORD_THREAD_ID = discord_thread_id

def setup_logging():
    """Mengatur logging untuk aplikasi dengan rotasi file."""
    handler = RotatingFileHandler('telegram_forwarder.log', maxBytes=5*1024*1024, backupCount=5)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    logger = logging.getLogger('telegram_forwarder')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(console_handler)
    
    return logger

def load_config():
    """Memuat konfigurasi dari channels.json, keywords.json, dan summary_keywords.json."""
    global FILTERED_CHANNELS, UNFILTERED_CHANNELS, VIP_CHANNELS, SUMMARY_CHANNELS, KEYWORDS, SUMMARY_KEYWORDS
    try:
        with open('channels.json', 'r') as f:
            channels_data = json.load(f)
            FILTERED_CHANNELS = [int(ch) for ch in channels_data.get('FILTERED_CHANNELS', [])]
            UNFILTERED_CHANNELS = [int(ch) for ch in channels_data.get('UNFILTERED_CHANNELS', [])]
            VIP_CHANNELS = [int(ch) for ch in channels_data.get('VIP_CHANNELS', [])]
            SUMMARY_CHANNELS = [int(ch) for ch in channels_data.get('SUMMARY_CHANNELS', [])]
            
            for ch in FILTERED_CHANNELS + UNFILTERED_CHANNELS + VIP_CHANNELS + SUMMARY_CHANNELS:
                if ch > 0:
                    logger.warning(f"ID channel {ch} positif, seharusnya negatif untuk channel Telegram.")
            
            logger.info(f"Loaded channels: FILTERED={FILTERED_CHANNELS}, UNFILTERED={UNFILTERED_CHANNELS}, VIP={VIP_CHANNELS}, SUMMARY={SUMMARY_CHANNELS}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading channels.json: {str(e)}")
        FILTERED_CHANNELS = []
        UNFILTERED_CHANNELS = []
        VIP_CHANNELS = []
        SUMMARY_CHANNELS = []

    try:
        with open('keywords.json', 'r') as f:
            keywords_data = json.load(f)
            KEYWORDS = [str(kw).strip() for kw in keywords_data.get('KEYWORDS', [])]
            logger.info(f"Loaded keywords: {KEYWORDS}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading keywords.json: {str(e)}")
        KEYWORDS = []

    try:
        with open('summary_keywords.json', 'r') as f:
            summary_keywords_data = json.load(f)
            SUMMARY_KEYWORDS = [str(kw).strip() for kw in summary_keywords_data.get('SUMMARY_KEYWORDS', [])]
            logger.info(f"Loaded summary keywords: {SUMMARY_KEYWORDS}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading summary_keywords.json: {str(e)}")
        SUMMARY_KEYWORDS = []

# Inisialisasi saat modul diimpor
load_env()
logger = setup_logging()
load_config()
