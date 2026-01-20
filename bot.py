import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from supabase import create_client, Client
from datetime import datetime
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://dlfqzerwhxoyvzolxoux.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsZnF6ZXJ3aHhveXZ6b2x4b3V4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg3NjE4MTgsImV4cCI6MjA4NDMzNzgxOH0.YN8PEk0BJk4DEYGXhSPXR0la3ZZgkp1MjJhLz_J2tF4')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# States
class PrintForm(StatesGroup):
    name = State()
    spool_id = State()
    weight = State()
    hours = State()
    sale_price = State()

class SpoolForm(StatesGroup):
    name = State()
    cost = State()
    weight = State()

# Главное меню
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Сводка", callback_data="dashboard")],
        [InlineKeyboardButton(text="📝 Добавить печать", callback_data="add_print")],
        [InlineKeyboardButton(text="🧵 Управление катушками", callback_data="spools")],
        [InlineKeyboardButton(text="⚙️ Настройки принтера", callback_data="settings")]
    ])
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)

    # Инициализация настроек пользователя
    try:
        result = supabase.table('printer_settings').select('*').eq('user_id', user_id).execute()
        if not result.data:
            # Создаем настройки по умолчанию
            supabase.table('printer_settings').insert({
                'user_id': user_id,
                'printer_cost': 50000,
                'amortization_months': 24,
                'electricity_cost': 6,
                'printer_power': 0.3
            }).execute()
    except Exception as e:
        logger.error(f"Error initializing user settings: {e}")

    await message.answer(
        "🖨️ *Калькулятор заработка 3D принтера*\n\n"
        "Я помогу вам отслеживать расходы и доходы от 3D печати.\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# Сводка
@dp.callback_query(F.data == "dashboard")
async def show_dashboard(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    try:
        # Получаем все печати пользователя
        prints = supabase.table('prints').select('*').eq('user_id', user_id).execute()

        if not prints.data:
            await callback.message.edit_text(
                "📊 *Сводка*\n\n"
                "У вас пока нет печатей. Добавьте первую печать!",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return

        total_profit = sum(float(p['profit']) for p in prints.data)
        total_revenue = sum(float(p['sale_price']) for p in prints.data)
        total_cost = sum(float(p['total_cost']) for p in prints.data)
        total_plastic = sum(float(p['weight']) for p in prints.data)

        text = (
            f"📊 *Сводка*\n\n"
            f"💰 Чистая прибыль: {total_profit:.2f} ₽\n"
            f"📈 Общая выручка: {total_revenue:.2f} ₽\n"
            f"💸 Себестоимость: {total_cost:.2f} ₽\n"
            f"🧵 Израсходовано: {total_plastic:.0f} г\n"
            f"📝 Всего печатей: {len(prints.data)}"
        )

        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error showing dashboard: {e}")
        await callback.answer("Ошибка при загрузке данных", show_alert=True)

# Управление катушками
@dp.callback_query(F.data == "spools")
async def show_spools(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    try:
        spools = supabase.table('spools').select('*').eq('user_id', user_id).execute()

        if not spools.data:
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
            return

        text = "🧵 *Ваши катушки:*\n\n"
        for spool in spools.data:
            text += (
                f"• *{spool['name']}*\n"
                f"  Стоимость: {float(spool['cost']):.2f} ₽\n"
                f"  Вес: {float(spool['weight']):.0f} г\n"
                f"  Цена за грамм: {float(spool['price_per_gram']):.2f} ₽/г\n\n"
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить катушку", callback_data="add_spool")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error showing spools: {e}")
        await callback.answer("Ошибка при загрузке катушек", show_alert=True)

# Добавление катушки
@dp.callback_query(F.data == "add_spool")
async def add_spool_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🧵 Введите название катушки (например, 'PLA Белый'):")
    await state.set_state(SpoolForm.name)

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

        # Добавляем катушку в базу
        supabase.table('spools').insert({
            'user_id': user_id,
            'name': data['name'],
            'cost': data['cost'],
            'weight': weight,
            'price_per_gram': data['cost'] / weight
        }).execute()

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

    # Проверяем наличие катушек
    spools = supabase.table('spools').select('*').eq('user_id', user_id).execute()
    if not spools.data:
        await callback.message.edit_text(
            "❌ Сначала добавьте катушку пластика!",
            reply_markup=main_menu()
        )
        return

    await callback.message.edit_text("📝 Введите название детали:")
    await state.set_state(PrintForm.name)

@dp.message(PrintForm.name)
async def add_print_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)

    # Показываем список катушек
    user_id = str(message.from_user.id)
    spools = supabase.table('spools').select('*').eq('user_id', user_id).execute()

    text = "🧵 Выберите катушку (отправьте номер):\n\n"
    for idx, spool in enumerate(spools.data, 1):
        text += f"{idx}. {spool['name']} ({float(spool['price_per_gram']):.2f} ₽/г)\n"

    await state.update_data(spools=spools.data)
    await message.answer(text)
    await state.set_state(PrintForm.spool_id)

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
        await message.answer("⚖️ Введите вес израсходованного пластика в граммах:")
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
        await message.answer("❌ Неверный формат. Введите число (например, 150):")

@dp.message(PrintForm.hours)
async def add_print_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
        await state.update_data(hours=hours)
        await message.answer("💵 Введите цену продажи в рублях:")
        await state.set_state(PrintForm.sale_price)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например, 5.5):")

@dp.message(PrintForm.sale_price)
async def add_print_price(message: types.Message, state: FSMContext):
    try:
        sale_price = float(message.text)
        data = await state.get_data()
        user_id = str(message.from_user.id)

        # Получаем настройки принтера
        settings = supabase.table('printer_settings').select('*').eq('user_id', user_id).single().execute()
        printer_cost = float(settings.data['printer_cost'])
        amortization_months = int(settings.data['amortization_months'])
        electricity_cost = float(settings.data['electricity_cost'])
        printer_power = float(settings.data['printer_power'])

        # Расчеты
        spool = data['selected_spool']
        weight = data['weight']
        hours = data['hours']

        material_cost = weight * float(spool['price_per_gram'])
        electricity_cost_calc = hours * printer_power * electricity_cost
        amortization = hours * (printer_cost / amortization_months) / (30 * 24)
        total_cost = material_cost + electricity_cost_calc + amortization
        profit = sale_price - total_cost

        # Сохраняем в базу
        supabase.table('prints').insert({
            'user_id': user_id,
            'date': datetime.now().date().isoformat(),
            'name': data['name'],
            'spool_name': spool['name'],
            'weight': weight,
            'hours': hours,
            'sale_price': sale_price,
            'material_cost': material_cost,
            'electricity_cost_calc': electricity_cost_calc,
            'amortization': amortization,
            'total_cost': total_cost,
            'profit': profit
        }).execute()

        # Формируем отчет
        profit_emoji = "💚" if profit >= 0 else "❤️"
        text = (
            f"✅ *Печать добавлена!*\n\n"
            f"📝 Деталь: {data['name']}\n"
            f"🧵 Катушка: {spool['name']}\n"
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
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")
    except Exception as e:
        logger.error(f"Error adding print: {e}")
        await message.answer("❌ Ошибка при добавлении печати", reply_markup=main_menu())
        await state.clear()

# Настройки принтера
@dp.callback_query(F.data == "settings")
async def show_settings(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    try:
        settings = supabase.table('printer_settings').select('*').eq('user_id', user_id).single().execute()

        text = (
            f"⚙️ *Настройки принтера*\n\n"
            f"💰 Стоимость принтера: {float(settings.data['printer_cost']):.0f} ₽\n"
            f"📅 Срок амортизации: {settings.data['amortization_months']} мес\n"
            f"⚡ Стоимость электричества: {float(settings.data['electricity_cost']):.2f} ₽/кВт·ч\n"
            f"🔌 Мощность принтера: {float(settings.data['printer_power']):.2f} кВт\n\n"
            f"Для изменения настроек используйте веб-версию"
        )

        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await callback.answer("Ошибка при загрузке настроек", show_alert=True)

# Назад в главное меню
@dp.callback_query(F.data == "back")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=main_menu()
    )

# Запуск бота
async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
