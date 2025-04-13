# discord_utils.py
import aiohttp
import asyncio
import time
import random
import os
import json
from config import DISCORD_AUTH_TOKEN, DISCORD_THREAD_ID, logger
from utils import guess_blocked_keywords

message_queue = asyncio.Queue()
failed_message_queue = asyncio.Queue()

async def send_message_to_discord_thread(message, media_path=None):
    """
    Menambahkan pesan ke antrian untuk dikirim ke thread Discord.
    
    Args:
        message (str): Pesan yang akan dikirim.
        media_path (str, optional): Path lokal ke file media (misalnya, gambar) untuk diunggah.
    """
    await message_queue.put((message, media_path))
    logger.info(f"Pesan ditambahkan ke antrian utama: {message[:50]}...")

async def validate_thread_access(session, headers):
    """
    Memeriksa apakah bot memiliki akses ke thread Discord.
    
    Returns:
        bool: True jika akses valid, False jika tidak.
    """
    url = f"https://discord.com/api/v10/channels/{DISCORD_THREAD_ID}"
    try:
        async with session.get(url, headers=headers, timeout=5) as response:
            if response.status == 200:
                logger.info(f"Thread Discord {DISCORD_THREAD_ID} dapat diakses.")
                return True
            else:
                logger.error(f"Gagal mengakses thread Discord {DISCORD_THREAD_ID}: {response.status} - {await response.text()}")
                return False
    except Exception as e:
        logger.error(f"Error saat memvalidasi thread Discord {DISCORD_THREAD_ID}: {str(e)}")
        return False

async def handle_failed_message(message, media_path=None, retry_count=0, max_retries=3, reason="Tidak diketahui"):
    """
    Menangani pesan yang gagal dengan delay dan retry.
    
    Args:
        message (str): Pesan yang gagal.
        media_path (str, optional): Path file media yang gagal.
        retry_count (int): Jumlah percobaan saat ini.
        max_retries (int): Maksimum percobaan ulang.
        reason (str): Alasan kegagalan.
    """
    if retry_count >= max_retries:
        suspected_keywords = guess_blocked_keywords(message)
        full_reason = f"Gagal permanen: {reason}. Keyword yang mungkin diblokir: {', '.join(suspected_keywords) if suspected_keywords else 'Tidak diketahui'}"
        logger.critical(f"Pesan gagal setelah {max_retries} percobaan: {message[:50]}... ({full_reason})")
        await failed_message_queue.put((message, full_reason))
        return

    # Delay acak antara 1-5 menit (60-300 detik)
    delay = random.uniform(60, 300)
    logger.info(f"Pesan gagal, menunggu {delay:.2f} detik sebelum retry ke-{retry_count + 1}: {message[:50]}...")
    await asyncio.sleep(delay)
    
    # Tambahkan kembali ke antrian utama
    await message_queue.put((message, media_path))
    logger.info(f"Pesan ditambahkan kembali ke antrian utama untuk retry: {message[:50]}...")

async def discord_worker():
    """
    Pekerja yang mengambil pesan dari antrian dan mengirimkannya ke thread Discord.
    """
    if not DISCORD_AUTH_TOKEN or not DISCORD_THREAD_ID:
        logger.critical("DISCORD_AUTH_TOKEN atau DISCORD_THREAD_ID tidak valid atau kosong.")
        await failed_message_queue.put(("", "Startup gagal: DISCORD_AUTH_TOKEN atau DISCORD_THREAD_ID kosong."))
        return

    url = f"https://discord.com/api/v10/channels/{DISCORD_THREAD_ID}/messages"
    headers = {
        "Authorization": DISCORD_AUTH_TOKEN,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    }

    async with aiohttp.ClientSession() as session:
        # Validasi akses thread saat startup
        if not await validate_thread_access(session, headers):
            logger.critical("Bot tidak memiliki akses ke thread Discord. Periksa izin bot atau thread ID di .env.")
            await failed_message_queue.put(("", "Startup gagal: Bot tidak memiliki akses ke thread Discord."))
            return

        while True:
            item = await message_queue.get()
            message, media_path = item
            logger.info(f"Mengambil pesan dari antrian: {message[:50]}... (media: {media_path})")

            payload = {
                "content": message[:2000],  # Batasi 2000 karakter sesuai Discord
                "nonce": str(int(time.time() * 1000)),
                "tts": False,
                "flags": 0
            }

            logger.info("Menunggu 10 detik sebelum mengirim pesan ke Discord...")
            await asyncio.sleep(10)
            logger.info("Delay selesai, mengirim pesan ke Discord.")

            try:
                if media_path and os.path.exists(media_path):
                    # Kirim pesan dengan lampiran
                    form = aiohttp.FormData()
                    form.add_field("payload_json", json.dumps(payload))
                    form.add_field("file", open(media_path, "rb"), filename=os.path.basename(media_path), content_type="image/jpeg")

                    async with session.post(url, headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        response_text = await response.text()
                        logger.info(f"Discord response: {response.status} - {response_text}")
                        if response.status == 200:
                            logger.info(f"Pesan dengan lampiran berhasil dikirim ke thread Discord {DISCORD_THREAD_ID}")
                        elif response.status == 401:
                            reason = f"Unauthorized: Bot tidak diizinkan mengakses thread {DISCORD_THREAD_ID}"
                            logger.error(f"{reason}: {response_text}")
                            await handle_failed_message(message, media_path, retry_count=0, reason=reason)
                        elif response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 5))
                            logger.warning(f"Rate limit tercapai. Menunggu {retry_after} detik...")
                            await asyncio.sleep(retry_after)
                            await message_queue.put((message, media_path))  # Tambahkan kembali ke antrian
                        elif response.status == 400 and "blocked" in response_text.lower():
                            logger.warning(f"Pesan diblokir oleh server Discord: {message[:50]}...")
                            await handle_failed_message(message, media_path, retry_count=0, reason="Pesan diblokir oleh server")
                        else:
                            reason = f"Error API: {response.status} - {response_text}"
                            logger.critical(f"Gagal mengirim pesan ke Discord: {reason}")
                            await handle_failed_message(message, media_path, retry_count=0, reason=reason)
                else:
                    # Kirim pesan tanpa lampiran
                    async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        response_text = await response.text()
                        logger.info(f"Discord response: {response.status} - {response_text}")
                        if response.status == 200:
                            logger.info(f"Pesan berhasil dikirim ke thread Discord {DISCORD_THREAD_ID}")
                        elif response.status == 401:
                            reason = f"Unauthorized: Bot tidak diizinkan mengakses thread {DISCORD_THREAD_ID}"
                            logger.error(f"{reason}: {response_text}")
                            await handle_failed_message(message, retry_count=0, reason=reason)
                        elif response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 5))
                            logger.warning(f"Rate limit tercapai. Menunggu {retry_after} detik...")
                            await asyncio.sleep(retry_after)
                            await message_queue.put((message, None))  # Tambahkan kembali ke antrian
                        elif response.status == 400 and "blocked" in response_text.lower():
                            logger.warning(f"Pesan diblokir oleh server Discord: {message[:50]}...")
                            await handle_failed_message(message, retry_count=0, reason="Pesan diblokir oleh server")
                        else:
                            reason = f"Error API: {response.status} - {response_text}"
                            logger.critical(f"Gagal mengirim pesan ke Discord: {reason}")
                            await handle_failed_message(message, retry_count=0, reason=reason)
            except Exception as e:
                logger.critical(f"Exception saat mengirim pesan ke Discord: {str(e)}")
                await handle_failed_message(message, media_path, retry_count=0, reason=f"Exception: {str(e)}")
            finally:
                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                        logger.info(f"File sementara dihapus: {media_path}")
                    except Exception as e:
                        logger.error(f"Gagal menghapus file sementara {media_path}: {str(e)}")
                message_queue.task_done()
