import asyncio
import random
import string
import os
import subprocess

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputSticker,
    FSInputFile
)

from PIL import Image

TOKEN = ""

# ⚠️ Должен точно совпадать с @username бота (без @)
BOT_USERNAME = "elhakkastickerbot"

bot = Bot(TOKEN)
dp = Dispatcher()

user_mode = {}


def random_pack_name():
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{rand}_by_{BOT_USERNAME.lower()}"


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот для создания стикер-паков.\n\n"
        "📖 <b>Инструкция:</b>\n\n"
        "1️⃣ Напиши /createpack\n"
        "2️⃣ Выбери тип пака:\n"
        "   • 📦 <b>Стикер Пак</b> — обычные стикеры\n"
        "   • 😀 <b>Эмодзи Пак</b> — кастомные эмодзи\n\n"
        "3️⃣ Отправь один из вариантов:\n"
        "   • 🖼 <b>Фото</b> — станет статичным стикером\n"
        "   • 🎞 <b>GIF / Анимация</b> — станет анимированным стикером\n"
        "   • 🎭 <b>Существующий стикер</b> — скопируется в новый пак\n\n"
        "4️⃣ Готово! Бот пришлёт ссылку на твой новый пак 🎉\n\n"
        "▶️ Начать: /createpack",
        parse_mode="HTML"
    )


@dp.message(Command("createpack"))
async def create_pack(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Стикер Пак", callback_data="sticker_pack"),
                InlineKeyboardButton(text="😀 Эмодзи Пак", callback_data="emoji_pack")
            ]
        ]
    )
    await message.answer("Выберите тип пака:", reply_markup=kb)


@dp.callback_query(F.data.in_(["sticker_pack", "emoji_pack"]))
async def select_pack(callback: CallbackQuery):
    user_mode[callback.from_user.id] = callback.data
    await callback.message.edit_text(
        "Отправьте фото, GIF/анимацию или существующий стикер."
    )
    await callback.answer()


async def photo_to_sticker(file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    source = f"source_{file_id[:8]}.jpg"
    result = f"sticker_{file_id[:8]}.png"

    await bot.download_file(tg_file.file_path, destination=source)

    img = Image.open(source).convert("RGBA")
    img.thumbnail((512, 512))

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    canvas.paste(img, (x, y))
    canvas.save(result)

    return result


async def gif_to_webm(file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    source = f"source_{file_id[:8]}.mp4"
    result = f"sticker_{file_id[:8]}.webm"

    await bot.download_file(tg_file.file_path, destination=source)

    cmd = [
        "ffmpeg", "-y", "-i", source,
        "-vf",
        "scale=512:512:force_original_aspect_ratio=decrease,"
        "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0",
        "-t", "3",
        "-c:v", "libvpx-vp9",
        "-b:v", "0",
        "-crf", "30",
        "-an",
        result
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if proc.returncode != 0 or not os.path.exists(result):
        err = proc.stderr.decode(errors="ignore")[-300:]
        raise RuntimeError(f"ffmpeg ошибка:\n{err}")

    return result


@dp.message(F.photo | F.sticker | F.animation | F.document)
async def create_new_pack(message: Message):
    uid = message.from_user.id

    if uid not in user_mode:
        await message.answer(
            "⚠️ Сначала выберите тип пака через /createpack"
        )
        return

    mode = user_mode[uid]
    pack_name = random_pack_name()
    pack_title = (
        "Sticker @elhakkastickerbot"
        if mode == "sticker_pack"
        else "Emoji @elhakkastickerbot"
    )

    is_gif = bool(message.animation) or (
        message.document and
        message.document.mime_type in ("image/gif", "video/mp4")
    )

    source_files = []

    await message.answer("⏳ Создаю пак, подождите...")

    try:
        if message.sticker:
            fmt = (
                "animated" if message.sticker.is_animated else
                "video" if message.sticker.is_video else
                "static"
            )
            sticker = InputSticker(
                sticker=message.sticker.file_id,
                emoji_list=["😀"],
                format=fmt
            )

        elif is_gif:
            file_id = (
                message.animation.file_id
                if message.animation
                else message.document.file_id
            )
            webm_file = await gif_to_webm(file_id)
            source_files = [f"source_{file_id[:8]}.mp4", webm_file]

            sticker = InputSticker(
                sticker=FSInputFile(webm_file),
                emoji_list=["😀"],
                format="video"
            )

        else:
            fid = message.photo[-1].file_id
            png_file = await photo_to_sticker(fid)
            source_files = [f"source_{fid[:8]}.jpg", png_file]

            sticker = InputSticker(
                sticker=FSInputFile(png_file),
                emoji_list=["😀"],
                format="static"
            )

        await bot.create_new_sticker_set(
            user_id=uid,
            name=pack_name,
            title=pack_title,
            stickers=[sticker]
        )

        await message.answer(
            f"✅ <b>Пак успешно создан!</b>\n\n"
            f"🔗 <a href='https://t.me/addstickers/{pack_name}'>Открыть пак</a>\n\n"
            f"📌 Ссылка: https://t.me/addstickers/{pack_name}",
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<code>{e}</code>", parse_mode="HTML")

    finally:
        for file in source_files:
            if os.path.exists(file):
                os.remove(file)
        user_mode.pop(uid, None)


async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())