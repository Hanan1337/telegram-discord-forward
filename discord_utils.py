import aiohttp
import asyncio
import time
from config import DISCORD_AUTH_TOKEN, DISCORD_THREAD_ID, setup_logging

logger = setup_logging()

async def send_message_to_discord_thread(message):
    """
    Mengirim pesan ke thread Discord menggunakan Discord API secara async.
    
    Args:
        message (str): Pesan yang akan dikirim ke thread Discord.
    
    Returns:
        bool: True jika berhasil, False jika gagal.
    """
    if not DISCORD_AUTH_TOKEN or not DISCORD_THREAD_ID:
        logger.critical("DISCORD_AUTH_TOKEN atau DISCORD_THREAD_ID tidak valid atau kosong.")
        return False

    url = f"https://discord.com/api/v10/channels/{DISCORD_THREAD_ID}/messages"
    headers = {
        "Authorization": DISCORD_AUTH_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    }
    payload = {
        "content": message[:2000],  # Batasi 2000 karakter sesuai Discord
        "nonce": str(int(time.time() * 1000)),
        "tts": False,
        "flags": 0
    }

    logger.info("Menunggu 5 detik sebelum mengirim pesan ke Discord...")
    await asyncio.sleep(10)
    logger.info("Delay selesai, mengirim pesan ke Discord.")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response_text = await response.text()
                logger.debug(f"Discord response: {response.status} - {response_text}")
                if response.status == 200:
                    logger.info(f"Pesan berhasil dikirim ke thread Discord {DISCORD_THREAD_ID}")
                    return True
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limit tercapai. Menunggu {retry_after} detik...")
                    await asyncio.sleep(retry_after)
                    return await send_message_to_discord_thread(message)  # Retry
                else:
                    logger.critical(f"Gagal mengirim pesan ke Discord: {response.status} - {response_text}")
                    return False
        except Exception as e:
            logger.critical(f"Error saat mengirim pesan ke Discord: {str(e)}")
            return False
