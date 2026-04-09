from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from typing import List
from datetime import date, time

from app.database.crud import DAYS_UZ


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏢 Binolar"), KeyboardButton(text="🟢 Bo'sh uylar (Shaxmatka)")],
            [KeyboardButton(text="⭐ Sevimlilar"), KeyboardButton(text="🧮 Kalkulyator")],
            [KeyboardButton(text="🏗 Qurilish jarayoni"), KeyboardButton(text="❓ FAQ")],
            [KeyboardButton(text="📞 Bog'lanish")],
        ],
        resize_keyboard=True
    )


def buildings_kb(buildings) -> InlineKeyboardMarkup:
    buttons = []
    for b in buildings:
        buttons.append([InlineKeyboardButton(text=f"🏢 {b.name}", callback_data=f"building:{b.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def floors_kb(building_id: int, total_floors: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i in range(total_floors, 0, -1):
        row.append(InlineKeyboardButton(text=f"{i}-qavat", callback_data=f"floor:{building_id}:{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_buildings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def apartments_kb(apartments, floor_id: int, building_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for apt in apartments:
        status = "🔴" if apt.is_sold else "🟢"
        text = f"{status} {apt.apartment_number}-kvartira ({apt.rooms} xona)"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"apt:{apt.id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_to_floors:{building_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def apartment_detail_kb(apartment_id: int, building_id: int, is_sold: bool,
                        is_fav: bool = False, has_installment: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if not is_sold:
        buttons.append([InlineKeyboardButton(text="📅 Ofisga yozilish", callback_data=f"book:{apartment_id}")])
    if has_installment and not is_sold:
        buttons.append([InlineKeyboardButton(text="💳 Bo'lib to'lash", callback_data=f"installment:{apartment_id}")])
    fav_text = "💔 Sevimlilardan o'chirish" if is_fav else "⭐ Sevimlilarga qo'shish"
    buttons.append([InlineKeyboardButton(text=fav_text, callback_data=f"fav:{apartment_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_to_floor_apts:{apartment_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ==================== SHAXMATKA ====================

def shaxmatka_kb(apartments_data: List[dict], building_id: int) -> InlineKeyboardMarkup:
    floors_map = {}
    for item in apartments_data:
        fn = item["floor_number"]
        apt = item["apartment"]
        if fn not in floors_map:
            floors_map[fn] = []
        floors_map[fn].append(apt)

    buttons = []
    for fn in sorted(floors_map.keys(), reverse=True):
        apts = sorted(floors_map[fn], key=lambda a: a.apartment_number)
        row = [InlineKeyboardButton(text=f"{fn}⬆️", callback_data=f"shax_label:{fn}")]
        for apt in apts:
            emoji = "🔴" if apt.is_sold else "🟢"
            row.append(InlineKeyboardButton(text=emoji, callback_data=f"apt:{apt.id}"))
        buttons.append(row)

    header = [InlineKeyboardButton(text="Qavat", callback_data="shax_label:h")]
    max_apts = max((len(floors_map[fn]) for fn in floors_map), default=4)
    for i in range(1, max_apts + 1):
        header.append(InlineKeyboardButton(text=f"X{i}", callback_data=f"shax_label:{i}"))
    buttons.insert(0, header)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shaxmatka_building_select_kb(buildings) -> InlineKeyboardMarkup:
    buttons = []
    for b in buildings:
        buttons.append([InlineKeyboardButton(text=f"🏢 {b.name}", callback_data=f"shaxmatka:{b.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== BOOKING ====================

def booking_dates_kb(dates: List[date], apartment_id: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for d in dates:
        day_name = DAYS_UZ.get(d.weekday(), "")
        text = f"{d.strftime('%d.%m')} {day_name}"
        row.append(InlineKeyboardButton(text=text, callback_data=f"bdate:{apartment_id}:{d.isoformat()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booking_times_kb(times: List[time], apartment_id: int, date_str: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for t in times:
        text = t.strftime("%H:%M")
        row.append(InlineKeyboardButton(
            text=text, callback_data=f"btime:{apartment_id}:{date_str}:{text}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"book:{apartment_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ADMIN ====================

def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Binolarni boshqarish", callback_data="adm:buildings")],
        [InlineKeyboardButton(text="📅 Ish jadvalini sozlash", callback_data="adm:schedule")],
        [InlineKeyboardButton(text="📋 Uchrashuvlar ro'yxati", callback_data="adm:bookings")],
        [InlineKeyboardButton(text="🏗 Qurilish hisoboti qo'shish", callback_data="adm:construction")],
        [InlineKeyboardButton(text="📊 To'liq statistika", callback_data="adm:stats")],
        [InlineKeyboardButton(text="👥 Adminlar boshqarish", callback_data="adm:admins")],
        [InlineKeyboardButton(text="❓ FAQ boshqarish", callback_data="adm:faq")],
        [InlineKeyboardButton(text="📍 Manzil sozlash", callback_data="adm:address")],
        [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast")],
    ])


def admin_buildings_kb(buildings) -> InlineKeyboardMarkup:
    buttons = []
    for b in buildings:
        buttons.append([InlineKeyboardButton(text=f"🏢 {b.name}", callback_data=f"adm_b:{b.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Yangi bino qo'shish", callback_data="adm:add_building")])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_building_detail_kb(building_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Fasad rasmi o'zgartirish", callback_data=f"adm_bphoto:{building_id}")],
        [InlineKeyboardButton(text="📐 Qavatlarni boshqarish", callback_data=f"adm_floors:{building_id}")],
        [InlineKeyboardButton(text="🏠 Kvartiralar (Shablon)", callback_data=f"adm_bulk:{building_id}")],
        [InlineKeyboardButton(text="🗑 Binoni o'chirish", callback_data=f"adm_bdel:{building_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:buildings")],
    ])


def admin_floors_kb(floors, building_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for f in floors:
        buttons.append([InlineKeyboardButton(
            text=f"{f.floor_number}-qavat", callback_data=f"adm_fl:{f.id}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Qavat qo'shish", callback_data=f"adm_addfl:{building_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_b:{building_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_floor_detail_kb(floor_id: int, building_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Qavat plani rasmi", callback_data=f"adm_flphoto:{floor_id}")],
        [InlineKeyboardButton(text="🏠 Kvartiralar", callback_data=f"adm_flapts:{floor_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_floors:{building_id}")],
    ])


def admin_apt_list_kb(apartments, floor_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for apt in apartments:
        status = "🔴" if apt.is_sold else "🟢"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {apt.apartment_number}-kvartira ({apt.rooms}x, {apt.area}m²)",
            callback_data=f"adm_apt:{apt.id}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Kvartira qo'shish", callback_data=f"adm_addapt:{floor_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_fl:{floor_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_apt_detail_kb(apt) -> InlineKeyboardMarkup:
    status_text = "🟢 Sotuvga qo'yish" if apt.is_sold else "🔴 Sotildi deb belgilash"
    status_cb = f"adm_apt_unsell:{apt.id}" if apt.is_sold else f"adm_apt_sell:{apt.id}"
    inst_text = "💳 Bo'lib to'lash ❌ O'chirish" if apt.installment_available else "💳 Bo'lib to'lash ✅ Yoqish"
    inst_cb = f"adm_inst_off:{apt.id}" if apt.installment_available else f"adm_inst_on:{apt.id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_text, callback_data=status_cb)],
        [InlineKeyboardButton(text="💰 Narx o'zgartirish", callback_data=f"adm_apt_price:{apt.id}")],
        [InlineKeyboardButton(text=inst_text, callback_data=inst_cb)],
        [InlineKeyboardButton(text="🖼 Rasmlar o'zgartirish", callback_data=f"adm_apt_photos:{apt.id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_flapts:{apt.floor_id}")],
    ])


def admin_schedule_kb(schedules) -> InlineKeyboardMarkup:
    buttons = []
    active_days = {s.day_of_week for s in schedules}
    for day_num, day_name in DAYS_UZ.items():
        if day_num in active_days:
            s = next(sc for sc in schedules if sc.day_of_week == day_num)
            text = f"✅ {day_name}: {s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}"
        else:
            text = f"⬜ {day_name}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"adm_sched:{day_num}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_schedule_day_kb(day_num: int, is_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_active:
        buttons.append([InlineKeyboardButton(text="🔄 Vaqtni o'zgartirish", callback_data=f"adm_sched_set:{day_num}")])
        buttons.append([InlineKeyboardButton(text="❌ O'chirish", callback_data=f"adm_sched_del:{day_num}")])
    else:
        buttons.append([InlineKeyboardButton(text="➕ Vaqt belgilash", callback_data=f"adm_sched_set:{day_num}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:schedule")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_construction_building_kb(buildings) -> InlineKeyboardMarkup:
    buttons = []
    for b in buildings:
        buttons.append([InlineKeyboardButton(text=f"🏢 {b.name}", callback_data=f"adm_constr:{b.id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_broadcast_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, yuborish", callback_data="adm_broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:main")],
    ])
