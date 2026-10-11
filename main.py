import asyncio
import json
import random
from pathlib import Path
import discord

client = discord.Client()
messages_dir = Path(__file__).parent / "messages"
cleaned_file = Path(__file__).parent / "cleaned.txt"
token = "your_token"


def load_cleaned():
    if not cleaned_file.is_file():
        return set()
    return set(cleaned_file.read_text(encoding="utf-8").split())


def mark_cleaned(ids):
    with open(cleaned_file, "a", encoding="utf-8") as f:
        for chat_id in ids:
            f.write(f"{chat_id}\n")


async def wipe(channel):
    count = 0
    seen = 0
    try:
        async for msg in channel.history(limit=None):
            seen += 1
            if msg.author.id != client.user.id:
                continue
            if msg.type not in (discord.MessageType.default, discord.MessageType.reply):
                continue
            try:
                await msg.delete()
                count += 1
                await asyncio.sleep(random.uniform(2, 4))
            except discord.HTTPException as e:
                print(f"skip {msg.id}: {e.code}")
    except discord.Forbidden:
        pass
    return count


def find_closed_dms():
    open_ids = {ch.id for ch in client.private_channels}
    closed = []
    for folder in messages_dir.iterdir():
        file = folder / "channel.json"
        if not file.is_file():
            continue
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if data.get("type") != "DM":
            continue
        chat_id = int(data["id"])
        if chat_id in open_ids:
            continue
        others = [str(r) for r in data.get("recipients", []) if str(r) != str(client.user.id)]
        closed.append((chat_id, others))
    return closed


async def get_names(channel, others):
    recipient = getattr(channel, "recipient", None)
    names = []
    for r in others:
        user = None
        if recipient is not None and str(recipient.id) == r:
            user = recipient
        if user is None and r.isdigit():
            user = client.get_user(int(r))
        if user is None and r.isdigit():
            try:
                user = await client.fetch_user(int(r))
            except discord.HTTPException:
                user = None
        names.append(f"{user.name} ({r})" if user else r)
    return ", ".join(names) or "unknown"


@client.event
async def on_ready():
    done_ids = load_cleaned()
    closed = [c for c in find_closed_dms() if str(c[0]) not in done_ids]
    if not closed:
        print("no closed dms found")
        await client.close()
        return
    print(f"closed dms: {len(closed)}")
    total = 0
    pending = []
    try:
        for chat_id, others in closed:
            try:
                channel = await client.fetch_channel(chat_id)
            except discord.HTTPException:
                channel = None
            names = await get_names(channel, others)
            if channel is None:
                print(f"cleaning dm with {names}: couldn't open, skipping")
                continue
            print(f"cleaning dm with {names}")
            deleted = await wipe(channel)
            total += deleted
            pending.append(chat_id)
            if len(pending) >= 5:
                mark_cleaned(pending)
                pending = []
            print(f"{names}: deleted {deleted}")
            await asyncio.sleep(random.uniform(1, 2))
    finally:
        if pending:
            mark_cleaned(pending)
    print(f"done, deleted {total} messages")
    await client.close()

client.run(token)
