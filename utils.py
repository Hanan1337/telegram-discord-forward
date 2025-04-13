# utils.py
import re
import aiohttp
import requests
from langdetect import detect
from config import GOOGLE_API_KEY, logger
from telethon.errors import SessionPasswordNeededError

def extract_username(input_str):
    """
    Mengekstrak nama pengguna dari string input, menghapus '@' atau mengekstrak dari URL Telegram.
    
    Args:
        input_str: String input (username atau URL).
    
    Returns:
        str: Nama pengguna yang telah diekstrak, atau None jika input tidak valid.
    """
    if not isinstance(input_str, str):
        logger.error(f"Input untuk extract_username bukan string: {input_str}")
        return None
    if input_str.startswith('@'):
        return input_str[1:]
    url_pattern = r'https?://t\.me/(\w+)'
    match = re.search(url_pattern, input_str)
    if match:
        return match.group(1)
    return input_str

def contains_keyword(text, keywords):
    """
    Memeriksa apakah teks mengandung salah satu kata kunci.
    
    Args:
        text (str): Teks yang akan diperiksa.
        keywords (list): Daftar kata kunci.
    
    Returns:
        bool: True jika kata kunci ditemukan, False jika tidak.
    """
    if not text or not keywords:
        logger.warning("Teks atau kata kunci kosong.")
        return False
    
    text_lower = text.lower().strip()
    for keyword in keywords:
        keyword_clean = keyword.lower().strip()
        # Gunakan pencocokan kata utuh untuk menghindari false positive
        if re.search(r'\b' + re.escape(keyword_clean) + r'\b', text_lower):
            logger.info(f"Kata kunci '{keyword}' ditemukan di pesan: {text}")
            return True
    
    logger.info(f"Tidak ada kata kunci yang cocok di pesan: {text}")
    return False

def guess_blocked_keywords(text):
    """
    Mencoba menduga keyword yang mungkin diblokir dalam pesan.
    
    Args:
        text (str): Teks pesan.
    
    Returns:
        list: Daftar kata atau frasa yang mungkin diblokir.
    """
    if not text:
        return []

    # Daftar pola yang sering dianggap mencurigakan
    suspicious_patterns = [
        r'(https?://[^\s]+)',  # Tautan
        r'\b[A-Z]{2,}\b',      # Kata semua huruf besar (misalnya, CZ, DOJ)
        r'\b\w+\.\w+\b',       # Domain seperti velo.xyz
        r'\b[\w-]+\b'          # Kata umum (diambil terakhir)
    ]

    suspicious_keywords = []
    text_lower = text.lower()

    # Cek pola mencurigakan
    for pattern in suspicious_patterns[:3]:  # Prioritaskan tautan, huruf besar, domain
        matches = re.findall(pattern, text, re.IGNORECASE)
        suspicious_keywords.extend(matches)

    # Jika tidak ada yang ditemukan, cek kata umum
    if not suspicious_keywords:
        words = re.findall(r'\b[\w-]+\b', text_lower)
        # Ambil kata yang lebih panjang dari 3 huruf untuk mengurangi noise
        suspicious_keywords.extend(word for word in words if len(word) > 3)

    # Hapus duplikasi dan batasi jumlah
    suspicious_keywords = list(dict.fromkeys(suspicious_keywords))[:5]
    logger.info(f"Dugaan keyword yang diblokir: {suspicious_keywords}")
    return suspicious_keywords

def remove_markdown(text):
    """
    Menghapus simbol markdown dari teks.
    
    Args:
        text (str): Teks yang akan dibersihkan.
    
    Returns:
        str: Teks tanpa simbol markdown.
    """
    if not text:
        return ""
    
    # Hapus simbol markdown
    text = re.sub(r'\*\*', '', text)  # Hapus **
    text = re.sub(r'\*', '', text)    # Hapus *
    text = re.sub(r'__', '', text)    # Hapus __
    text = re.sub(r'_', '', text)     # Hapus _
    text = re.sub(r'~~', '', text)    # Hapus ~~
    text = re.sub(r'`', '', text)     # Hapus `
    text = re.sub(r'```', '', text)   # Hapus ```
    
    return text.strip()

async def translate_text(text, target_lang="id"):
    """
    Menerjemahkan teks ke bahasa target menggunakan beberapa API terjemahan.
    
    Args:
        text (str): Teks yang akan diterjemahkan.
        target_lang (str): Kode bahasa target (default: 'id').
    
    Returns:
        str: Teks yang telah diterjemahkan, atau teks asli jika gagal.
    """
    try:
        if not text or detect(text) == "id":
            logger.info(f"Teks sudah dalam bahasa Indonesia atau kosong: {text}")
            return text
        
        # API Utama: Wordvice AI
        url = "https://sysapi.wordvice.ai/tools/non-member/fetch-llm-result"
        payload = {
            "prompt": "Translate the following English text into Indonesian.",
            "text": text,
            "tool": "translate"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "accept-language": "en-US,en;q=0.9",
            "origin": "https://wordvice.ai",
            "referer": "https://wordvice.ai/"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    raise Exception(f"Wordvice API error: {response.status}")
                data = await response.json()
                if data.get("code") == "0000":
                    translated_text = data["result"][0]["text"]
                    logger.info(f"Terjemahan Wordvice AI berhasil: {translated_text}")
                    return translated_text
                else:
                    raise Exception(f"API error: {data.get('message')}")
    
    except Exception as e:
        logger.error(f"Terjemahan Wordvice AI gagal: {str(e)}, mencoba MachineTranslation...")
        
        # Cadangan Pertama: MachineTranslation (Lingvanex)
        try:
            url = "https://api.machinetranslation.com/v1/translation/lingvanex"
            payload = {
                "text": text,
                "source_language_code": "en",
                "target_language_code": target_lang,
                "share_id": "19bd9373-bb23-4d01-aa07-5cea4218eb37"
            }
            headers = {
                'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
                'Accept': "application/json, text/plain, */*",
                'Accept-Encoding': "gzip, deflate, br, zstd",
                'Content-Type': "application/json",
                'sec-ch-ua-platform': "\"Android\"",
                'sec-ch-ua': "\"Brave\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
                'sec-ch-ua-mobile': "?1",
                'Sec-GPC': "1",
                'Accept-Language': "en-US,en;q=0.5",
                'Origin': "https://www.machinetranslation.com",
                'Sec-Fetch-Site': "same-site",
                'Sec-Fetch-Mode': "cors",
                'Sec-Fetch-Dest': "empty",
                'Referer': "https://www.machinetranslation.com/"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        raise Exception(f"MachineTranslation API error: {response.status}")
                    data = await response.json()
                    translated_text = data["response"]["translated_text"]
                    logger.info(f"Terjemahan MachineTranslation berhasil: {translated_text}")
                    return translated_text
        
        except Exception as e:
            logger.error(f"Terjemahan MachineTranslation gagal: {str(e)}, mencoba Google Translate...")
            
            # Cadangan Kedua: Google Translate
            try:
                if GOOGLE_API_KEY:
                    url = f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
                    payload = {"q": text, "target": target_lang, "format": "text"}
                    response = requests.post(url, json=payload)
                    response.raise_for_status()
                    translated_text = response.json()["data"]["translations"][0]["translatedText"]
                    logger.info(f"Terjemahan Google Translate berhasil: {translated_text}")
                    return translated_text
                else:
                    logger.warning("Tidak ada kunci API cadangan untuk Google Translate.")
                    return text
            except Exception as fallback_e:
                logger.critical(f"Semua API terjemahan gagal: {str(fallback_e)}")
                return text

async def login(client, code_queue):
    """
    Melakukan login ke klien Telegram menggunakan kode verifikasi dari antrian.
    
    Args:
        client: Objek TelegramClient.
        code_queue: Antrian asinkron untuk kode verifikasi.
    """
    from config import PHONE
    try:
        await client.start(phone=PHONE)
        if not await client.is_user_authorized():
            logger.info("Memulai proses login...")
            logger.info("Kirim kode verifikasi (5 digit) ke bot melalui pesan.")
            code = await code_queue.get()  # Tunggu kode dari antrian
            try:
                await client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                logger.info("Akun memerlukan kata sandi 2FA.")
                password = input("Masukkan kata sandi 2FA kamu: ")  # Ganti jika diperlukan
                await client.sign_in(password=password)
            logger.info("Login berhasil!")
    except Exception as e:
        logger.critical(f"Login gagal: {str(e)}")
        raise

async def shutdown_client(client):
    """
    Menghentikan klien Telegram dengan aman.
    
    Args:
        client: Objek TelegramClient.
    """
    logger.info("Menghentikan klien...")
    try:
        await client.disconnect()
        logger.info("Klien berhenti.")
    except Exception as e:
        logger.critical(f"Gagal menghentikan klien: {str(e)}")
        raise
