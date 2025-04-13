import asyncio
from telethon import TelegramClient, events
from config import API_ID, API_HASH, PHONE, ADMINS, setup_logging, load_env, FILTERED_CHANNELS, UNFILTERED_CHANNELS, VIP_CHANNELS, SUMMARY_CHANNELS, SUMMARY_KEYWORDS, IMAGE_CHANNELS
from utils import login
from discord_utils import discord_worker, failed_message_queue
from telegram_handlers import (
    forward_message, 
    add_filter_channel, 
    add_unfilter_channel, 
    add_keyword, 
    remove_filter_channel, 
    remove_unfilter_channel, 
    remove_keyword, 
    list_filter_channel, 
    list_unfilter_channel, 
    list_keyword, 
    add_vip_channel, 
    list_vip_channel, 
    remove_vip_channel,
    add_summary_channel,
    remove_summary_channel,
    list_summary_channel,
    add_keyword_summary,
    list_keyword_summary,
    remove_keyword_summary,
    add_image_channel,
    remove_image_channel,
    list_image_channel
)

# Inisialisasi logger
logger = setup_logging()

async def main():
    # Inisialisasi klien Telegram
    client = TelegramClient('telegram_session', API_ID, API_HASH)
    
    # Buat antrian untuk kode verifikasi
    code_queue = asyncio.Queue()

    # Handler untuk menerima kode verifikasi dari admin (5 digit)
    @client.on(events.NewMessage(pattern=r'^\d{5}$'))
    async def code_handler(event):
        if str(event.sender_id) in ADMINS:
            code = event.text.strip()
            await code_queue.put(code)
            await event.reply("Kode verifikasi diterima!")
        else:
            await event.reply("Maaf, hanya admin yang boleh mengirim kode.")

    # Jalankan login dengan code_queue
    await login(client, code_queue)
    logger.info("Memulai fungsi main()")

    # Jalankan pekerja Discord di latar belakang
    asyncio.create_task(discord_worker())
    
    # Jalankan tugas notifikasi pesan gagal
    asyncio.create_task(notify_failed_messages_with_telegram(client))

    # Daftarkan handler untuk pesan baru
    chats = FILTERED_CHANNELS + UNFILTERED_CHANNELS + VIP_CHANNELS + SUMMARY_CHANNELS + IMAGE_CHANNELS
    if not chats:
        logger.warning("Tidak ada channel yang dipantau. Tambahkan channel ke channels.json atau gunakan perintah admin.")
    else:
        client.add_event_handler(forward_message, events.NewMessage(chats=chats))
        logger.info(f"Handler forward_message terdaftar untuk channel: {chats}")

    # Daftarkan handler perintah admin dengan pola regex yang ketat
    admin_commands = [
        (add_filter_channel, r'^/addfilterch (.+)'),
        (add_unfilter_channel, r'^/addunfilterch(.+)'),
        (add_keyword, r'^/add_keyword (.+)'),
        (remove_filter_channel, r'^/removefilterch (.+)'),
        (remove_unfilter_channel, r'^/removeunfilterch (.+)'),
        (remove_keyword, r'^/remove_keyword (.+)'),
        (list_filter_channel, r'^/list_filter\b'),
        (list_unfilter_channel, r'^/list_unfilter\b'),
        (list_keyword, r'^/list_keyword\b'),
        (add_vip_channel, r'^/addvip (.+)'),
        (list_vip_channel, r'^/list_vip\b'),
        (remove_vip_channel, r'^/removevip (.+)'),
        (add_summary_channel, r'^/addsummarych (.+)'),
        (remove_summary_channel, r'^/removesummary (.+)'),
        (list_summary_channel, r'^/list_summary\b'),
        (add_keyword_summary, r'^/addkeysummary (.+)'),
        (list_keyword_summary, r'^/listkeywsummary\b'),
        (remove_keyword_summary, r'^/removekeysummary (.+)'),
        (add_image_channel, r'^/addimagech (.+)'),
        (remove_image_channel, r'^/removeimagech (.+)'),
        (list_image_channel, r'^/listimgch\b')
    ]

    for handler, pattern in admin_commands:
        client.add_event_handler(handler, events.NewMessage(pattern=pattern))

    # Jalankan klien hingga terputus
    await client.run_until_disconnected()

async def notify_failed_messages_with_telegram(client):
    """
    Mengirim notifikasi pesan gagal ke admin melalui Telegram.
    """
    while True:
        message, reason = await failed_message_queue.get()
        for admin in ADMINS:
            try:
                if message:
                    await client.send_message(int(admin), f"Pesan gagal dikirim ke Discord: {message[:100]}...\nAlasan: {reason}")
                else:
                    await client.send_message(int(admin), f"Error Discord: {reason}")
                logger.info(f"Notifikasi pesan gagal dikirim ke admin {admin}: {message[:50] if message else reason}...")
            except Exception as e:
                logger.error(f"Gagal mengirim notifikasi ke admin {admin}: {str(e)}")
        failed_message_queue.task_done()

if __name__ == "__main__":
    load_env()  # Muat variabel lingkungan dari .env
    asyncio.run(main())  # Jalankan fungsi main dengan asyncio.run()
