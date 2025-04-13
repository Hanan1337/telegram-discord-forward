# telegram_handlers.py
import json
import re
import os
import tempfile
from collections import deque
from telethon import events
from telethon.tl.types import MessageMediaPhoto
from config import FILTERED_CHANNELS, UNFILTERED_CHANNELS, VIP_CHANNELS, SUMMARY_CHANNELS, IMAGE_CHANNELS, KEYWORDS, SUMMARY_KEYWORDS, ADMINS, TARGET_CHANNEL, DISCORD_THREAD_ID, logger
from utils import extract_username, contains_keyword, translate_text, remove_markdown
from discord_utils import send_message_to_discord_thread

# Gunakan deque untuk melacak pesan yang sudah diproses (batas maksimal 1000 pesan)
processed_messages = deque(maxlen=1000)

async def update_monitored_chats(client):
    """
    Memperbarui daftar channel yang dipantau oleh bot.
    
    Args:
        client: Objek TelegramClient.
    """
    chats = FILTERED_CHANNELS + UNFILTERED_CHANNELS + VIP_CHANNELS + SUMMARY_CHANNELS + IMAGE_CHANNELS
    if not chats:
        logger.warning("Tidak ada channel yang dipantau.")
        return
    
    try:
        client.add_event_handler(forward_message, events.NewMessage(chats=chats))
        logger.info(f"Channel yang dipantau diperbarui: {chats}")
    except Exception as e:
        logger.critical(f"Gagal memperbarui channel yang dipantau: {str(e)}")
        raise

def transform_summary_message(message, for_discord=False):
    """
    Mengubah pesan untuk hanya menampilkan bagian penting dengan format khusus.
    
    Args:
        message (str): Pesan asli.
        for_discord (bool): Jika True, hapus tautan untuk Discord.
    
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
    if for_discord:
        important_message = re.sub(url_pattern, '', important_message)
    else:
        urls = re.findall(url_pattern, important_message)
        for url in urls:
            modified_url = url.replace('.', '[.]', 1)
            important_message = important_message.replace(url, modified_url)

    return important_message.strip()

async def forward_message(event):
    """
    Meneruskan pesan dari channel sumber ke target berdasarkan aturan.
    
    Args:
        event: Event dari Telethon yang berisi pesan baru.
    """
    try:
        message = event.message
        chat_id = event.chat_id
        message_id = message.id
        
        # Buat ID unik untuk pesan
        unique_id = f"{chat_id}:{message_id}"
        if unique_id in processed_messages:
            logger.debug(f"Pesan {unique_id} sudah diproses, dilewati.")
            return
        
        # Tambahkan ke deque
        processed_messages.append(unique_id)
        
        source_username = f"@{event.chat.username}" if event.chat.username else f"Channel ID: {chat_id}"
        logger.info(f"Memproses pesan {message.id} dari {chat_id}: {message.text}")

        # Tangani pesan bergambar dari IMAGE_CHANNELS
        if chat_id in IMAGE_CHANNELS and message.media and isinstance(message.media, MessageMediaPhoto):
            translated_text = ""
            if message.text:
                translated_text = await translate_text(message.text.strip())
                translated_text = remove_markdown(translated_text)  # Hapus markdown
            else:
                translated_text = ""

            # Forward pesan bergambar ke Telegram
            final_message_telegram = f"{translated_text} - {source_username}" if translated_text else f"- {source_username}"
            await event.client.send_message(TARGET_CHANNEL, file=message.media, message=final_message_telegram)
            logger.info(f"Pesan bergambar {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL}")
            
            # Simpan gambar sementara untuk Discord
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            media_path = temp_file.name
            try:
                await event.client.download_media(message.media, media_path)
                final_message_discord = f"## {translated_text} - {source_username}" if translated_text else f"- {source_username}"
                await send_message_to_discord_thread(final_message_discord, media_path=media_path)
                logger.info(f"Pesan bergambar {message.id} dikirim ke antrian Discord dari {chat_id}")
            except Exception as e:
                logger.error(f"Gagal mengunduh atau mengirim gambar ke Discord: {str(e)}")
                await failed_message_queue.put((final_message_discord, f"Gagal mengunduh gambar: {str(e)}"))
            finally:
                temp_file.close()
            return

        # Tangani pesan teks seperti sebelumnya
        translated_text = message.text
        if message.text:
            translated_text = await translate_text(message.text.strip())
        else:
            translated_text = "(Tidak ada teks)"

        if chat_id in SUMMARY_CHANNELS:
            if message.text and contains_keyword(message.text, SUMMARY_KEYWORDS):
                base_message_telegram = transform_summary_message(translated_text, for_discord=False)
                base_message_discord = transform_summary_message(translated_text, for_discord=True)
                final_message_telegram = f"{base_message_telegram} - {source_username}"
                final_message_discord = f"### {base_message_discord} - {source_username}"
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan ringkasan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan antrian Discord")
            else:
                logger.info(f"Pesan dari {chat_id} tidak mengandung summary keywords: {message.text}")
        else:
            base_message = translated_text
            if chat_id in VIP_CHANNELS:
                final_message_telegram = f"**{base_message} - {source_username}**"
                final_message_discord = f"### {base_message} - {source_username}"
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan VIP {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan antrian Discord")
            
            elif chat_id in FILTERED_CHANNELS:
                if message.text and contains_keyword(message.text, KEYWORDS):
                    final_message_telegram = f"{base_message} - {source_username}"
                    final_message_discord = f"### {base_message} - {source_username}"
                    await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                    await send_message_to_discord_thread(final_message_discord)
                    logger.info(f"Pesan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan antrian Discord")
                else:
                    logger.info(f"Pesan dari {chat_id} tidak mengandung kata kunci: {message.text}")
            
            elif chat_id in UNFILTERED_CHANNELS:
                final_message_telegram = f"{base_message} - {source_username}"
                final_message_discord = f"{base_message} - {source_username}"
                await event.client.send_message(TARGET_CHANNEL, final_message_telegram)
                await send_message_to_discord_thread(final_message_discord)
                logger.info(f"Pesan {message.id} diteruskan dari {chat_id} ke {TARGET_CHANNEL} dan antrian Discord")
    
    except Exception as e:
        logger.critical(f"Gagal memproses pesan {message.id}: {str(e)}")
        for admin in ADMINS:
            try:
                await event.client.send_message(int(admin), f"Galat memproses pesan {message.id} dari {source_username}: {str(e)}\nTeks: {message.text}")
            except Exception as send_error:
                logger.error(f"Gagal mengirim pesan ke admin {admin}: {str(send_error)}")

async def update_channel_list(event, channel_list, list_name, action, channel_name):
    """
    Utilitas untuk menambah atau menghapus channel dari daftar.
    
    Args:
        event: Event dari Telethon.
        channel_list: Daftar channel yang akan diubah (misalnya, IMAGE_CHANNELS).
        list_name: Nama daftar (untuk logging dan pesan).
        action: 'add' atau 'remove'.
        channel_name: Nama atau ID channel.
    """
    if event.sender_id not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    try:
        entity = await event.client.get_entity(channel_name)
        channel_id = entity.id
        if channel_id > 0:
            channel_id = -1000000000000 - channel_id
        
        if action == "add" and channel_id not in channel_list:
            channel_list.append(channel_id)
            message = f"Channel {channel_name} ditambahkan ke {list_name}."
            logger.info(f"Channel {channel_id} ditambahkan ke {list_name}: {channel_list}")
        elif action == "remove" and channel_id in channel_list:
            channel_list.remove(channel_id)
            message = f"Channel {channel_name} dihapus dari {list_name}."
            logger.info(f"Channel {channel_id} dihapus dari {list_name}: {channel_list}")
        else:
            message = f"Channel {channel_name} sudah ada di {list_name}." if action == "add" else f"Channel {channel_name} tidak ditemukan di {list_name}."
            await event.reply(message)
            return
        
        with open('channels.json', 'w') as f:
            json.dump({
                'FILTERED_CHANNELS': FILTERED_CHANNELS,
                'UNFILTERED_CHANNELS': UNFILTERED_CHANNELS,
                'VIP_CHANNELS': VIP_CHANNELS,
                'SUMMARY_CHANNELS': SUMMARY_CHANNELS,
                'IMAGE_CHANNELS': IMAGE_CHANNELS
            }, f)
        await event.reply(message)
        await update_monitored_chats(event.client)
    except Exception as e:
        await event.reply(f"Gagal {action} channel: {str(e)}")
        logger.error(f"Galat {action} channel {channel_name}: {str(e)}")

# Handler perintah admin untuk menambah channel ke IMAGE_CHANNELS
async def add_image_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, IMAGE_CHANNELS, "IMAGE_CHANNELS", "add", channel_name)

# Handler perintah admin untuk menghapus channel dari IMAGE_CHANNELS
async def remove_image_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, IMAGE_CHANNELS, "IMAGE_CHANNELS", "remove", channel_name)

# Handler perintah admin untuk menampilkan daftar IMAGE_CHANNELS
async def list_image_channel(event):
    if event.sender_id not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if IMAGE_CHANNELS:
        list_str = "Daftar Channel Gambar:\n"
        for i, channel_id in enumerate(IMAGE_CHANNELS):
            try:
                entity = await event.client.get_entity(channel_id)
                name = entity.username or f"Channel ID: {channel_id}"
                list_str += f"{i+1}. @{name}\n"
            except Exception:
                list_str += f"{i+1}. Channel ID: {channel_id} (tidak dapat diambil)\n"
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada channel di IMAGE_CHANNELS.")

# Handler perintah admin untuk menambah channel ke SUMMARY_CHANNELS
async def add_summary_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, SUMMARY_CHANNELS, "SUMMARY_CHANNELS", "add", channel_name)

# Handler perintah admin untuk menghapus channel dari SUMMARY_CHANNELS
async def remove_summary_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, SUMMARY_CHANNELS, "SUMMARY_CHANNELS", "remove", channel_name)

# Handler perintah admin untuk menampilkan daftar SUMMARY_CHANNELS
async def list_summary_channel(event):
    if event.sender_id not in ADMINS:
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
    if event.sender_id not in ADMINS:
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

# Handler perintah admin untuk menghapus keyword dari SUMMARY_KEYWORDS
async def remove_keyword_summary(event):
    if event.sender_id not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    keyword = event.pattern_match.group(1).strip()
    if keyword in SUMMARY_KEYWORDS:
        SUMMARY_KEYWORDS.remove(keyword)
        with open('summary_keywords.json', 'w') as f:
            json.dump({'SUMMARY_KEYWORDS': SUMMARY_KEYWORDS}, f)
        await event.reply(f"Kata kunci summary {keyword} dihapus.")
        logger.info(f"Kata kunci summary {keyword} dihapus: {SUMMARY_KEYWORDS}")
    else:
        await event.reply(f"Kata kunci summary {keyword} tidak ditemukan.")

# Handler perintah admin untuk menampilkan daftar SUMMARY_KEYWORDS
async def list_keyword_summary(event):
    if event.sender_id not in ADMINS:
        await event.reply("Kamu tidak berwenang menggunakan perintah ini.")
        return
    
    if SUMMARY_KEYWORDS:
        list_str = "Daftar Kata Kunci Summary:\n"
        list_str += "\n".join([f"{i+1}. {keyword}" for i, keyword in enumerate(SUMMARY_KEYWORDS)])
        await event.reply(f"```\n{list_str}\n```")
    else:
        await event.reply("Tidak ada kata kunci summary yang ditambahkan.")

# Handler perintah admin untuk menambah channel ke FILTERED_CHANNELS
async def add_filter_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, FILTERED_CHANNELS, "FILTERED_CHANNELS", "add", channel_name)

# Handler perintah admin untuk menambah channel ke UNFILTERED_CHANNELS
async def add_unfilter_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, UNFILTERED_CHANNELS, "UNFILTERED_CHANNELS", "add", channel_name)

# Handler perintah admin untuk menambah kata kunci
async def add_keyword(event):
    if event.sender_id not in ADMINS:
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
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, FILTERED_CHANNELS, "FILTERED_CHANNELS", "remove", channel_name)

# Handler perintah admin untuk menghapus channel dari UNFILTERED_CHANNELS
async def remove_unfilter_channel(event):
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, UNFILTERED_CHANNELS, "UNFILTERED_CHANNELS", "remove", channel_name)

# Handler perintah admin untuk menghapus kata kunci
async def remove_keyword(event):
    if event.sender_id not in ADMINS:
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
    if event.sender_id not in ADMINS:
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
    if event.sender_id not in ADMINS:
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
    if event.sender_id not in ADMINS:
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
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, VIP_CHANNELS, "VIP_CHANNELS", "add", channel_name)

# Handler perintah admin untuk menampilkan daftar VIP_CHANNELS
async def list_vip_channel(event):
    if event.sender_id not in ADMINS:
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
    input_str = event.pattern_match.group(1)
    channel_name = extract_username(input_str)
    await update_channel_list(event, VIP_CHANNELS, "VIP_CHANNELS", "remove", channel_name)
