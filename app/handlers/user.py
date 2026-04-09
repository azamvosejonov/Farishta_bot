from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from app.database.engine import async_session
from app.database.crud import (
    upsert_user, get_all_buildings, get_building,
    get_floor_by_number, get_apartments_by_floor,
    get_apartment, get_all_apartments_for_building,
    get_price_change_text, get_construction_reports,
    toggle_favorite, get_user_favorites, is_favorite,
    get_all_faq, calc_installment, get_setting,
)
from app.keyboards import (
    main_menu_kb, buildings_kb, floors_kb, apartments_kb,
    apartment_detail_kb, shaxmatka_kb, shaxmatka_building_select_kb
)

router = Router()


async def safe_edit_text_or_send(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML"
):
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return
    except TelegramBadRequest as exc:
        if "there is no text in the message to edit" not in str(exc).lower():
            raise
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        await upsert_user(session, message.from_user.id,
                          message.from_user.full_name, message.from_user.username)
    await message.answer(
        "🏠 <b>Assalomu alaykum!</b>\n\n"
        "Ko'chmas mulk botimizga xush kelibsiz.\n"
        "Quyidagi menyudan foydalaning:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ==================== BINOLAR ====================

@router.message(F.text == "🏢 Binolar")
async def show_buildings(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        buildings = await get_all_buildings(session)
    if not buildings:
        await message.answer("🏗 Hozircha binolar qo'shilmagan.")
        return
    await message.answer(
        "🏢 <b>Binoni tanlang:</b>",
        reply_markup=buildings_kb(buildings),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_buildings")
async def back_to_buildings(callback: CallbackQuery):
    async with async_session() as session:
        buildings = await get_all_buildings(session)
    if not buildings:
        await safe_edit_text_or_send(callback, "🏗 Hozircha binolar qo'shilmagan.")
        await callback.answer()
        return
    await safe_edit_text_or_send(
        callback,
        "🏢 <b>Binoni tanlang:</b>",
        reply_markup=buildings_kb(buildings),
    )
    await callback.answer()


# ==================== BINO TANLASH -> QAVATLAR ====================

@router.callback_query(F.data.startswith("building:"))
async def select_building(callback: CallbackQuery):
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        building = await get_building(session, building_id)
    if not building:
        await callback.answer("Bino topilmadi", show_alert=True)
        return

    if building.facade_photo:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=building.facade_photo,
            caption=f"🏢 <b>{building.name}</b>\n📍 {building.address or ''}\n\n⬇️ Qavatni tanlang:",
            reply_markup=floors_kb(building.id, building.total_floors),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"🏢 <b>{building.name}</b>\n📍 {building.address or ''}\n\n⬇️ Qavatni tanlang:",
            reply_markup=floors_kb(building.id, building.total_floors),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_floors:"))
async def back_to_floors(callback: CallbackQuery):
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        building = await get_building(session, building_id)
    if not building:
        await callback.answer("Bino topilmadi", show_alert=True)
        return

    if building.facade_photo:
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=building.facade_photo,
                    caption=f"🏢 <b>{building.name}</b>\n📍 {building.address or ''}\n\n⬇️ Qavatni tanlang:",
                    parse_mode="HTML"
                ),
                reply_markup=floors_kb(building.id, building.total_floors)
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=building.facade_photo,
                caption=f"🏢 <b>{building.name}</b>\n📍 {building.address or ''}\n\n⬇️ Qavatni tanlang:",
                reply_markup=floors_kb(building.id, building.total_floors),
                parse_mode="HTML"
            )
    else:
        await callback.message.edit_text(
            f"🏢 <b>{building.name}</b>\n📍 {building.address or ''}\n\n⬇️ Qavatni tanlang:",
            reply_markup=floors_kb(building.id, building.total_floors),
            parse_mode="HTML"
        )
    await callback.answer()


# ==================== QAVAT TANLASH -> KVARTIRALAR ====================

@router.callback_query(F.data.startswith("floor:"))
async def select_floor(callback: CallbackQuery):
    parts = callback.data.split(":")
    building_id = int(parts[1])
    floor_number = int(parts[2])

    async with async_session() as session:
        floor = await get_floor_by_number(session, building_id, floor_number)
        if not floor:
            await callback.answer("Bu qavatda ma'lumot yo'q", show_alert=True)
            return
        apartments = await get_apartments_by_floor(session, floor.id)

    if not apartments:
        await callback.answer("Bu qavatda kvartiralar yo'q", show_alert=True)
        return

    if floor.plan_photo:
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=floor.plan_photo,
                    caption=f"📐 <b>{floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                    parse_mode="HTML"
                ),
                reply_markup=apartments_kb(apartments, floor.id, building_id)
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=floor.plan_photo,
                caption=f"📐 <b>{floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                reply_markup=apartments_kb(apartments, floor.id, building_id),
                parse_mode="HTML"
            )
    else:
        try:
            await callback.message.edit_text(
                f"📐 <b>{floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                reply_markup=apartments_kb(apartments, floor.id, building_id),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                f"📐 <b>{floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                reply_markup=apartments_kb(apartments, floor.id, building_id),
                parse_mode="HTML"
            )
    await callback.answer()


# ==================== KVARTIRA TANLASH -> TO'LIQ MA'LUMOT ====================

@router.callback_query(F.data.startswith("apt:"))
async def select_apartment(callback: CallbackQuery):
    apartment_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        apt = await get_apartment(session, apartment_id)
        if not apt:
            await callback.answer("Kvartira topilmadi", show_alert=True)
            return
        price_text = await get_price_change_text(session, apartment_id)
        is_fav = await is_favorite(session, callback.from_user.id, apartment_id)

    floor = apt.floor
    building = floor.building
    status = "🔴 Sotilgan" if apt.is_sold else "🟢 Sotuvda"

    info_text = (
        f"🏢 <b>{building.name}</b> | {floor.floor_number}-qavat\n"
        f"🏠 <b>{apt.apartment_number}-kvartira</b>\n\n"
        f"🛏 Xonalar: <b>{apt.rooms} xona</b>\n"
        f"📏 Maydoni: <b>{apt.area} m²</b>\n"
        f"💰 Narxi: <b>{apt.price:,.0f} so'm</b>\n"
        f"💵 1 m² narxi: <b>{apt.price_per_m2:,.0f} so'm</b>\n"
        f"📊 Status: {status}\n"
    )

    if apt.installment_available and not apt.is_sold:
        inst = calc_installment(apt.price, apt.initial_payment_percent, apt.installment_months)
        info_text += (
            f"\n💳 <b>Bo'lib to'lash mavjud!</b>\n"
            f"  Boshlang'ich: {inst['initial']:,.0f} so'm ({inst['initial_pct']}%)\n"
            f"  Oylik: {inst['monthly']:,.0f} so'm × {inst['months']} oy\n"
        )

    if apt.description:
        info_text += f"\n📝 {apt.description}\n"

    if price_text:
        info_text += f"\n{price_text}\n"

    kb = apartment_detail_kb(apt.id, building.id, apt.is_sold,
                             is_fav=is_fav, has_installment=apt.installment_available)

    # Send apartment photos as media group if available
    if apt.photos and len(apt.photos) > 0:
        from aiogram.types import InputMediaPhoto as IMP
        try:
            await callback.message.delete()
        except Exception:
            pass

        media_group = []
        for i, photo_id in enumerate(apt.photos):
            if i == 0:
                media_group.append(IMP(media=photo_id, caption=info_text, parse_mode="HTML"))
            else:
                media_group.append(IMP(media=photo_id))

        if len(media_group) > 1:
            await callback.message.answer_media_group(media=media_group)
            await callback.message.answer(
                "⬇️ Harakatni tanlang:",
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer_photo(
                photo=apt.photos[0],
                caption=info_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    else:
        try:
            await callback.message.edit_text(
                info_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                info_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_floor_apts:"))
async def back_to_floor_apts(callback: CallbackQuery):
    apartment_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        apt = await get_apartment(session, apartment_id)
        if not apt:
            await callback.answer("Topilmadi", show_alert=True)
            return
        floor = apt.floor
        building = floor.building
        apartments = await get_apartments_by_floor(session, floor.id)

    if floor.plan_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=floor.plan_photo,
            caption=f"📐 <b>{floor.floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
            reply_markup=apartments_kb(apartments, floor.id, building.id),
            parse_mode="HTML"
        )
    else:
        try:
            await callback.message.edit_text(
                f"📐 <b>{floor.floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                reply_markup=apartments_kb(apartments, floor.id, building.id),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                f"📐 <b>{floor.floor_number}-qavat plani</b>\n\n🏠 Kvartira tanlang:",
                reply_markup=apartments_kb(apartments, floor.id, building.id),
                parse_mode="HTML"
            )
    await callback.answer()


# ==================== SHAXMATKA ====================

@router.message(F.text == "🟢 Bo'sh uylar (Shaxmatka)")
async def show_shaxmatka_buildings(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        buildings = await get_all_buildings(session)
    if not buildings:
        await message.answer("🏗 Hozircha binolar qo'shilmagan.")
        return
    if len(buildings) == 1:
        building = buildings[0]
        async with async_session() as session:
            data = await get_all_apartments_for_building(session, building.id)
        if not data:
            await message.answer("Ma'lumot topilmadi.")
            return
        await message.answer(
            f"📊 <b>{building.name} — Shaxmatka</b>\n\n"
            f"🟢 - Sotuvda | 🔴 - Sotilgan\n"
            f"Kvartira tanlang:",
            reply_markup=shaxmatka_kb(data, building.id),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "📊 <b>Shaxmatka — Binoni tanlang:</b>",
            reply_markup=shaxmatka_building_select_kb(buildings),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("shaxmatka:"))
async def show_shaxmatka(callback: CallbackQuery):
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        building = await get_building(session, building_id)
        data = await get_all_apartments_for_building(session, building_id)
    if not data:
        await callback.answer("Ma'lumot topilmadi", show_alert=True)
        return
    await callback.message.edit_text(
        f"📊 <b>{building.name} — Shaxmatka</b>\n\n"
        f"🟢 - Sotuvda | 🔴 - Sotilgan\n"
        f"Kvartira tanlang:",
        reply_markup=shaxmatka_kb(data, building_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shax_label:"))
async def shax_label_noop(callback: CallbackQuery):
    await callback.answer()


# ==================== QURILISH JARAYONI ====================

@router.message(F.text == "🏗 Qurilish jarayoni")
async def show_construction(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        buildings = await get_all_buildings(session)

    if not buildings:
        await message.answer("🏗 Hozircha binolar qo'shilmagan.")
        return

    if len(buildings) == 1:
        async with async_session() as session:
            reports = await get_construction_reports(session, buildings[0].id)
        if not reports:
            await message.answer("📭 Hozircha qurilish hisobotlari yo'q.")
            return
        for report in reports[:10]:
            text = (
                f"🏗 <b>{report.title}</b>\n"
                f"📅 {report.created_at.strftime('%d.%m.%Y')}\n"
            )
            if report.description:
                text += f"\n{report.description}"
            if report.media_file_id:
                if report.media_type == "video":
                    await message.answer_video(video=report.media_file_id, caption=text, parse_mode="HTML")
                else:
                    await message.answer_photo(photo=report.media_file_id, caption=text, parse_mode="HTML")
            else:
                await message.answer(text, parse_mode="HTML")
    else:
        from app.keyboards import shaxmatka_building_select_kb
        buttons = []
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        for b in buildings:
            buttons.append([InlineKeyboardButton(text=f"🏢 {b.name}", callback_data=f"constr_b:{b.id}")])
        await message.answer(
            "🏗 <b>Qurilish jarayoni — Binoni tanlang:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("constr_b:"))
async def show_construction_building(callback: CallbackQuery):
    building_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        reports = await get_construction_reports(session, building_id)
    if not reports:
        await callback.answer("📭 Hozircha hisobotlar yo'q", show_alert=True)
        return
    await callback.message.delete()
    for report in reports[:10]:
        text = (
            f"🏗 <b>{report.title}</b>\n"
            f"📅 {report.created_at.strftime('%d.%m.%Y')}\n"
        )
        if report.description:
            text += f"\n{report.description}"
        if report.media_file_id:
            if report.media_type == "video":
                await callback.message.answer_video(video=report.media_file_id, caption=text, parse_mode="HTML")
            else:
                await callback.message.answer_photo(photo=report.media_file_id, caption=text, parse_mode="HTML")
        else:
            await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ==================== BOG'LANISH ====================

@router.message(F.text == "📞 Bog'lanish")
async def show_contact(message: Message, state: FSMContext):
    await state.clear()
    from app.config import OFFICE_ADDRESS, OFFICE_LATITUDE, OFFICE_LONGITUDE
    async with async_session() as session:
        saved_addr = await get_setting(session, "office_address")
        saved_lat = await get_setting(session, "office_lat")
        saved_lon = await get_setting(session, "office_lon")
    addr = saved_addr or OFFICE_ADDRESS
    lat = float(saved_lat) if saved_lat else OFFICE_LATITUDE
    lon = float(saved_lon) if saved_lon else OFFICE_LONGITUDE
    await message.answer(
        f"📍 <b>Bizning ofis:</b>\n{addr}\n\n"
        f"📞 Bog'lanish uchun «Ofisga yozilish» tugmasidan foydalaning.",
        parse_mode="HTML"
    )
    await message.answer_location(latitude=lat, longitude=lon)


# ==================== SEVIMLILAR ====================

@router.callback_query(F.data.startswith("fav:"))
async def toggle_fav(callback: CallbackQuery):
    apartment_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        added = await toggle_favorite(session, callback.from_user.id, apartment_id)
    if added:
        await callback.answer("⭐ Sevimlilarga qo'shildi!", show_alert=True)
    else:
        await callback.answer("💔 Sevimlilardan o'chirildi!", show_alert=True)


@router.message(F.text == "⭐ Sevimlilar")
async def show_favorites(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        favorites = await get_user_favorites(session, message.from_user.id)
    if not favorites:
        await message.answer("📭 Sevimlilar ro'yxati bo'sh.\n\nKvartira ma'lumotlarida ⭐ tugmasini bosing.")
        return

    text = "⭐ <b>Sevimli kvartiralar:</b>\n\n"
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    for apt in favorites:
        floor = apt.floor
        building = floor.building
        status = "🔴" if apt.is_sold else "🟢"
        text += (
            f"{status} {building.name} | {floor.floor_number}-qavat | "
            f"{apt.apartment_number}-kvartira | {apt.rooms}x | "
            f"{apt.price:,.0f} so'm\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"{status} {building.name} {floor.floor_number}-qavat {apt.apartment_number}-kv",
            callback_data=f"apt:{apt.id}"
        )])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ==================== INSTALLMENT DETAIL ====================

@router.callback_query(F.data.startswith("installment:"))
async def show_installment(callback: CallbackQuery):
    apartment_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        apt = await get_apartment(session, apartment_id)
    if not apt or not apt.installment_available:
        await callback.answer("Bu kvartira uchun bo'lib to'lash mavjud emas", show_alert=True)
        return

    inst = calc_installment(apt.price, apt.initial_payment_percent, apt.installment_months)
    floor = apt.floor
    building = floor.building

    text = (
        f"💳 <b>BO'LIB TO'LASH REJASI</b>\n\n"
        f"🏢 {building.name} | {floor.floor_number}-qavat | {apt.apartment_number}-kv\n\n"
        f"💰 Umumiy narx: <b>{apt.price:,.0f} so'm</b>\n\n"
        f"1️⃣ Boshlang'ich to'lov ({inst['initial_pct']}%):\n"
        f"   <b>{inst['initial']:,.0f} so'm</b>\n\n"
        f"2️⃣ Qoldiq summa:\n"
        f"   <b>{inst['remaining']:,.0f} so'm</b>\n\n"
        f"3️⃣ Oylik to'lov ({inst['months']} oy):\n"
        f"   <b>{inst['monthly']:,.0f} so'm/oy</b>\n\n"
        f"📅 Ofisga yoziling — batafsil ma'lumot oling!"
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ofisga yozilish", callback_data=f"book:{apartment_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"apt:{apartment_id}")],
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==================== FAQ ====================

@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        faqs = await get_all_faq(session)
    faqs = [f for f in faqs if not f.question.startswith("__setting__")]
    if not faqs:
        await message.answer("📭 Hozircha ko'p so'raladigan savollar yo'q.")
        return
    text = "❓ <b>Ko'p so'raladigan savollar:</b>\n\n"
    for i, faq in enumerate(faqs, 1):
        text += f"<b>{i}. {faq.question}</b>\n{faq.answer}\n\n"
    await message.answer(text, parse_mode="HTML")


# ==================== IPOTEKA KALKULYATOR ====================

class CalcStates(StatesGroup):
    price = State()
    initial_pct = State()
    months = State()


@router.message(F.text == "🧮 Kalkulyator")
async def calc_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🧮 <b>Ipoteka / Bo'lib to'lash kalkulyatori</b>\n\n"
        "Kvartira narxini kiriting so'mda (masalan: 500000000):",
        parse_mode="HTML"
    )
    await state.set_state(CalcStates.price)


@router.message(CalcStates.price)
async def calc_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 500000000):")
        return
    await state.update_data(calc_price=price)
    await message.answer("💵 Boshlang'ich to'lov foizi? (masalan: 30):")
    await state.set_state(CalcStates.initial_pct)


@router.message(CalcStates.initial_pct)
async def calc_initial(message: Message, state: FSMContext):
    try:
        pct = float(message.text.replace(",", ".").replace("%", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 30):")
        return
    await state.update_data(calc_pct=pct)
    await message.answer("📅 Necha oyga? (masalan: 12, 18, 24):")
    await state.set_state(CalcStates.months)


@router.message(CalcStates.months)
async def calc_months(message: Message, state: FSMContext):
    try:
        months = int(message.text)
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 12):")
        return
    data = await state.get_data()
    price = data["calc_price"]
    pct = data["calc_pct"]
    inst = calc_installment(price, pct, months)

    text = (
        f"🧮 <b>HISOB NATIJASI</b>\n\n"
        f"💰 Umumiy narx: <b>{price:,.0f} so'm</b>\n\n"
        f"1️⃣ Boshlang'ich to'lov ({pct}%):\n"
        f"   <b>{inst['initial']:,.0f} so'm</b>\n\n"
        f"2️⃣ Qoldiq summa:\n"
        f"   <b>{inst['remaining']:,.0f} so'm</b>\n\n"
        f"3️⃣ Oylik to'lov ({months} oy):\n"
        f"   <b>{inst['monthly']:,.0f} so'm/oy</b>\n\n"
        f"📞 Batafsil ma'lumot uchun ofisga murojaat qiling!"
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await state.clear()
