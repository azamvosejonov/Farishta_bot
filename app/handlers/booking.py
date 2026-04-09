from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, time, datetime

from app.database.engine import async_session
from app.database.crud import (
    get_available_dates, get_available_slots, create_booking,
    get_apartment, update_user_phone, DAYS_UZ,
    get_all_admins, get_setting,
)
from app.keyboards import (
    booking_dates_kb, booking_times_kb, phone_request_kb, main_menu_kb
)
from app.config import ADMIN_ID, OFFICE_ADDRESS, OFFICE_LATITUDE, OFFICE_LONGITUDE
from app.handlers.utils import safe_callback_answer

router = Router()


class BookingState(StatesGroup):
    waiting_phone = State()


@router.callback_query(F.data.startswith("book:"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    apartment_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        dates = await get_available_dates(session)

    if not dates:
        await safe_callback_answer(callback, "❌ Hozircha bo'sh kun yo'q. Admin jadval belgilamagan.", show_alert=True)
        return

    await state.update_data(apartment_id=apartment_id)
    await callback.message.answer(
        "📅 <b>Ofisga tashrif buyurish uchun kunni tanlang:</b>",
        reply_markup=booking_dates_kb(dates, apartment_id),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("bdate:"))
async def select_booking_date(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    apartment_id = int(parts[1])
    date_str = parts[2]
    target_date = date.fromisoformat(date_str)

    async with async_session() as session:
        slots = await get_available_slots(session, target_date)

    if not slots:
        await safe_callback_answer(callback, "❌ Bu kunda bo'sh vaqt qolmagan.", show_alert=True)
        return

    day_name = DAYS_UZ.get(target_date.weekday(), "")
    await state.update_data(apartment_id=apartment_id, booking_date=date_str)

    await callback.message.edit_text(
        f"🕐 <b>{target_date.strftime('%d.%m.%Y')} {day_name}</b>\n\nVaqtni tanlang:",
        reply_markup=booking_times_kb(slots, apartment_id, date_str),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("btime:"))
async def select_booking_time(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    apartment_id = int(parts[1])
    date_str = parts[2]
    time_str = parts[3] + ":" + parts[4]  # HH:MM

    await state.update_data(
        apartment_id=apartment_id,
        booking_date=date_str,
        booking_time=time_str
    )

    await callback.message.delete()
    await callback.message.answer(
        "📱 <b>Iltimos, telefon raqamingizni yuboring:</b>\n\n"
        "Quyidagi tugmani bosing yoki raqamni qo'lda kiriting (masalan: +998901234567):",
        reply_markup=phone_request_kb(),
        parse_mode="HTML"
    )
    await state.set_state(BookingState.waiting_phone)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bron bekor qilindi.")
    await safe_callback_answer(callback)


@router.message(BookingState.waiting_phone, F.contact)
async def receive_contact(message: Message, state: FSMContext, bot: Bot):
    phone = message.contact.phone_number
    await _finalize_booking(message, state, bot, phone)


@router.message(BookingState.waiting_phone, F.text)
async def receive_phone_text(message: Message, state: FSMContext, bot: Bot):
    phone = message.text.strip()
    if not phone.replace("+", "").replace(" ", "").isdigit() or len(phone) < 9:
        await message.answer("❌ Noto'g'ri raqam. Iltimos, qayta kiriting (masalan: +998901234567):")
        return
    await _finalize_booking(message, state, bot, phone)


async def _finalize_booking(message: Message, state: FSMContext, bot: Bot, phone: str):
    data = await state.get_data()
    apartment_id = data.get("apartment_id")
    date_str = data.get("booking_date")
    time_str = data.get("booking_time")

    if not all([apartment_id, date_str, time_str]):
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan boshlang.", reply_markup=main_menu_kb())
        await state.clear()
        return

    booking_date = date.fromisoformat(date_str)
    hour, minute = map(int, time_str.split(":"))
    booking_time = time(hour, minute)

    async with async_session() as session:
        await update_user_phone(session, message.from_user.id, phone)
        booking = await create_booking(
            session, message.from_user.id, message.from_user.full_name,
            phone, apartment_id, booking_date, booking_time
        )
        apt = await get_apartment(session, apartment_id)
        saved_addr = await get_setting(session, "office_address")
        saved_lat = await get_setting(session, "office_lat")
        saved_lon = await get_setting(session, "office_lon")
        admins = await get_all_admins(session)

    if not booking:
        await message.answer(
            "❌ Bu vaqt allaqachon band qilingan. Iltimos, boshqa vaqt tanlang.",
            reply_markup=main_menu_kb()
        )
        await state.clear()
        return

    addr = saved_addr or OFFICE_ADDRESS
    lat = float(saved_lat) if saved_lat else OFFICE_LATITUDE
    lon = float(saved_lon) if saved_lon else OFFICE_LONGITUDE
    day_name = DAYS_UZ.get(booking_date.weekday(), "")

    # Uchrashuv vaqtigacha qancha qoldi
    now = datetime.now()
    booking_dt = datetime.combine(booking_date, booking_time)
    delta = booking_dt - now
    days_left = delta.days
    hours_left = delta.seconds // 3600
    countdown = ""
    if days_left > 0:
        countdown = f"⏳ Uchrashuvgacha: {days_left} kun {hours_left} soat"
    elif days_left == 0 and hours_left > 0:
        countdown = f"⏳ Uchrashuvgacha: {hours_left} soat"

    # Mijozga xabar
    await message.answer(
        f"✅ <b>Bron muvaffaqiyatli!</b>\n\n"
        f"📅 Sana: <b>{booking_date.strftime('%d.%m.%Y')} {day_name}</b>\n"
        f"🕐 Vaqt: <b>{time_str}</b>\n"
        f"📱 Telefon: {phone}\n"
        f"{countdown}\n\n"
        f"📍 <b>Ofis manzili:</b>\n{addr}\n\n"
        f"Sizni kutamiz! 🤝",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await message.answer_location(latitude=lat, longitude=lon)

    # Adminga bildirish — to'liq ma'lumotlar
    apt_info = ""
    if apt:
        floor = apt.floor
        building = floor.building
        apt_info = (
            f"\n\n🏢 <b>Kvartira ma'lumotlari:</b>"
            f"\n🏢 Bino: {building.name}"
            f"\n📐 Qavat: {floor.floor_number}"
            f"\n🏠 Kvartira: {apt.apartment_number} ({apt.rooms} xona, {apt.area}m²)"
            f"\n💰 Narx: {apt.price:,.0f} so'm"
        )
        if apt.installment_available:
            apt_info += f"\n💳 Bo'lib to'lash: ✅ ({apt.initial_payment_percent}%, {apt.installment_months} oy)"

    admin_text = (
        f"🔔 <b>YANGI UCHRASHUV BELGILANDI!</b>\n\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"📱 Telefon: {phone}\n"
        f"🆔 Telegram: @{message.from_user.username or 'yo`q'}\n"
        f"📅 Sana: {booking_date.strftime('%d.%m.%Y')} {day_name}\n"
        f"🕐 Vaqt: {time_str}\n"
        f"{countdown}"
        f"{apt_info}"
    )

    # Barcha adminlarga yuborish
    admin_ids = [ADMIN_ID] + [adm.user_id for adm in admins]
    admin_ids = list(set(admin_ids))
    for aid in admin_ids:
        try:
            await bot.send_message(aid, admin_text, parse_mode="HTML")
        except Exception:
            pass

    await state.clear()
