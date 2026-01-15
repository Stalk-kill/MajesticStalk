import discord
from discord.ext import commands
from discord.utils import get
import json
import asyncio

# ------------------- Настройка intents -------------------
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.reactions = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ------------------- Загрузка конфигурации -------------------
with open('config.json') as f:
    config = json.load(f)

bot.guild_id = int(config["guild_id"])
bot.channel_id = int(config["channel_id"])
bot.audit_channel_id = int(config["audit_channel_id"])
bot.role_audit_channel_id = int(config["role_audit_channel_id"])
bot.role_to_give_id = int(config["role_to_give"])
moderator_role_ids = [int(rid) for rid in config.get("moderator_roles", [])]

# ------------------- Проверка ролей и каналов -------------------
async def check_config():
    guild = bot.get_guild(bot.guild_id)
    if not guild:
        print("❌ Ошибка: сервер не найден по guild_id!")
        return

    print(f"✅ Проверка модераторских ролей и каналов на сервере '{guild.name}'")
    for rid in moderator_role_ids:
        role = guild.get_role(rid)
        if role:
            print(f"✅ Роль модератора '{role.name}' найдена")
        else:
            print(f"❌ Роль модератора с ID {rid} не найдена!")

    role_to_give = guild.get_role(bot.role_to_give_id)
    if role_to_give:
        print(f"✅ Роль для выдачи '{role_to_give.name}' найдена")
    else:
        print(f"❌ Роль для выдачи не найдена!")

    for cid_name, cid in [("channel_id", bot.channel_id), ("audit_channel_id", bot.audit_channel_id),
                          ("role_audit_channel_id", bot.role_audit_channel_id)]:
        channel = bot.get_channel(cid)
        if channel:
            print(f"✅ Канал {cid_name} найден: {channel.name}")
        else:
            print(f"❌ Канал {cid_name} с ID {cid} не найден!")

# ------------------- Embed с доступом -------------------
async def send_access_embed(channel, user=None):
    role_to_tag = get(channel.guild.roles, id=bot.role_to_give_id) if channel.guild else None
    description = f"{user.display_name}, нажмите ✅ чтобы получить роль {role_to_tag.mention}\nЕсли передумали — нажмите ❎" if user and role_to_tag else "Нажмите ✅ чтобы получить роль!\nЕсли передумали — нажмите ❎"
    embed = discord.Embed(title="✨ Доступ к серверу ✨", description=description, color=0xFF69B4)
    message = await channel.send(embed=embed)
    await message.add_reaction('✅')
    await message.add_reaction('❎')

# ------------------- Готовность -------------------
@bot.event
async def on_ready():
    print(f"Бот запущен и готов!")
    await check_config()
    bot_channel = bot.get_channel(bot.channel_id)
    if bot_channel:
        await send_access_embed(bot_channel)

# ------------------- Антиспам + реакции -------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == bot.channel_id:
        await send_access_embed(message.channel, message.author)

    # Антиспам ссылок
    if any(part.startswith("http://") or part.startswith("https://") for part in message.content.split()):
        user_roles_ids = [role.id for role in message.author.roles]
        is_moderator = any(rid in user_roles_ids for rid in moderator_role_ids)
        if not is_moderator:
            try: await message.delete()
            except: pass
            role_audit_channel = bot.get_channel(bot.role_audit_channel_id)
            if role_audit_channel:
                embed_audit = discord.Embed(
                    title="⚠️ Попытка спама/рекламы ссылки",
                    description=f"{message.author.mention} попытался отправить ссылку:\n`{message.content}`\nВ канале: {message.channel.mention}\nРоли: {', '.join([role.name for role in message.author.roles])}",
                    color=0xFF3366
                )
                await role_audit_channel.send(embed=embed_audit)

    await bot.process_commands(message)

# ------------------- Реакции для выдачи ролей -------------------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot: return
    if reaction.message.channel.id != bot.channel_id: return
    role_to_give = get(reaction.message.guild.roles, id=bot.role_to_give_id)
    role_audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not role_to_give: return

    if reaction.emoji == '✅':
        try:
            await user.add_roles(role_to_give)
            if role_audit_channel:
                embed = discord.Embed(title="🎉 Поздравляем!", description=f"{user.mention} получил(а) роль {role_to_give.mention} 💖\nТеперь может участвовать на сервере.", color=0xFF3366)
                await role_audit_channel.send(embed=embed)
            await reaction.remove(user)
        except Exception as e:
            if role_audit_channel:
                embed = discord.Embed(title="❌ Ошибка выдачи роли", description=f"{user.mention} не удалось выдать роль {role_to_give.mention}:\n{e}", color=0xFF0000)
                await role_audit_channel.send(embed=embed)
    elif reaction.emoji == '❎':
        if role_audit_channel:
            embed = discord.Embed(title="❌ Отказ от роли", description=f"{user.mention} отказался(ась) получать роль {role_to_give.mention}.", color=0xFF3366)
            await role_audit_channel.send(embed=embed)
        await reaction.remove(user)

# ------------------- Аудит пользователей -------------------
@bot.event
async def on_member_join(member):
    if member.guild.id != bot.guild_id: return
    audit_channel = bot.get_channel(bot.audit_channel_id)
    if not audit_channel: return
    embed = discord.Embed(title="🌟 Новый пользователь! 🌟", description=f"{member.mention} присоединился(-ась) к серверу!", color=0xCC66FF)
    embed.add_field(name="Пользователь", value=member.name, inline=False)
    embed.set_thumbnail(url=str(member.avatar.url) if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
    await audit_channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    if member.guild.id != bot.guild_id: return
    audit_channel = bot.get_channel(bot.audit_channel_id)
    if not audit_channel: return
    embed = discord.Embed(title="💔 Пользователь покинул сервер 💔", description=f"{member.name} покинул сервер.", color=0xFF3366)
    embed.add_field(name="Пользователь", value=member.name, inline=False)
    embed.set_thumbnail(url=str(member.avatar.url) if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
    await audit_channel.send(embed=embed)

# ------------------- Очистка сообщений -------------------
@bot.command(name='очистить')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = None):
    role_audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if amount is None:
        if role_audit_channel:
            embed = discord.Embed(title="❌ Ошибка очистки сообщений", description=f"{ctx.author.mention} не указал количество сообщений для удаления.", color=0xFF3366)
            await role_audit_channel.send(embed=embed)
        return
    deleted = await ctx.channel.purge(limit=amount)
    if role_audit_channel:
        embed = discord.Embed(title="🧹 Очистка сообщений", description=f"{ctx.author.mention} удалил(а) {len(deleted)} сообщений в {ctx.channel.mention}.", color=0xFF3366)
        await role_audit_channel.send(embed=embed)

# ------------------- Логирование сообщений -------------------
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    try:
        moderator = None
        async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
            if entry.target.id == message.author.id:
                moderator = entry.user
                break
        embed = discord.Embed(
            title="🗑 Сообщение удалено",
            description=(
                f"👤 Автор: {message.author.mention}\n"
                f"📍 Канал: {message.channel.mention}\n"
                f"💬 Сообщение:\n```{message.content or 'Без текста'}```\n"
                f"🛠 Удалил: {moderator.mention if moderator else 'Неизвестно'}"
            ),
            color=0xFF3366
        )
        await audit_channel.send(embed=embed)
    except Exception as e:
        print(f"Ошибка логирования удаления сообщения: {e}")

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    embed = discord.Embed(
        title="✏️ Сообщение отредактировано",
        description=f"👤 Автор: {before.author.mention}\n📍 Канал: {before.channel.mention}\n💬 Было:\n```{before.content}```\n💬 Стало:\n```{after.content}```",
        color=0xFFCC66
    )
    await audit_channel.send(embed=embed)

# ------------------- Лог каналов -------------------
@bot.event
async def on_guild_channel_create(channel):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        moderator = entry.user
        break
    else: moderator = None
    embed = discord.Embed(title="📁 Создан канал", description=f"📍 Канал: {channel.name}\n🛠 Создал: {moderator.mention if moderator else 'Неизвестно'}", color=0xCC66FF)
    await audit_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        moderator = entry.user
        break
    else: moderator = None
    embed = discord.Embed(title="❌ Удалён канал", description=f"📍 Канал: {channel.name}\n🛠 Удалил: {moderator.mention if moderator else 'Неизвестно'}", color=0xFF3366)
    await audit_channel.send(embed=embed)

@bot.event
async def on_guild_channel_update(before, after):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel or before.name == after.name: return
    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
        moderator = entry.user
        break
    else: moderator = None
    embed = discord.Embed(title="✏️ Изменён канал", description=f"📍 Было: {before.name}\n📍 Стало: {after.name}\n🛠 Изменил: {moderator.mention if moderator else 'Неизвестно'}", color=0xFF69B4)
    await audit_channel.send(embed=embed)

# ------------------- Лог ролей -------------------
@bot.event
async def on_guild_role_create(role):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
        moderator = entry.user
        break
    else: moderator = None
    embed = discord.Embed(
        title="🎭 Создана новая роль",
        description=f"Роль: {role.name}\nЦвет: {role.color}\nПрава: {', '.join([p[0] for p in role.permissions if p[1]]) or 'Нет'}\nСоздал: {moderator.mention if moderator else 'Неизвестно'}",
        color=0x66CCFF
    )
    await audit_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        moderator = entry.user
        break
    else: moderator = None
    embed = discord.Embed(
        title="❌ Роль удалена",
        description=f"Роль: {role.name}\nУдалил: {moderator.mention if moderator else 'Неизвестно'}",
        color=0xFF3366
    )
    await audit_channel.send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    audit_channel = bot.get_channel(bot.role_audit_channel_id)
    if not audit_channel: return
    async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
        moderator = entry.user
        break
    else: moderator = None

    changes = []
    if before.name != after.name:
        changes.append(f"Название: `{before.name}` → `{after.name}`")
    if before.color != after.color:
        changes.append(f"Цвет: `{before.color}` → `{after.color}`")
    if before.permissions != after.permissions:
        before_perms = [p[0] for p in before.permissions if p[1]]
        after_perms = [p[0] for p in after.permissions if p[1]]
        changes.append(f"Права: `{', '.join(before_perms) or 'Нет'}` → `{', '.join(after_perms) or 'Нет'}`")

    if changes:
        embed = discord.Embed(
            title="✏️ Роль обновлена",
            description=f"Роль: {after.name}\nИзменения:\n" + "\n".join(changes) + f"\n🛠 Изменил: {moderator.mention if moderator else 'Неизвестно'}",
            color=0xFF69B4
        )
        await audit_channel.send(embed=embed)

# ------------------- Запуск бота -------------------
bot.run(config['token'])
