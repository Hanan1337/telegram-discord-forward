# telegram_handlers.py

import json
import re
from telethon import events
from config import FILTERED_CHANNELS, UNFILTERED_CHANNELS, VIP_CHANNELS, SUMMARY_CHANNELS, KEYWORDS, SUMMARY_KEYWORDS, ADMINS, TARGET_CHANNEL, DISCORD_THREAD_ID, logger
from utils import extract_username, contains_keyword, translate_text
from discord_utils import send_message_to_discord_thread

async def update_monitored_chats(client):
    """
    Memperbarui daftar channel yang dipantau oleh bot.
    
    Args:
        client: Objek TelegramClient.
    """
    chats = FILTERED_CHANNELS + UNFILTERED_CHANNELS + VIP_CHANNELS + SUMMARY_CHANNELS
    if not chats:
        logger.warning("Tidak ada channel yang dipantau.")
        return
    
    try:
        client.remove_event_handler(forward_message)
        client.add_event_handler(forward_message, events.NewMessage(chats=chats))
        logger.info(f"Channel yang dipantau diperbarui: {chats}")
    except Exception as e:
        logger.critical(f"Gagal memperbarui channel yang dipantau: {str(e)}")
        raise

def transform_summary_message(message):
    """
    Mengubah pesan untuk hanya menampilkan bagian penting dengan format khusus.
    
    Args:
        message (str): Pesan asli.
    
    Returns:
        str: Pesan yang telah diringkas dan diformat.
    """
    lines = message.split('\n')
    important_message = lines[0].strip() if lines else message.strip()

    wallet_pattern = r'0x[a-fA-F0-9]{40}'
    wallets = re.findall(wallet_pattern, important_message)
    for wallet in wallets:
        shortened_wallet = f"{wallet[:3]}...{wallet[-2:]}"
        important_message = important_message.replace(wallet, shortened_wallet)

    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, important_message)
    for url in urls:
        modified_url = url.replace('.', '[.]', 1)
        important_message = important_message.replace(url, modified_url)

    return important_message

async def forward_message(event):
    """
    Meneruskan pesan dari channel sumber ke target berdasarkan aturan.
    
    Args:
        event: Event dari Telethon yang berisi pesan baru.
    """
    try:
        message = event.message
        chat_id = event.chat_id
        source_username = f"@{event.chat.username}" if event.chat.username else f"Channel ID: {chat_id}"
        logger.info(f"Memproses pesan {message.id} dari {chat_id}: {message.text}")

        translated_text = message.text
        if message.text:
            translated_text = await translate_text(message.text.strip())
        else:
            translated_text = "(Tidak ada teks)"

        if chat_id in SUMMARY_CHANNELS:
            if message.text and contains_keyword(message.text, SUMMARY_KEYWORDS):
                base_message = transform_summary_message(translated_text)
                final_message_telegram = f"{base_message} - {source_username}"  # Tanpa bold
                final_message_discord = f"### {base_message} - {source_username}"  # Tambah ### untuk Discord
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan ringkasan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan Discord thread")
            else:
                logger.info(f"Pesan dari {chat_id} tidak mengandung summary keywords: {message.text}")
        else:
            base_message = translated_text
            if chat_id in VIP_CHANNELS:
                final_message_telegram = f"**{base_message} - {source_username}**"
                final_message_discord = f"### {base_message} - {source_username}"
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan VIP {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan Discord thread")
            
            elif chat_id in FILTERED_CHANNELS:
                if message.text and contains_keyword(message.text, KEYWORDS):
                    final_message_telegram = f"{base_message} - {source_username}"
                    final_message_discord = f"### {base_message} - {source_username}"
                    await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                    await send_message_to_discord_thread(final_message_discord)
                    logger.info(f"Pesan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan Discord thread")
                else:
                    logger.info(f"Pesan dari {chat_id} tidak mengandung kata kunci: {message.text}")
            
            elif chat_id in UNFILTERED_CHANNELS:
                final_message_telegram = f"{base_message} - {source_username}"
                final_message_discord = f"{base_message} - {source_username}"
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan Discord thread")
    
    except Exception as e:
        logger.critical(f"Gagal memproses pesan {message.id}: {str(e)}")
        for admin in ADMINS:
            try:
                await event.client.send_message(int(admin), f"Galat memproses pesan {message.id} dari {source_username}: {str(e)}\nTeks: {message.text}")
            except Exception as send_error:
                logger.error(f"Gagal mengirim pesan ke admin {admin}: {str(send_error)}")

# Handler perintah admin untuk menambah channel ke SUMMARY_CHANNELS
async def add_summary_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id not in SUMMARY_CHANNELS:
            SUMMARY_CHANNELS.append(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} ditambahkan ke SUMMARY_CHANNELS.")
            logger.info(f"Channel {channel_id} ditambahkan ke SUMMARY_CHANNELS: {SUMMARY_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} sudah ada di SUMMARY_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menambah channel: {str(e)}")
        logger.error(f"Galat menambah channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menghapus channel dari SUMMARY_CHANNELS
async def remove_summary_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id in SUMMARY_CHANNELS:
            SUMMARY_CHANNELS.remove(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} dihapus dari SUMMARY_CHANNELS.")
            logger.info(f"Channel {channel_id} dihapus dari SUMMARY_CHANNELS: {SUMMARY_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} tidak ditemukan di SUMMARY_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menghapus channel: {str(e)}")
        logger.error(f"Galat menghapus channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menampilkan daftar SUMMARY_CHANNELS
async def list_summary_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if SUMMARY_CHANNELS:
        list_str = "Daftar Channel Summary:\n"
        for i, channel_id in enumerate(SUMMARY_CHANNELS):
            try:
                entity = await event.client.get_entity(channel_id)
                name = entity.username or f"Channel ID: {channel_id}"
                list_str += f"{i+1}. @{name}\n"
            except Exception:
                list_str += f"{i+1}. Channel ID: {channel_id} (tidak dapat diambil)\n"
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada channel di SUMMARY_CHANNELS.")

# Handler perintah admin untuk menambah keyword ke SUMMARY_KEYWORDS
async def add_keyword_summary(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    keyword = event.pattern_match.group(1).strip()
    if keyword not in SUMMARY_KEYWORDS:
        SUMMARY_KEYWORDS.append(keyword)
        with open('summary_keywords.json', 'w') as f:
            json.dump({'SUMMARY_KEYWORDS': SUMMARY_KEYWORDS}, f)
        await event.reply(f"Kata kunci summary {keyword} ditambahkan.")
        logger.info(f"Kata kunci summary {keyword} ditambahkan: {SUMMARY_KEYWORDS}")
    else:
        await event.reply(f"Kata kunci summary {keyword} sudah ada.")

# Handler perintah admin untuk menambah channel ke FILTERED_CHANNELS
async def add_filter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id not in FILTERED_CHANNELS:
            FILTERED_CHANNELS.append(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} ditambahkan ke FILTERED_CHANNELS.")
            logger.info(f"Channel {channel_id} ditambahkan ke FILTERED_CHANNELS: {FILTERED_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} sudah ada di FILTERED_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menambah channel: {str(e)}")
        logger.error(f"Galat menambah channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menambah channel ke UNFILTERED_CHANNELS
async def add_unfilter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id not in UNFILTERED_CHANNELS:
            UNFILTERED_CHANNELS.append(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} ditambahkan ke UNFILTERED_CHANNELS.")
            logger.info(f"Channel {channel_id} ditambahkan ke UNFILTERED_CHANNELS: {UNFILTERED_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} sudah ada di UNFILTERED_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menambah channel: {str(e)}")
        logger.error(f"Galat menambah channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menambah kata kunci
async def add_keyword(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    keyword = event.pattern_match.group(1).strip()
    if keyword not in KEYWORDS:
        KEYWORDS.append(keyword)
        with open('keywords.json', 'w') as f:
            json.dump({'KEYWORDS': KEYWORDS}, f)
        await event.reply(f"Kata kunci {keyword} ditambahkan.")
        logger.info(f"Kata kunci {keyword} ditambahkan: {KEYWORDS}")
    else:
        await event.reply(f"Kata kunci {keyword} sudah ada.")

# Handler perintah admin untuk menghapus channel dari FILTERED_CHANNELS
async def remove_filter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id in FILTERED_CHANNELS:
            FILTERED_CHANNELS.remove(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} dihapus dari FILTERED_CHANNELS.")
            logger.info(f"Channel {channel_id} dihapus dari FILTERED_CHANNELS: {FILTERED_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} tidak ditemukan di FILTERED_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menghapus channel: {str(e)}")
        logger.error(f"Galat menghapus channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menghapus channel dari UNFILTERED_CHANNELS
async def remove_unfilter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id in UNFILTERED_CHANNELS:
            UNFILTERED_CHANNELS.remove(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} dihapus dari UNFILTERED_CHANNELS.")
            logger.info(f"Channel {channel_id} dihapus dari UNFILTERED_CHANNELS: {UNFILTERED_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} tidak ditemukan di UNFILTERED_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menghapus channel: {str(e)}")
        logger.error(f"Galat menghapus channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menghapus kata kunci
async def remove_keyword(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    keyword = event.pattern_match.group(1).strip()
    if keyword in KEYWORDS:
        KEYWORDS.remove(keyword)
        with open('keywords.json', 'w') as f:
            json.dump({'KEYWORDS': KEYWORDS}, f)
        await event.reply(f"Kata kunci {keyword} dihapus.")
        logger.info(f"Kata kunci {keyword} dihapus: {KEYWORDS}")
    else:
        await event.reply(f"Kata kunci {keyword} tidak ditemukan.")

# Handler perintah admin untuk menampilkan daftar FILTERED_CHANNELS
async def list_filter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if FILTERED_CHANNELS:
        list_str = "Daftar Channel Filter:\n"
        for i, channel_id in enumerate(FILTERED_CHANNELS):
            try:
                entity = await event.client.get_entity(channel_id)
                name = entity.username or f"Channel ID: {channel_id}"
                list_str += f"{i+1}. @{name}\n"
            except Exception:
                list_str += f"{i+1}. Channel ID: {channel_id} (tidak dapat diambil)\n"
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada channel di FILTERED_CHANNELS.")

# Handler perintah admin untuk menampilkan daftar UNFILTERED_CHANNELS
async def list_unfilter_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if UNFILTERED_CHANNELS:
        list_str = "Daftar Channel Tanpa Filter:\n"
        for i, channel_id in enumerate(UNFILTERED_CHANNELS):
            try:
                entity = await event.client.get_entity(channel_id)
                name = entity.username or f"Channel ID: {channel_id}"
                list_str += f"{i+1}. @{name}\n"
            except Exception:
                list_str += f"{i+1}. Channel ID: {channel_id} (tidak dapat diambil)\n"
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada channel di UNFILTERED_CHANNELS.")

# Handler perintah admin untuk menampilkan daftar kata kunci
async def list_keyword(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if KEYWORDS:
        list_str = "Daftar Kata Kunci:\n"
        list_str += "\n".join([f"{i+1}. {keyword}" for i, keyword in enumerate(KEYWORDS)])
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada kata kunci yang ditambahkan.")

# Handler perintah admin untuk menambah channel ke VIP_CHANNELS
async def add_vip_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id not in VIP_CHANNELS:
            VIP_CHANNELS.append(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} ditambahkan ke VIP_CHANNELS.")
            logger.info(f"Channel {channel_id} ditambahkan ke VIP_CHANNELS: {VIP_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} sudah ada di VIP_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menambah channel VIP: {str(e)}")
        logger.error(f"Galat menambah channel VIP {channel_name}: {str(e)}")

# Handler perintah admin untuk menampilkan daftar VIP_CHANNELS
async def list_vip_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if VIP_CHANNELS:
        list_str = "Daftar Channel VIP:\n"
        for i, channel_id in enumerate(VIP_CHANNELS):
            try:
                entity = await event.client.get_entity(channel_id)
                name = entity.username or f"Channel ID: {channel_id}"
                list_str += f"{i+1}. @{name}\n"
            except Exception:
                list_str += f"{i+1}. Channel ID: {channel_id} (tidak dapat diambil)\n"
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada channel di VIP_CHANNELS.")

# Handler perintah admin untuk menghapus channel dari VIP_CHANNELS
async def remove_vip_channel(event):
    if str(event.sender_id) not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if channel_id in VIP_CHANNELS:
            VIP_CHANNELS.remove(channel_id)
            with open('channels.json', 'w') as f:
                json.dump({
                    'FILTERED_CHANNELS': FILTERED_CHANNELS,
                    'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                    'VIP_CHANNELS': VIP_CHANNELS,
                    'SUMMARY_CHANNELS': SUMMARY_CHANNELS
                }, f)
            await event.reply(f"Channel {channel_name} dihapus dari VIP_CHANNELS.")
            logger.info(f"Channel {channel_id} dihapus dari VIP_CHANNELS: {VIP_CHANNELS}")
            await update_monitored_chats(event.client)
        else:
            await event.reply(f"Channel {channel_name} tidak ditemukan di VIP_CHANNELS.")
    
    except Exception as e:
        await event.reply(f"Gagal menghapus channel VIP: {str(e)}")
        logger.error(f"Galat menghapus channel VIP {channel_name}: {str(e)}")
