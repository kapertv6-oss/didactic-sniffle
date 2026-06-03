import asyncio
import random
import string
import os
import subprocess

import static_ffmpeg

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

TOKEN = "8904088638:AAGjGQ45-wIcz_C_bta7G2VlvMTgUucMrR8"

BOT_USERNAME = "elhakkastickerbot"

bot = Bot(TOKEN)
dp = Dispatcher()

# user_id -> {"mode": "sticker_pack"/"emoji_pack", "pack_name": str, "count": int}
user_sessions = {}


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
        "3️⃣ Отправляй стикеры по одному:\n"
        "   • 🖼 <b>Фото</b> — статичный стикер\n"
        "   • 🎞 <b>GIF / Анимация</b> — анимированный стикер\n"
        "   • 🎭 <b>Существующий стикер</b> — копия в новый пак\n\n"
        "4️⃣ Когда добавишь все стикеры — напиши /done\n\n"
        "5️⃣ Бот пришлёт ссылку на готовый пак 🎉\n\n"
        "▶️ Начать: /createpack",
        parse_mode="HTML"
    )


@dp.message(Command("createpack"))
async def create_pack(message: Message):
    uid = message.from_user.id

    # Если уже есть активная сессия — предупреждаем
    if uid in user_sessions:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🗑 Начать новый", callback_data="new_pack"),
                    InlineKeyboardButton(text="↩️ Продолжить текущий", callback_data="continue_pack")
                ]
            ]
        )
        await message.answer(
            f"⚠️ У тебя уже есть активный пак со стикерами: {user_sessions[uid]['count']} шт.\n"
            "Что делаем?",
            reply_markup=kb
        )
        return

    await show_pack_type_keyboard(message)


async def show_pack_type_keyboard(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Стикер Пак", callback_data="sticker_pack"),
                InlineKeyboardButton(text="😀 Эмодзи Пак", callback_data="emoji_pack")
            ]
        ]
    )
    await message.answer("Выберите тип пака:", reply_markup=kb)


@dp.callback_query(F.data == "new_pack")
async def new_pack(callback: CallbackQuery):
    user_sessions.pop(callback.from_user.id, None)
    await callback.message.edit_text("Старый пак отменён. Выберите тип нового пака:")
    await show_pack_type_keyboard(callback.message)
    await callback.answer()


@dp.callback_query(F.data == "continue_pack")
async def continue_pack(callback: CallbackQuery):
    uid = callback.from_user.id
    count = user_sessions[uid]["count"]
    await callback.message.edit_text(
        f"Продолжаем! В паке уже {count} стикер(ов).\n"
        "Отправляй ещё или напиши /done чтобы завершить."
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["sticker_pack", "emoji_pack"]))
async def select_pack(callback: CallbackQuery):
    uid = callback.from_user.id
    user_sessions[uid] = {
        "mode": callback.data,
        "pack_name": random_pack_name(),
        "count": 0
    }
    await callback.message.edit_text(
        "Отправляй фото, GIF или стикеры по одному.\n"
        "Когда закончишь — напиши /done"
    )
    await callback.answer()


@dp.message(Command("done"))
async def done(message: Message):
    uid = message.from_user.id

    if uid not in user_sessions:
        await message.answer("⚠️ Нет активного пака. Начни с /createpack")
        return

    count = user_sessions[uid]["count"]

    if count == 0:
        await message.answer("⚠️ Ты ещё не добавил ни одного стикера! Отправь хотя бы один.")
        return

    pack_name = user_sessions[uid]["pack_name"]

    await message.answer(
        f"✅ <b>Пак готов! Добавлено стикеров: {count}</b>\n\n"
        f"🔗 <a href='https://t.me/addstickers/{pack_name}'>Открыть пак</a>\n\n"
        f"📌 Ссылка: https://t.me/addstickers/{pack_name}",
        parse_mode="HTML"
    )

    user_sessions.pop(uid, None)


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
async def add_sticker(message: Message):
    uid = message.from_user.id

    if uid not in user_sessions:
        await message.answer("⚠️ Сначала создай пак через /createpack")
        return

    session = user_sessions[uid]
    pack_name = session["pack_name"]
    mode = session["mode"]
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

    await message.answer("⏳ Добавляю стикер...")

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

            # Сначала загружаем файл и получаем file_id
            uploaded = await bot.upload_sticker_file(
                user_id=uid,
                sticker=FSInputFile(webm_file),
                sticker_format="video"
            )

            sticker = InputSticker(
                sticker=uploaded.file_id,
                emoji_list=["😀"],
                format="video"
            )

        else:
            fid = message.photo[-1].file_id
            png_file = await photo_to_sticker(fid)
            source_files = [f"source_{fid[:8]}.jpg", png_file]

            # Сначала загружаем файл и получаем file_id
            uploaded = await bot.upload_sticker_file(
                user_id=uid,
                sticker=FSInputFile(png_file),
                sticker_format="static"
            )

            sticker = InputSticker(
                sticker=uploaded.file_id,
                emoji_list=["😀"],
                format="static"
            )

        # Первый стикер — создаём пак, остальные — добавляем
        if session["count"] == 0:
            await bot.create_new_sticker_set(
                user_id=uid,
                name=pack_name,
                title=pack_title,
                stickers=[sticker]
            )
        else:
            await bot.add_sticker_to_set(
                user_id=uid,
                name=pack_name,
                sticker=sticker
            )

        session["count"] += 1
        count = session["count"]

        await message.answer(
            f"✅ Стикер {count} добавлен!\n"
            "Отправь ещё или напиши /done чтобы завершить."
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка:\n<code>{e}</code>",
            parse_mode="HTML"
        )

    finally:
        for file in source_files:
            if os.path.exists(file):
                os.remove(file)

async def main():
    static_ffmpeg.add_paths()
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
