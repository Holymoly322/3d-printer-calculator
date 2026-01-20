import os
import logging
import re
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import asyncio
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_PATH = 'printer_bot.db'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# States
class PrintForm(StatesGroup):
    name = State()
    gcode_or_manual = State()
    spool_id = State()
    weight = State()
    hours = State()
    sale_price = State()

class SpoolForm(StatesGroup):
    name = State()
    cost = State()
    weight = State()

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица настроек принтера
        await db.execute('''
            CREATE TABLE IF NOT EXISTS printer_settings (
                user_id TEXT PRIMARY KEY,
                printer_cost REAL DEFAULT 50000,
                amortization_months INTEGER DEFAULT 24,
                electricity_cost REAL DEFAULT 6,
                printer_power REAL DEFAULT 0.3,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица катушек
        await db.execute('''
            CREATE TABLE IF NOT EXISTS spools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                cost REAL NOT NULL,
                weight REAL NOT NULL,
                price_per_gram REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица печатей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS prints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                name TEXT NOT NULL,
                spool_name TEXT NOT NULL,
                weight REAL NOT NULL,
                hours REAL NOT NULL,
                sale_price REAL NOT NULL,
                material_cost REAL NOT NULL,
                electricity_cost_calc REAL NOT NULL,
                amortization REAL NOT NULL,
                total_cost REAL NOT NULL,
                profit REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.commit()
    logger.info("Database initialized successfully")

# Функция парсинга G-code
def parse_gcode(content: str):
    weight_grams = None
    time_hours = None
    lines = content.split('\n')[:300]  # Увеличил до 300 строк для Bambu Lab

    for line in lines:
        line = line.strip()

        # Bambu Lab Studio - прямой вес в граммах
        if 'filament used [g]' in line.lower() or 'total filament used [g]' in line.lower():
            match = re.search(r'=\s*(\d+\.?\d*)', line)
            if match:
                weight_grams = float(match.group(1))

        # Bambu Lab - filament_weight
        elif 'filament_weight' in line.lower():
            match = re.search(r'(\d+\.?\d*)', line)
            if match and not weight_grams:
                weight_grams = float(match.group(1))

        # PrusaSlicer - вес
        elif 'filament used [g]' in line.lower():
            match = re.search(r'(\d+\.?\d*)', line)
            if match:
                weight_grams = float(match.group(1))

        # Длина в мм -> вес (для файлов где нет прямого веса)
        elif ('filament used [mm]' in line.lower() or 'filament used:' in line.lower()) and not weight_grams:
            match = re.search(r'(\d+\.?\d*)', line)
            if match:
                length_mm = float(match.group(1))
                weight_grams = (length_mm / 1000) * 2.4  # ~2.4г на метр для PLA 1.75мм

        # Время печати - Bambu Lab: estimated printing time (normal mode) = 2h 30m 15s
        if 'estimated printing time' in line.lower() or 'print time' in line.lower() or 'total time' in line.lower():
            hours_match = re.search(r'(\d+)h', line)
            mins_match = re.search(r'(\d+)m', line)
            secs_match = re.search(r'(\d+)s', line)

            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(mins_match.group(1)) if mins_match else 0
            seconds = int(secs_match.group(1)) if secs_match else 0

            time_hours = hours + (minutes / 60) + (seconds / 3600)

        # Cura: ;TIME:7200
        elif line.startswith(';TIME:'):
            match = re.search(r';TIME:(\d+)', line)
            if match:
                time_seconds = int(match.group(1))
                time_hours = time_seconds / 3600

    return weight_grams, time_hours

# Главное меню
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Сводка", callback_data="dashboard")],
        [InlineKeyboardButton(text="📝 Добавить печать", callback_data="add_print")],
        [InlineKeyboardButton(text="🧵 Управление катушками", callback_data="spools")],
        [InlineKeyboardButton(text="⚙️ Настройки принтера", callback_data="settings")]
    ])
    return keyboard

# /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем есть ли настройки пользователя
        async with db.execute('SELECT * FROM printer_settings WHERE user_id = ?', (user_id,)) as cursor:
            settings = await cursor.fetchone()

        if not settings:
            # Создаем настройки по умолчанию
            await db.execute('''
                INSERT INTO printer_settings (user_id, printer_cost, amortization_months, electricity_cost, printer_power)
                VALUES (?, 50000, 24, 6, 0.3)
            ''', (user_id,))
            await db.commit()

    await message.answer(
        "🖨️ *Калькулятор заработка 3D принтера*\n\n"
        "Я помогу вам отслеживать расходы и доходы от 3D печати.\n\n"
        "✨ Поддерживаются файлы:\n"
        "• Bambu Lab Studio (.gcode, .3mf)\n"
        "• Cura (.gcode)\n"
        "• PrusaSlicer (.gcode)\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# Сводка
@dp.callback_query(F.data == "dashboard")
async def show_dashboard(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM prints WHERE user_id = ?', (user_id,)) as cursor:
            prints = await cursor.fetchall()

        if not prints:
            await callback.message.edit_text(
                "📊 *Сводка*\n\n"
                "У вас пока нет печатей. Добавьте первую печать!",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return

        total_profit = sum(p[12] for p in prints)  # profit
        total_revenue = sum(p[7] for p in prints)  # sale_price
        total_cost = sum(p[11] for p in prints)  # total_cost
        total_plastic = sum(p[5] for p in prints)  # weight

        text = (
            f"📊 *Сводка*\n\n"
            f"💰 Чистая прибыль: {total_profit:.2f} ₽\n"
            f"📈 Общая выручка: {total_revenue:.2f} ₽\n"
            f"💸 Себестоимость: {total_cost:.2f} ₽\n"
            f"🧵 Израсходовано: {total_plastic:.0f} г\n"
            f"📝 Всего печатей: {len(prints)}"
        )

        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    await callback.answer()

# Катушки
@dp.callback_query(F.data == "spools")
async def show_spools(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM spools WHERE user_id = ? ORDER BY created_at DESC', (user_id,)) as cursor:
            spools = await cursor.fetchall()

        if not spools:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить катушку", callback_data="add_spool")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
            ])
            await callback.message.edit_text(
                "🧵 *Катушки пластика*\n\n"
                "У вас пока нет катушек. Добавьте первую!",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        text = "🧵 *Ваши катушки:*\n\n"
        for spool in spools:
            text += (
                f"• *{spool[2]}*\n"  # name
                f"  Стоимость: {spool[3]:.2f} ₽\n"  # cost
                f"  Вес: {spool[4]:.0f} г\n"  # weight
                f"  Цена за грамм: {spool[5]:.2f} ₽/г\n\n"  # price_per_gram
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить катушку", callback_data="add_spool")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# Добавление катушки
@dp.callback_query(F.data == "add_spool")
async def add_spool_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🧵 Введите название катушки (например, 'PLA Белый'):")
    await state.set_state(SpoolForm.name)
    await callback.answer()

@dp.message(SpoolForm.name)
async def add_spool_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💰 Введите стоимость катушки в рублях:")
    await state.set_state(SpoolForm.cost)

@dp.message(SpoolForm.cost)
async def add_spool_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text)
        await state.update_data(cost=cost)
        await message.answer("⚖️ Введите вес катушки в граммах:")
        await state.set_state(SpoolForm.weight)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например, 1500):")

@dp.message(SpoolForm.weight)
async def add_spool_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text)
        data = await state.get_data()
        user_id = str(message.from_user.id)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO spools (user_id, name, cost, weight, price_per_gram)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, data['name'], data['cost'], weight, data['cost'] / weight))
            await db.commit()

        await message.answer(
            f"✅ Катушка *{data['name']}* добавлена!\n"
            f"Цена за грамм: {(data['cost'] / weight):.2f} ₽/г",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например, 1000):")
    except Exception as e:
        logger.error(f"Error adding spool: {e}")
        await message.answer("❌ Ошибка при добавлении катушки", reply_markup=main_menu())
        await state.clear()

# Добавление печати
@dp.callback_query(F.data == "add_print")
async def add_print_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM spools WHERE user_id = ?', (user_id,)) as cursor:
            spools = await cursor.fetchall()

    if not spools:
        await callback.message.edit_text(
            "❌ Сначала добавьте катушку пластика!",
            reply_markup=main_menu()
        )
        await callback.answer()
        return

    await callback.message.edit_text("📝 Введите название детали:")
    await state.set_state(PrintForm.name)
    await callback.answer()

@dp.message(PrintForm.name)
async def add_print_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Загрузить G-code файл", callback_data="upload_gcode")],
        [InlineKeyboardButton(text="✍️ Ввести данные вручную", callback_data="manual_input")]
    ])

    await message.answer(
        "Как вы хотите добавить данные о печати?",
        reply_markup=keyboard
    )
    await state.set_state(PrintForm.gcode_or_manual)

# Обработчик загрузки G-code
@dp.callback_query(F.data == "upload_gcode", PrintForm.gcode_or_manual)
async def handle_upload_gcode(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📄 Отправьте файл (.gcode или .3mf)\n\n"
        "Бот автоматически извлечет:\n"
        "• Вес пластика\n"
        "• Время печати\n\n"
        "✨ Поддержка:\n"
        "• Bambu Lab Studio\n"
        "• Cura\n"
        "• PrusaSlicer\n"
        "• Simplify3D"
    )
    await callback.answer()

# Обработчик документов
@dp.message(F.document, PrintForm.gcode_or_manual)
async def handle_gcode_file(message: types.Message, state: FSMContext):
    document = message.document

    if not (document.file_name.endswith('.gcode') or document.file_name.endswith('.gco') or document.file_name.endswith('.3mf')):
        await message.answer("❌ Пожалуйста, отправьте файл .gcode, .gco или .3mf")
        return

    try:
        file = await bot.get_file(document.file_id)
        file_content = await bot.download_file(file.file_path)
        content = file_content.read().decode('utf-8', errors='ignore')

        weight_grams, time_hours = parse_gcode(content)

        if weight_grams and time_hours:
            await state.update_data(weight=weight_grams, hours=time_hours)
            await message.answer(
                f"✅ Данные успешно извлечены!\n\n"
                f"⚖️ Вес: {weight_grams:.1f} г\n"
                f"⏱️ Время: {time_hours:.2f} ч\n\n"
                f"Теперь выберите катушку..."
            )

            user_id = str(message.from_user.id)
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute('SELECT * FROM spools WHERE user_id = ?', (user_id,)) as cursor:
                    spools = await cursor.fetchall()

            text = "🧵 Выберите катушку (отправьте номер):\n\n"
            for idx, spool in enumerate(spools, 1):
                text += f"{idx}. {spool[2]} ({spool[5]:.2f} ₽/г)\n"

            await state.update_data(spools=spools)
            await message.answer(text)
            await state.set_state(PrintForm.spool_id)
        else:
            error_msg = "⚠️ Не удалось извлечь данные из файла.\n\n"
            if not weight_grams:
                error_msg += "• Вес пластика не найден\n"
            if not time_hours:
                error_msg += "• Время печати не найдено\n"
            error_msg += "\nПопробуйте ввести данные вручную."

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="manual_input")]
            ])
            await message.answer(error_msg, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        await message.answer(
            "❌ Ошибка при обработке файла. Попробуйте ввести данные вручную.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="manual_input")]
            ])
        )

# Ручной ввод
@dp.callback_query(F.data == "manual_input", PrintForm.gcode_or_manual)
async def handle_manual_input(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM spools WHERE user_id = ?', (user_id,)) as cursor:
            spools = await cursor.fetchall()

    text = "🧵 Выберите катушку (отправьте номер):\n\n"
    for idx, spool in enumerate(spools, 1):
        text += f"{idx}. {spool[2]} ({spool[5]:.2f} ₽/г)\n"

    await state.update_data(spools=spools)
    await callback.message.edit_text(text)
    await state.set_state(PrintForm.spool_id)
    await callback.answer()

@dp.message(PrintForm.spool_id)
async def add_print_spool(message: types.Message, state: FSMContext):
    try:
        idx = int(message.text) - 1
        data = await state.get_data()
        spools = data['spools']

        if idx < 0 or idx >= len(spools):
            await message.answer("❌ Неверный номер. Попробуйте снова:")
            return

        await state.update_data(selected_spool=spools[idx])

        if 'weight' in data and 'hours' in data:
            await message.answer("💵 Введите цену продажи в рублях:")
            await state.set_state(PrintForm.sale_price)
        else:
            await message.answer("⚖️ Введите вес пластика в граммах:")
            await state.set_state(PrintForm.weight)
    except ValueError:
        await message.answer("❌ Введите номер катушки:")

@dp.message(PrintForm.weight)
async def add_print_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text)
        await state.update_data(weight=weight)
        await message.answer("⏱️ Введите время печати в часах (например, 5.5):")
        await state.set_state(PrintForm.hours)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")

@dp.message(PrintForm.hours)
async def add_print_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
        await state.update_data(hours=hours)
        await message.answer("💵 Введите цену продажи в рублях:")
        await state.set_state(PrintForm.sale_price)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")

@dp.message(PrintForm.sale_price)
async def add_print_price(message: types.Message, state: FSMContext):
    try:
        sale_price = float(message.text)
        data = await state.get_data()
        user_id = str(message.from_user.id)

        async with aiosqlite.connect(DB_PATH) as db:
            # Получаем настройки
            async with db.execute('SELECT * FROM printer_settings WHERE user_id = ?', (user_id,)) as cursor:
                settings = await cursor.fetchone()

            printer_cost = settings[1]
            amortization_months = settings[2]
            electricity_cost = settings[3]
            printer_power = settings[4]

            # Расчеты
            spool = data['selected_spool']
            weight = data['weight']
            hours = data['hours']

            material_cost = weight * spool[5]  # price_per_gram
            electricity_cost_calc = hours * printer_power * electricity_cost
            amortization = hours * (printer_cost / amortization_months) / (30 * 24)
            total_cost = material_cost + electricity_cost_calc + amortization
            profit = sale_price - total_cost

            # Сохраняем печать
            await db.execute('''
                INSERT INTO prints (
                    user_id, date, name, spool_name, weight, hours,
                    sale_price, material_cost, electricity_cost_calc,
                    amortization, total_cost, profit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, datetime.now().date().isoformat(), data['name'],
                spool[2], weight, hours, sale_price, material_cost,
                electricity_cost_calc, amortization, total_cost, profit
            ))
            await db.commit()

        profit_emoji = "💚" if profit >= 0 else "❤️"
        text = (
            f"✅ *Печать добавлена!*\n\n"
            f"📝 Деталь: {data['name']}\n"
            f"🧵 Катушка: {spool[2]}\n"
            f"⚖️ Вес: {weight:.0f} г\n"
            f"⏱️ Время: {hours:.1f} ч\n\n"
            f"💰 *Финансы:*\n"
            f"├ Материал: {material_cost:.2f} ₽\n"
            f"├ Электричество: {electricity_cost_calc:.2f} ₽\n"
            f"├ Амортизация: {amortization:.2f} ₽\n"
            f"├ *Себестоимость: {total_cost:.2f} ₽*\n"
            f"├ Цена продажи: {sale_price:.2f} ₽\n"
            f"└ {profit_emoji} *Прибыль: {profit:.2f} ₽*"
        )

        await message.answer(text, reply_markup=main_menu(), parse_mode="Markdown")
        await state.clear()
    except Exception as e:
        logger.error(f"Error adding print: {e}")
        await message.answer("❌ Ошибка при добавлении печати", reply_markup=main_menu())
        await state.clear()

# Настройки
@dp.callback_query(F.data == "settings")
async def show_settings(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM printer_settings WHERE user_id = ?', (user_id,)) as cursor:
            settings = await cursor.fetchone()

        text = (
            f"⚙️ *Настройки принтера*\n\n"
            f"💰 Стоимость принтера: {settings[1]:.0f} ₽\n"
            f"📅 Срок амортизации: {settings[2]} мес\n"
            f"⚡ Стоимость электричества: {settings[3]:.2f} ₽/кВт·ч\n"
            f"🔌 Мощность принтера: {settings[4]:.2f} кВт\n\n"
            f"_Настройки можно изменить в базе данных_"
        )

        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    await callback.answer()

# Назад
@dp.callback_query(F.data == "back")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=main_menu()
    )
    await callback.answer()

# Запуск
async def main():
    await init_db()
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
