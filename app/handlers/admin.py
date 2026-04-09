from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import time
import asyncio

from app.database.engine import async_session
from app.database.crud import (
    get_all_buildings, get_building, create_building, delete_building,
    update_building_photo, get_floors_by_building, get_floor, create_floor,
    update_floor_photo, get_apartments_by_floor, get_apartment,
    create_apartment, update_apartment_status, update_apartment_price,
    update_apartment_photos, bulk_create_apartments,
    get_all_schedules, set_schedule, remove_schedule,
    get_upcoming_bookings, cancel_booking,
    add_construction_report, get_stats, get_full_stats, get_all_users, DAYS_UZ,
    is_admin_user, is_superadmin, add_admin, remove_admin, get_all_admins,
    create_faq, get_all_faq, delete_faq,
    set_installment, set_setting, get_setting,
)
from app.keyboards import (
    admin_main_kb, admin_buildings_kb, admin_building_detail_kb,
    admin_floors_kb, admin_floor_detail_kb, admin_apt_list_kb,
    admin_apt_detail_kb, admin_schedule_kb, admin_schedule_day_kb,
    admin_construction_building_kb, confirm_broadcast_kb
)
from app.config import ADMIN_ID, ADMIN_SECRET

router = Router()


# ==================== FILTER ====================

async def check_admin(user_id: int) -> bool:
    async with async_session() as session:
        return await is_admin_user(session, user_id)


# ==================== STATES ====================

class AdminStates(StatesGroup):
    # Building
    add_building_name = State()
    add_building_address = State()
    add_building_floors = State()
    building_photo = State()
    # Floor
    add_floor_number = State()
    floor_photo = State()
    # Apartment
    add_apt_number = State()
    add_apt_rooms = State()
    add_apt_area = State()
    add_apt_price = State()
    add_apt_desc = State()
    add_apt_photos = State()
    # Bulk
    bulk_apt_number = State()
    bulk_rooms = State()
    bulk_area = State()
    bulk_price = State()
    bulk_desc = State()
    bulk_photos = State()
    bulk_from_floor = State()
    bulk_to_floor = State()
    # Apartment edit
    apt_new_price = State()
    apt_new_photos = State()
    # Installment
    inst_initial_pct = State()
    inst_months = State()
    # Schedule
    schedule_time = State()
    # Construction
    construction_title = State()
    construction_desc = State()
    construction_media = State()
    # Broadcast
    broadcast_message = State()
    # Admin management
    add_admin_id = State()
    add_admin_name = State()
    # FAQ
    faq_question = State()
    faq_answer = State()
    # Address
    address_text = State()
    address_location = State()


# ==================== ADMIN ENTRY ====================

@router.message(F.text.startswith("/admin"))
async def admin_entry(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    if message.text.strip() != ADMIN_SECRET:
        return
    await state.clear()
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\nBoshqaruvni tanlang:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "adm:main")
async def admin_main(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\nBoshqaruvni tanlang:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== BUILDINGS MANAGEMENT ====================

@router.callback_query(F.data == "adm:buildings")
async def admin_buildings(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await state.clear()
    async with async_session() as session:
        buildings = await get_all_buildings(session)
    await callback.message.edit_text(
        "🏢 <b>Binolarni boshqarish:</b>",
        reply_markup=admin_buildings_kb(buildings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "adm:add_building")
async def admin_add_building(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🏢 Yangi bino nomini kiriting:")
    await state.set_state(AdminStates.add_building_name)
    await callback.answer()


@router.message(AdminStates.add_building_name)
async def admin_building_name(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await state.update_data(building_name=message.text)
    await message.answer("📍 Bino manzilini kiriting (yoki '-' bosing):")
    await state.set_state(AdminStates.add_building_address)


@router.message(AdminStates.add_building_address)
async def admin_building_address(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    address = message.text if message.text != "-" else None
    await state.update_data(building_address=address)
    await message.answer("🏗 Qavatlar sonini kiriting (masalan: 12):")
    await state.set_state(AdminStates.add_building_floors)


@router.message(AdminStates.add_building_floors)
async def admin_building_floors(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        total_floors = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    data = await state.get_data()
    async with async_session() as session:
        building = await create_building(
            session, data["building_name"], data.get("building_address"), total_floors
        )
        # Auto-create floors
        for i in range(1, total_floors + 1):
            await create_floor(session, building.id, i)

    await message.answer(
        f"✅ <b>{building.name}</b> binosi yaratildi!\n"
        f"📐 {total_floors} ta qavat avtomatik qo'shildi.\n\n"
        f"Endi bino fasadi rasmini yuborasizmi?",
        reply_markup=admin_building_detail_kb(building.id),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm_b:"))
async def admin_building_detail(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        building = await get_building(session, building_id)
        stats = await get_stats(session, building_id)
    if not building:
        await callback.answer("Topilmadi", show_alert=True)
        return
    await callback.message.edit_text(
        f"🏢 <b>{building.name}</b>\n"
        f"📍 {building.address or '-'}\n"
        f"📐 Qavatlar: {building.total_floors}\n"
        f"🏠 Jami kvartiralar: {stats['total']}\n"
        f"🟢 Sotuvda: {stats['available']} | 🔴 Sotilgan: {stats['sold']}",
        reply_markup=admin_building_detail_kb(building_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_bphoto:"))
async def admin_building_photo(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    await state.update_data(building_id=building_id)
    await callback.message.edit_text("🖼 Bino fasadi rasmini yuboring:")
    await state.set_state(AdminStates.building_photo)
    await callback.answer()


@router.message(AdminStates.building_photo, F.photo)
async def admin_building_photo_receive(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    async with async_session() as session:
        await update_building_photo(session, data["building_id"], photo_id)
    await message.answer(
        "✅ Fasad rasmi saqlandi!",
        reply_markup=admin_building_detail_kb(data["building_id"]),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm_bdel:"))
async def admin_building_delete(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await delete_building(session, building_id)
        buildings = await get_all_buildings(session)
    await callback.message.edit_text(
        "🗑 Bino o'chirildi!\n\n🏢 <b>Binolarni boshqarish:</b>",
        reply_markup=admin_buildings_kb(buildings),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== FLOORS MANAGEMENT ====================

@router.callback_query(F.data.startswith("adm_floors:"))
async def admin_floors(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        floors = await get_floors_by_building(session, building_id)
    await callback.message.edit_text(
        "📐 <b>Qavatlar:</b>",
        reply_markup=admin_floors_kb(floors, building_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_addfl:"))
async def admin_add_floor(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    await state.update_data(building_id=building_id)
    await callback.message.edit_text("📐 Qavat raqamini kiriting:")
    await state.set_state(AdminStates.add_floor_number)
    await callback.answer()


@router.message(AdminStates.add_floor_number)
async def admin_floor_number(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        floor_number = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    data = await state.get_data()
    async with async_session() as session:
        await create_floor(session, data["building_id"], floor_number)
        floors = await get_floors_by_building(session, data["building_id"])
    await message.answer(
        f"✅ {floor_number}-qavat qo'shildi!",
        reply_markup=admin_floors_kb(floors, data["building_id"]),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm_fl:"))
async def admin_floor_detail(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    floor_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        floor = await get_floor(session, floor_id)
    if not floor:
        await callback.answer("Topilmadi", show_alert=True)
        return
    await callback.message.edit_text(
        f"📐 <b>{floor.floor_number}-qavat</b>",
        reply_markup=admin_floor_detail_kb(floor_id, floor.building_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_flphoto:"))
async def admin_floor_photo(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    floor_id = int(callback.data.split(":")[1])
    await state.update_data(floor_id=floor_id)
    await callback.message.edit_text("🖼 Qavat plani rasmini yuboring:")
    await state.set_state(AdminStates.floor_photo)
    await callback.answer()


@router.message(AdminStates.floor_photo, F.photo)
async def admin_floor_photo_receive(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    async with async_session() as session:
        await update_floor_photo(session, data["floor_id"], photo_id)
        floor = await get_floor(session, data["floor_id"])
    await message.answer(
        f"✅ Qavat plani rasmi saqlandi!",
        reply_markup=admin_floor_detail_kb(data["floor_id"], floor.building_id),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== APARTMENTS MANAGEMENT ====================

@router.callback_query(F.data.startswith("adm_flapts:"))
async def admin_floor_apartments(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    floor_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        apartments = await get_apartments_by_floor(session, floor_id)
    await callback.message.edit_text(
        "🏠 <b>Kvartiralar:</b>",
        reply_markup=admin_apt_list_kb(apartments, floor_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_addapt:"))
async def admin_add_apartment(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    floor_id = int(callback.data.split(":")[1])
    await state.update_data(floor_id=floor_id)
    await callback.message.edit_text("🏠 Kvartira raqamini kiriting (1, 2, 3 yoki 4):")
    await state.set_state(AdminStates.add_apt_number)
    await callback.answer()


@router.message(AdminStates.add_apt_number)
async def admin_apt_number(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        num = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(apt_number=num)
    await message.answer("🛏 Xonalar sonini kiriting (masalan: 3):")
    await state.set_state(AdminStates.add_apt_rooms)


@router.message(AdminStates.add_apt_rooms)
async def admin_apt_rooms(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        rooms = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(apt_rooms=rooms)
    await message.answer("📏 Maydonini kiriting m² (masalan: 85.5):")
    await state.set_state(AdminStates.add_apt_area)


@router.message(AdminStates.add_apt_area)
async def admin_apt_area(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        area = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(apt_area=area)
    await message.answer("💰 Narxni kiriting so'mda (masalan: 500000000):")
    await state.set_state(AdminStates.add_apt_price)


@router.message(AdminStates.add_apt_price)
async def admin_apt_price(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(apt_price=price)
    await message.answer("📝 Tavsif kiriting (yoki '-' bosing):")
    await state.set_state(AdminStates.add_apt_desc)


@router.message(AdminStates.add_apt_desc)
async def admin_apt_desc(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    desc = message.text if message.text != "-" else None
    await state.update_data(apt_desc=desc, apt_photos=[])
    await message.answer(
        "🖼 Kvartira rasmlarini yuboring (1 dan 10 gacha).\n"
        "Tugagach, /done buyrug'ini yuboring:"
    )
    await state.set_state(AdminStates.add_apt_photos)


@router.message(AdminStates.add_apt_photos, F.photo)
async def admin_apt_photos(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    photos = data.get("apt_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(apt_photos=photos)
    await message.answer(f"📸 {len(photos)} ta rasm qabul qilindi. Yana yuboring yoki /done bosing.")


@router.message(AdminStates.add_apt_photos, F.text == "/done")
async def admin_apt_photos_done(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        apt = await create_apartment(
            session, data["floor_id"], data["apt_number"], data["apt_rooms"],
            data["apt_area"], data["apt_price"], data.get("apt_desc"),
            data.get("apt_photos", [])
        )
        apartments = await get_apartments_by_floor(session, data["floor_id"])
    await message.answer(
        f"✅ {apt.apartment_number}-kvartira qo'shildi!",
        reply_markup=admin_apt_list_kb(apartments, data["floor_id"]),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== APARTMENT DETAIL (ADMIN) ====================

@router.callback_query(F.data.startswith("adm_apt:"))
async def admin_apt_detail(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        apt = await get_apartment(session, apt_id)
    if not apt:
        await callback.answer("Topilmadi", show_alert=True)
        return
    status = "🔴 Sotilgan" if apt.is_sold else "🟢 Sotuvda"
    await callback.message.edit_text(
        f"🏠 <b>{apt.apartment_number}-kvartira</b>\n"
        f"🛏 Xonalar: {apt.rooms}\n"
        f"📏 Maydon: {apt.area} m²\n"
        f"💰 Narx: {apt.price:,.0f} so'm\n"
        f"📊 Status: {status}\n"
        f"🖼 Rasmlar: {len(apt.photos or [])} ta",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_apt_sell:"))
async def admin_apt_sell(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await update_apartment_status(session, apt_id, True)
        apt = await get_apartment(session, apt_id)
    await callback.answer("🔴 Sotildi deb belgilandi!", show_alert=True)
    status = "🔴 Sotilgan"
    await callback.message.edit_text(
        f"🏠 <b>{apt.apartment_number}-kvartira</b>\n"
        f"🛏 Xonalar: {apt.rooms}\n"
        f"📏 Maydon: {apt.area} m²\n"
        f"💰 Narx: {apt.price:,.0f} so'm\n"
        f"📊 Status: {status}\n"
        f"🖼 Rasmlar: {len(apt.photos or [])} ta",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_apt_unsell:"))
async def admin_apt_unsell(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await update_apartment_status(session, apt_id, False)
        apt = await get_apartment(session, apt_id)
    await callback.answer("🟢 Sotuvga qaytarildi!", show_alert=True)
    status = "🟢 Sotuvda"
    await callback.message.edit_text(
        f"🏠 <b>{apt.apartment_number}-kvartira</b>\n"
        f"🛏 Xonalar: {apt.rooms}\n"
        f"📏 Maydon: {apt.area} m²\n"
        f"💰 Narx: {apt.price:,.0f} so'm\n"
        f"📊 Status: {status}\n"
        f"🖼 Rasmlar: {len(apt.photos or [])} ta",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_apt_price:"))
async def admin_apt_price_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    await state.update_data(edit_apt_id=apt_id)
    await callback.message.edit_text("💰 Yangi narxni kiriting so'mda:")
    await state.set_state(AdminStates.apt_new_price)
    await callback.answer()


@router.message(AdminStates.apt_new_price)
async def admin_apt_price_set(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    data = await state.get_data()
    async with async_session() as session:
        await update_apartment_price(session, data["edit_apt_id"], price)
        apt = await get_apartment(session, data["edit_apt_id"])
    await message.answer(
        f"✅ Narx yangilandi: {price:,.0f} so'm",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm_apt_photos:"))
async def admin_apt_photos_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    await state.update_data(edit_apt_id=apt_id, new_apt_photos=[])
    await callback.message.edit_text(
        "🖼 Yangi rasmlarni yuboring.\nTugagach /done bosing.\n\n"
        "⚠️ Eski rasmlar yangilari bilan almashtiriladi."
    )
    await state.set_state(AdminStates.apt_new_photos)
    await callback.answer()


@router.message(AdminStates.apt_new_photos, F.photo)
async def admin_apt_photos_recv(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    photos = data.get("new_apt_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(new_apt_photos=photos)
    await message.answer(f"📸 {len(photos)} ta rasm. Yana yuboring yoki /done bosing.")


@router.message(AdminStates.apt_new_photos, F.text == "/done")
async def admin_apt_photos_save(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await update_apartment_photos(session, data["edit_apt_id"], data.get("new_apt_photos", []))
        apt = await get_apartment(session, data["edit_apt_id"])
    await message.answer(
        f"✅ Rasmlar yangilandi!",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== BULK UPLOAD ====================

@router.callback_query(F.data.startswith("adm_bulk:"))
async def admin_bulk_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    await state.update_data(bulk_building_id=building_id)
    await callback.message.edit_text(
        "📋 <b>Shablon yaratish (Bulk Upload)</b>\n\n"
        "Kvartira raqamini kiriting (1, 2, 3 yoki 4).\n"
        "Bu raqam barcha tanlangan qavatlarga qo'llaniladi:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.bulk_apt_number)
    await callback.answer()


@router.message(AdminStates.bulk_apt_number)
async def admin_bulk_number(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        num = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(bulk_apt_num=num)
    await message.answer("🛏 Xonalar soni:")
    await state.set_state(AdminStates.bulk_rooms)


@router.message(AdminStates.bulk_rooms)
async def admin_bulk_rooms(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        rooms = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(bulk_rooms=rooms)
    await message.answer("📏 Maydon m²:")
    await state.set_state(AdminStates.bulk_area)


@router.message(AdminStates.bulk_area)
async def admin_bulk_area(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        area = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(bulk_area=area)
    await message.answer("💰 Narx so'mda:")
    await state.set_state(AdminStates.bulk_price)


@router.message(AdminStates.bulk_price)
async def admin_bulk_price(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(bulk_price=price)
    await message.answer("📝 Tavsif (yoki '-'):")
    await state.set_state(AdminStates.bulk_desc)


@router.message(AdminStates.bulk_desc)
async def admin_bulk_desc(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    desc = message.text if message.text != "-" else None
    await state.update_data(bulk_desc=desc, bulk_photos=[])
    await message.answer("🖼 Rasmlarni yuboring. Tugagach /done bosing:")
    await state.set_state(AdminStates.bulk_photos)


@router.message(AdminStates.bulk_photos, F.photo)
async def admin_bulk_photos(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    photos = data.get("bulk_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(bulk_photos=photos)
    await message.answer(f"📸 {len(photos)} ta rasm. /done bosing yoki yana yuboring.")


@router.message(AdminStates.bulk_photos, F.text == "/done")
async def admin_bulk_photos_done(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await message.answer("📐 Nechanchi qavatdan? (masalan: 2):")
    await state.set_state(AdminStates.bulk_from_floor)


@router.message(AdminStates.bulk_from_floor)
async def admin_bulk_from(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        f = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(bulk_from=f)
    await message.answer("📐 Nechanchi qavatgacha? (masalan: 12):")
    await state.set_state(AdminStates.bulk_to_floor)


@router.message(AdminStates.bulk_to_floor)
async def admin_bulk_to(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        t = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    data = await state.get_data()

    async with async_session() as session:
        created = await bulk_create_apartments(
            session, data["bulk_building_id"], data["bulk_apt_num"],
            data["bulk_rooms"], data["bulk_area"], data["bulk_price"],
            data.get("bulk_desc"), data.get("bulk_photos", []),
            data["bulk_from"], t
        )

    await message.answer(
        f"✅ <b>Shablon qo'llanildi!</b>\n"
        f"📊 {len(created)} ta kvartira yaratildi\n"
        f"({data['bulk_apt_num']}-raqamli, {data['bulk_from']}-qavatdan {t}-qavatgacha)",
        reply_markup=admin_building_detail_kb(data["bulk_building_id"]),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== SCHEDULE ====================

@router.callback_query(F.data == "adm:schedule")
async def admin_schedule(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await state.clear()
    async with async_session() as session:
        schedules = await get_all_schedules(session)
    await callback.message.edit_text(
        "📅 <b>Ish jadvali</b>\n\n"
        "Kunni tanlang va vaqt belgilang.\n"
        "✅ = Faol | ⬜ = O'chirilgan",
        reply_markup=admin_schedule_kb(schedules),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sched:"))
async def admin_schedule_day(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    day_num = int(callback.data.split(":")[1])
    async with async_session() as session:
        schedules = await get_all_schedules(session)
    is_active = day_num in {s.day_of_week for s in schedules}
    await callback.message.edit_text(
        f"📅 <b>{DAYS_UZ[day_num]}</b>",
        reply_markup=admin_schedule_day_kb(day_num, is_active),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sched_set:"))
async def admin_schedule_set(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    day_num = int(callback.data.split(":")[1])
    await state.update_data(sched_day=day_num)
    await callback.message.edit_text(
        f"📅 <b>{DAYS_UZ[day_num]}</b>\n\n"
        "Ish vaqtini kiriting (masalan: 10:00-16:00):"
    )
    await state.set_state(AdminStates.schedule_time)
    await callback.answer()


@router.message(AdminStates.schedule_time)
async def admin_schedule_time(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        parts = message.text.replace(" ", "").split("-")
        start_h, start_m = map(int, parts[0].split(":"))
        end_h, end_m = map(int, parts[1].split(":"))
        start_time = time(start_h, start_m)
        end_time = time(end_h, end_m)
    except (ValueError, IndexError):
        await message.answer("❌ Noto'g'ri format. Masalan: 10:00-16:00")
        return

    data = await state.get_data()
    async with async_session() as session:
        await set_schedule(session, data["sched_day"], start_time, end_time)
        schedules = await get_all_schedules(session)

    await message.answer(
        f"✅ {DAYS_UZ[data['sched_day']]} ish vaqti: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}",
        reply_markup=admin_schedule_kb(schedules),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm_sched_del:"))
async def admin_schedule_delete(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    day_num = int(callback.data.split(":")[1])
    async with async_session() as session:
        await remove_schedule(session, day_num)
        schedules = await get_all_schedules(session)
    await callback.message.edit_text(
        f"✅ {DAYS_UZ[day_num]} o'chirildi!",
        reply_markup=admin_schedule_kb(schedules),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== BOOKINGS LIST ====================

@router.callback_query(F.data == "adm:bookings")
async def admin_bookings(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        bookings = await get_upcoming_bookings(session)

    if not bookings:
        await callback.message.edit_text(
            "📋 Kelgusi uchrashuvlar yo'q.",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = "📋 <b>Kelgusi uchrashuvlar:</b>\n\n"
    for b in bookings[:20]:
        day_name = DAYS_UZ.get(b.booking_date.weekday(), "")
        text += (
            f"📅 {b.booking_date.strftime('%d.%m.%Y')} {day_name} "
            f"🕐 {b.booking_time.strftime('%H:%M')}\n"
            f"👤 {b.user_fullname} | 📱 {b.user_phone or '-'}\n\n"
        )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==================== CONSTRUCTION REPORT ====================

@router.callback_query(F.data == "adm:construction")
async def admin_construction(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        buildings = await get_all_buildings(session)
    if not buildings:
        await callback.answer("Avval bino qo'shing", show_alert=True)
        return
    await callback.message.edit_text(
        "🏗 <b>Qurilish hisoboti — Binoni tanlang:</b>",
        reply_markup=admin_construction_building_kb(buildings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_constr:"))
async def admin_construction_building(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    building_id = int(callback.data.split(":")[1])
    await state.update_data(constr_building_id=building_id)
    await callback.message.edit_text("🏗 Hisobot sarlavhasini kiriting (masalan: Aprel oyi: 5-qavat yopildi):")
    await state.set_state(AdminStates.construction_title)
    await callback.answer()


@router.message(AdminStates.construction_title)
async def admin_constr_title(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await state.update_data(constr_title=message.text)
    await message.answer("📝 Qo'shimcha izoh kiriting (yoki '-'):")
    await state.set_state(AdminStates.construction_desc)


@router.message(AdminStates.construction_desc)
async def admin_constr_desc(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    desc = message.text if message.text != "-" else None
    await state.update_data(constr_desc=desc)
    await message.answer("🖼 Rasm yoki video yuboring (yoki /skip bosing):")
    await state.set_state(AdminStates.construction_media)


@router.message(AdminStates.construction_media, F.photo)
async def admin_constr_photo(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await add_construction_report(
            session, data["constr_building_id"], data["constr_title"],
            data.get("constr_desc"), message.photo[-1].file_id, "photo"
        )
    await message.answer("✅ Qurilish hisoboti saqlandi!", reply_markup=admin_main_kb())
    await state.clear()


@router.message(AdminStates.construction_media, F.video)
async def admin_constr_video(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await add_construction_report(
            session, data["constr_building_id"], data["constr_title"],
            data.get("constr_desc"), message.video.file_id, "video"
        )
    await message.answer("✅ Qurilish hisoboti saqlandi!", reply_markup=admin_main_kb())
    await state.clear()


@router.message(AdminStates.construction_media, F.text == "/skip")
async def admin_constr_skip(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await add_construction_report(
            session, data["constr_building_id"], data["constr_title"],
            data.get("constr_desc")
        )
    await message.answer("✅ Qurilish hisoboti saqlandi!", reply_markup=admin_main_kb())
    await state.clear()


# ==================== STATISTICS ====================

@router.callback_query(F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        buildings = await get_all_buildings(session)
        full = await get_full_stats(session)

    text = (
        "📊 <b>TO'LIQ STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{full['users']}</b>\n"
        f"📅 Jami uchrashuvlar: <b>{full['bookings_total']}</b>\n"
        f"  ┣ Kelgusi: {full['bookings_upcoming']}\n"
        f"  ┗ O'tgan: {full['bookings_past']}\n\n"
        f"🏠 Jami kvartiralar: <b>{full['apartments_total']}</b>\n"
        f"  ┣ 🟢 Sotuvda: {full['apartments_available']}\n"
        f"  ┗ 🔴 Sotilgan: {full['apartments_sold']}\n\n"
        f"💰 Umumiy sotuv summasi: <b>{full['total_revenue']:,.0f} so'm</b>\n\n"
    )

    for b in buildings:
        async with async_session() as session:
            stats = await get_stats(session, b.id)
        text += (
            f"🏢 <b>{b.name}</b>\n"
            f"   🏠 Jami: {stats['total']} | "
            f"🟢 Bo'sh: {stats['available']} | "
            f"🔴 Sotilgan: {stats['sold']}\n"
            f"   💰 Sotuv: {stats['revenue']:,.0f} so'm\n"
            f"   💳 Bo'lib to'lash: {stats['installment']} ta\n\n"
        )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==================== BROADCAST ====================

@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "📢 <b>Ommaviy xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:"
    )
    await state.set_state(AdminStates.broadcast_message)
    await callback.answer()


@router.message(AdminStates.broadcast_message)
async def admin_broadcast_text(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await state.update_data(broadcast_text=message.text)
    await message.answer(
        f"📢 <b>Xabar:</b>\n\n{message.text}\n\n"
        f"Yuborishni tasdiqlaysizmi?",
        reply_markup=confirm_broadcast_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "adm_broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")

    async with async_session() as session:
        users = await get_all_users(session)

    sent = 0
    failed = 0
    await callback.message.edit_text("📢 Yuborilmoqda...")

    for user in users:
        try:
            await bot.send_message(user.id, f"📢 <b>Yangilik!</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await callback.message.edit_text(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Xatolik: {failed}",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


# ==================== INSTALLMENT (BO'LIB TO'LASH) ====================

@router.callback_query(F.data.startswith("adm_inst_on:"))
async def admin_inst_on(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    await state.update_data(inst_apt_id=apt_id)
    await callback.message.edit_text(
        "💳 <b>Bo'lib to'lash sozlash</b>\n\n"
        "Boshlang'ich to'lov foizini kiriting (masalan: 30):"
    )
    await state.set_state(AdminStates.inst_initial_pct)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_inst_off:"))
async def admin_inst_off(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    apt_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await set_installment(session, apt_id, False)
        apt = await get_apartment(session, apt_id)
    await callback.answer("💳 Bo'lib to'lash o'chirildi!", show_alert=True)
    status = "🔴 Sotilgan" if apt.is_sold else "🟢 Sotuvda"
    await callback.message.edit_text(
        f"🏠 <b>{apt.apartment_number}-kvartira</b>\n"
        f"🛏 Xonalar: {apt.rooms}\n"
        f"📏 Maydon: {apt.area} m²\n"
        f"💰 Narx: {apt.price:,.0f} so'm\n"
        f"📊 Status: {status}\n"
        f"🖼 Rasmlar: {len(apt.photos or [])} ta",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )


@router.message(AdminStates.inst_initial_pct)
async def admin_inst_pct(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        pct = float(message.text.replace(",", ".").replace("%", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 30):")
        return
    await state.update_data(inst_pct=pct)
    await message.answer("📅 Necha oyga bo'lib to'lash? (masalan: 12):")
    await state.set_state(AdminStates.inst_months)


@router.message(AdminStates.inst_months)
async def admin_inst_months(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        months = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 12):")
        return
    data = await state.get_data()
    async with async_session() as session:
        await set_installment(session, data["inst_apt_id"], True, data["inst_pct"], months)
        apt = await get_apartment(session, data["inst_apt_id"])
    await message.answer(
        f"✅ Bo'lib to'lash yoqildi!\n"
        f"💳 Boshlang'ich: {data['inst_pct']}%\n"
        f"📅 Muddat: {months} oy",
        reply_markup=admin_apt_detail_kb(apt),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== MULTI ADMIN ====================

@router.callback_query(F.data == "adm:admins")
async def admin_admins_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        admins = await get_all_admins(session)

    text = "👥 <b>Adminlar ro'yxati:</b>\n\n"
    text += f"👑 Bosh admin: <code>{ADMIN_ID}</code> (superadmin)\n\n"
    for adm in admins:
        text += f"👤 {adm.name} — <code>{adm.user_id}</code> ({adm.role})\n"
    if not admins:
        text += "📭 Qo'shimcha adminlar yo'q.\n"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm:add_admin")],
        [InlineKeyboardButton(text="🗑 Admin o'chirish", callback_data="adm:remove_admin")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:add_admin")
async def admin_add_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "👤 Yangi admin Telegram ID raqamini kiriting:\n\n"
        "💡 Foydalanuvchi botga /start yozgandan keyin, uning ID sini bilish mumkin."
    )
    await state.set_state(AdminStates.add_admin_id)
    await callback.answer()


@router.message(AdminStates.add_admin_id)
async def admin_add_admin_id(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    try:
        new_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return
    await state.update_data(new_admin_id=new_id)
    await message.answer("👤 Admin ismini kiriting:")
    await state.set_state(AdminStates.add_admin_name)


@router.message(AdminStates.add_admin_name)
async def admin_add_admin_name(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await add_admin(session, data["new_admin_id"], message.text.strip())
    await message.answer(
        f"✅ Admin qo'shildi!\n"
        f"👤 {message.text.strip()} — <code>{data['new_admin_id']}</code>",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "adm:remove_admin")
async def admin_remove_admin_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        admins = await get_all_admins(session)
    if not admins:
        await callback.answer("📭 Qo'shimcha adminlar yo'q", show_alert=True)
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    for adm in admins:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {adm.name} ({adm.user_id})",
            callback_data=f"adm_deladmin:{adm.user_id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:admins")])
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan adminni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_deladmin:"))
async def admin_remove_admin_confirm(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    uid = int(callback.data.split(":")[1])
    async with async_session() as session:
        await remove_admin(session, uid)
    await callback.answer("🗑 Admin o'chirildi!", show_alert=True)
    async with async_session() as session:
        admins = await get_all_admins(session)
    text = "👥 <b>Adminlar ro'yxati:</b>\n\n"
    text += f"👑 Bosh admin: <code>{ADMIN_ID}</code>\n\n"
    for adm in admins:
        text += f"👤 {adm.name} — <code>{adm.user_id}</code> ({adm.role})\n"
    if not admins:
        text += "📭 Qo'shimcha adminlar yo'q.\n"
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm:add_admin")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ==================== FAQ MANAGEMENT ====================

@router.callback_query(F.data == "adm:faq")
async def admin_faq_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    async with async_session() as session:
        faqs = await get_all_faq(session)
    faqs = [f for f in faqs if not f.question.startswith("__setting__")]

    text = "❓ <b>FAQ boshqarish</b>\n\n"
    if not faqs:
        text += "📭 Hozircha savollar yo'q.\n"
    for i, faq in enumerate(faqs, 1):
        text += f"<b>{i}. {faq.question}</b>\n{faq.answer}\n\n"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [InlineKeyboardButton(text="➕ Savol qo'shish", callback_data="adm:add_faq")],
    ]
    for faq in faqs:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {faq.question[:30]}...",
            callback_data=f"adm_delfaq:{faq.id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")])
    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "adm:add_faq")
async def admin_add_faq_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await callback.message.edit_text("❓ Savolni kiriting:")
    await state.set_state(AdminStates.faq_question)
    await callback.answer()


@router.message(AdminStates.faq_question)
async def admin_faq_question(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await state.update_data(faq_q=message.text)
    await message.answer("✏️ Javobini kiriting:")
    await state.set_state(AdminStates.faq_answer)


@router.message(AdminStates.faq_answer)
async def admin_faq_answer(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await create_faq(session, data["faq_q"], message.text)
    await message.answer("✅ FAQ saqlandi!", reply_markup=admin_main_kb())
    await state.clear()


@router.callback_query(F.data.startswith("adm_delfaq:"))
async def admin_delete_faq(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    faq_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await delete_faq(session, faq_id)
    await callback.answer("🗑 FAQ o'chirildi!", show_alert=True)
    # Refresh list
    async with async_session() as session:
        faqs = await get_all_faq(session)
    faqs = [f for f in faqs if not f.question.startswith("__setting__")]
    text = "❓ <b>FAQ boshqarish</b>\n\n"
    if not faqs:
        text += "📭 Hozircha savollar yo'q.\n"
    for i, faq in enumerate(faqs, 1):
        text += f"<b>{i}. {faq.question}</b>\n{faq.answer}\n\n"
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [InlineKeyboardButton(text="➕ Savol qo'shish", callback_data="adm:add_faq")],
    ]
    for faq in faqs:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {faq.question[:30]}...",
            callback_data=f"adm_delfaq:{faq.id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")])
    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )


# ==================== ADDRESS SETTINGS ====================

@router.callback_query(F.data == "adm:address")
async def admin_address(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    from app.config import OFFICE_ADDRESS, OFFICE_LATITUDE, OFFICE_LONGITUDE
    async with async_session() as session:
        saved_addr = await get_setting(session, "office_address")
        saved_lat = await get_setting(session, "office_lat")
        saved_lon = await get_setting(session, "office_lon")

    addr = saved_addr or OFFICE_ADDRESS
    lat = saved_lat or str(OFFICE_LATITUDE)
    lon = saved_lon or str(OFFICE_LONGITUDE)

    text = (
        "📍 <b>Ofis manzili sozlamalari</b>\n\n"
        f"📍 Manzil: {addr}\n"
        f"🗺 Koordinata: {lat}, {lon}\n"
    )
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Manzilni o'zgartirish", callback_data="adm:set_address")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:set_address")
async def admin_set_address(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📍 Yangi ofis manzili nomini kiriting (masalan: Toshkent, Chilonzor 7-kvartal):")
    await state.set_state(AdminStates.address_text)
    await callback.answer()


@router.message(AdminStates.address_text)
async def admin_address_text(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    new_address = (message.text or "").strip()
    if not new_address:
        await message.answer(
            "❌ Manzil matn ko'rinishida yuborilishi kerak.\n\n"
            "Masalan: Toshkent, Chilonzor 7-kvartal"
        )
        return
    await state.update_data(new_address=new_address)
    await message.answer(
        "🗺 Endi ofis lokatsiyasini yuboring:\n\n"
        "📎 Telegram'da pastdagi 📎 tugmasini bosib → 📍 Location → ofis joyini tanlang va yuboring."
    )
    await state.set_state(AdminStates.address_location)


@router.message(AdminStates.address_location, F.location)
async def admin_address_location(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    lat = message.location.latitude
    lon = message.location.longitude
    data = await state.get_data()
    new_address = (data.get("new_address") or "").strip()
    if not new_address:
        await state.set_state(AdminStates.address_text)
        await message.answer(
            "❌ Avval ofis manzilini matn ko'rinishida kiriting.\n\n"
            "Masalan: Toshkent, Chilonzor 7-kvartal"
        )
        return
    async with async_session() as session:
        await set_setting(session, "office_address", new_address)
        await set_setting(session, "office_lat", str(lat))
        await set_setting(session, "office_lon", str(lon))
    await message.answer(
        f"✅ <b>Manzil yangilandi!</b>\n\n"
        f"📍 {new_address}\n"
        f"🗺 {lat}, {lon}",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await state.clear()


@router.message(AdminStates.address_location)
async def admin_address_location_invalid(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    await message.answer(
        "❌ Lokatsiya yuboring!\n\n"
        "📎 Telegram'da pastdagi 📎 tugmasini bosib → 📍 Location → ofis joyini tanlang."
    )
