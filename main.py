import asyncio
from telethon import TelegramClient, events
from config import API_ID, API_HASH, PHONE, setup_logging, load_env, FILTERED_CHANNELS, UNFILTERED_CHANNELS, VIP_CHANNELS, SUMMARY_CHANNELS, SUMMARY_KEYWORDS
from utils import login
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
    add_keyword_summary  # Tambahkan handler baru
)

# Inisialisasi logger
logger = setup_logging()

async def main():
    # Inisialisasi klien Telegram
    client = TelegramClient('telegram_session', API_ID, API_HASH)
    await login(client)  # Login ke Telegram
    logger.info("Memulai fungsi main()")

    # Daftarkan handler untuk pesan baru
    chats = FILTERED_CHANNELS + UNFILTERED_CHANNELS + VIP_CHANNELS + SUMMARY_CHANNELS
    if not chats:
        logger.warning("Tidak ada channel yang dipantau. Tambahkan channel ke channels.json atau gunakan perintah admin.")
    else:
        client.add_event_handler(forward_message, events.NewMessage(chats=chats))
        logger.info(f"Handler forward_message terdaftar untuk channel: {chats}")

    # Daftarkan handler perintah admin
    client.add_event_handler(add_filter_channel, events.NewMessage(pattern='/add_filter_channel (.+)'))
    client.add_event_handler(add_unfilter_channel, events.NewMessage(pattern='/add_unfilter_channel (.+)'))
    client.add_event_handler(add_keyword, events.NewMessage(pattern='/add_keyword (.+)'))
    client.add_event_handler(remove_filter_channel, events.NewMessage(pattern='/remove_filter_channel (.+)'))
    client.add_event_handler(remove_unfilter_channel, events.NewMessage(pattern='/remove_unfilter_channel (.+)'))
    client.add_event_handler(remove_keyword, events.NewMessage(pattern='/remove_keyword (.+)'))
    client.add_event_handler(list_filter_channel, events.NewMessage(pattern='/list_filter'))
    client.add_event_handler(list_unfilter_channel, events.NewMessage(pattern='/list_unfilter'))
    client.add_event_handler(list_keyword, events.NewMessage(pattern='/list_keyword'))
    client.add_event_handler(add_vip_channel, events.NewMessage(pattern='/add_vip_channel (.+)'))
    client.add_event_handler(list_vip_channel, events.NewMessage(pattern='/list_vip'))
    client.add_event_handler(remove_vip_channel, events.NewMessage(pattern='/remove_vip_channel (.+)'))
    
    # Handler untuk SUMMARY_CHANNELS
    client.add_event_handler(add_summary_channel, events.NewMessage(pattern=r'/add_summary_channel (.+)'))
    client.add_event_handler(remove_summary_channel, events.NewMessage(pattern=r'/remove_summary_channel (.+)'))
    client.add_event_handler(list_summary_channel, events.NewMessage(pattern=r'/list_summary_channel'))
    client.add_event_handler(add_keyword_summary, events.NewMessage(pattern=r'/add_keyword_summary (.+)'))

    # Jalankan klien hingga terputus
    await client.run_until_disconnected()

if __name__ == "__main__":
    load_env()  # Muat variabel lingkungan dari .env
    asyncio.run(main())  # Jalankan fungsi main dengan asyncio.run()
