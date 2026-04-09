from datetime import date, time, datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Building, Floor, Apartment, PriceHistory,
    AdminSchedule, Booking, ConstructionReport, BotUser,
    AdminUser, Favorite, FAQ
)


# ==================== BOT USER ====================

async def upsert_user(session: AsyncSession, user_id: int, fullname: str, username: str = None):
    user = await session.get(BotUser, user_id)
    if user:
        user.fullname = fullname
        user.username = username
    else:
        user = BotUser(id=user_id, fullname=fullname, username=username)
        session.add(user)
    await session.commit()
    return user


async def update_user_phone(session: AsyncSession, user_id: int, phone: str):
    stmt = update(BotUser).where(BotUser.id == user_id).values(phone=phone)
    await session.execute(stmt)
    await session.commit()


async def get_all_users(session: AsyncSession) -> List[BotUser]:
    result = await session.execute(select(BotUser))
    return result.scalars().all()


# ==================== BUILDING ====================

async def create_building(session: AsyncSession, name: str, address: str = None,
                          total_floors: int = 12, apartments_per_floor: int = 4,
                          facade_photo: str = None) -> Building:
    building = Building(
        name=name, address=address, total_floors=total_floors,
        apartments_per_floor=apartments_per_floor, facade_photo=facade_photo
    )
    session.add(building)
    await session.commit()
    await session.refresh(building)
    return building


async def get_all_buildings(session: AsyncSession) -> List[Building]:
    result = await session.execute(select(Building).order_by(Building.id))
    return result.scalars().all()


async def get_building(session: AsyncSession, building_id: int) -> Optional[Building]:
    return await session.get(Building, building_id)


async def update_building_photo(session: AsyncSession, building_id: int, photo: str):
    stmt = update(Building).where(Building.id == building_id).values(facade_photo=photo)
    await session.execute(stmt)
    await session.commit()


async def delete_building(session: AsyncSession, building_id: int):
    building = await session.get(Building, building_id)
    if building:
        await session.delete(building)
        await session.commit()


# ==================== FLOOR ====================

async def create_floor(session: AsyncSession, building_id: int, floor_number: int,
                       plan_photo: str = None) -> Floor:
    floor = Floor(building_id=building_id, floor_number=floor_number, plan_photo=plan_photo)
    session.add(floor)
    await session.commit()
    await session.refresh(floor)
    return floor


async def get_floors_by_building(session: AsyncSession, building_id: int) -> List[Floor]:
    result = await session.execute(
        select(Floor).where(Floor.building_id == building_id).order_by(Floor.floor_number)
    )
    return result.scalars().all()


async def get_floor(session: AsyncSession, floor_id: int) -> Optional[Floor]:
    return await session.get(Floor, floor_id)


async def get_floor_by_number(session: AsyncSession, building_id: int, floor_number: int) -> Optional[Floor]:
    result = await session.execute(
        select(Floor).where(
            and_(Floor.building_id == building_id, Floor.floor_number == floor_number)
        )
    )
    return result.scalar_one_or_none()


async def update_floor_photo(session: AsyncSession, floor_id: int, photo: str):
    stmt = update(Floor).where(Floor.id == floor_id).values(plan_photo=photo)
    await session.execute(stmt)
    await session.commit()


# ==================== APARTMENT ====================

async def create_apartment(session: AsyncSession, floor_id: int, apartment_number: int,
                           rooms: int, area: float, price: float,
                           description: str = None, photos: list = None) -> Apartment:
    price_per_m2 = round(price / area, 2) if area > 0 else 0
    apt = Apartment(
        floor_id=floor_id, apartment_number=apartment_number, rooms=rooms,
        area=area, price=price, price_per_m2=price_per_m2,
        description=description, photos=photos or []
    )
    session.add(apt)
    await session.commit()
    await session.refresh(apt)
    return apt


async def get_apartments_by_floor(session: AsyncSession, floor_id: int) -> List[Apartment]:
    result = await session.execute(
        select(Apartment).where(Apartment.floor_id == floor_id).order_by(Apartment.apartment_number)
    )
    return result.scalars().all()


async def get_apartment(session: AsyncSession, apartment_id: int) -> Optional[Apartment]:
    result = await session.execute(
        select(Apartment)
        .options(selectinload(Apartment.floor).selectinload(Floor.building))
        .options(selectinload(Apartment.price_history))
        .where(Apartment.id == apartment_id)
    )
    return result.scalar_one_or_none()


async def update_apartment_status(session: AsyncSession, apartment_id: int, is_sold: bool):
    stmt = update(Apartment).where(Apartment.id == apartment_id).values(is_sold=is_sold)
    await session.execute(stmt)
    await session.commit()


async def update_apartment_price(session: AsyncSession, apartment_id: int, new_price: float):
    apt = await session.get(Apartment, apartment_id)
    if apt:
        old_price = apt.price
        apt.price = new_price
        apt.price_per_m2 = round(new_price / apt.area, 2) if apt.area > 0 else 0
        history = PriceHistory(apartment_id=apartment_id, old_price=old_price, new_price=new_price)
        session.add(history)
        await session.commit()


async def update_apartment_photos(session: AsyncSession, apartment_id: int, photos: list):
    stmt = update(Apartment).where(Apartment.id == apartment_id).values(photos=photos)
    await session.execute(stmt)
    await session.commit()


async def get_all_apartments_for_building(session: AsyncSession, building_id: int) -> List[dict]:
    result = await session.execute(
        select(Apartment, Floor.floor_number)
        .join(Floor, Apartment.floor_id == Floor.id)
        .where(Floor.building_id == building_id)
        .order_by(Floor.floor_number.desc(), Apartment.apartment_number)
    )
    rows = result.all()
    return [{"apartment": row[0], "floor_number": row[1]} for row in rows]


# ==================== BULK CREATE ====================

async def bulk_create_apartments(session: AsyncSession, building_id: int,
                                 template_apt_number: int, rooms: int, area: float,
                                 price: float, description: str, photos: list,
                                 from_floor: int, to_floor: int):
    """Create same apartment type across multiple floors."""
    created = []
    for floor_num in range(from_floor, to_floor + 1):
        floor = await get_floor_by_number(session, building_id, floor_num)
        if not floor:
            floor = await create_floor(session, building_id, floor_num)

        existing = await session.execute(
            select(Apartment).where(
                and_(Apartment.floor_id == floor.id,
                     Apartment.apartment_number == template_apt_number)
            )
        )
        if existing.scalar_one_or_none():
            continue

        apt = await create_apartment(
            session, floor.id, template_apt_number, rooms, area, price, description, photos
        )
        created.append(apt)
    return created


# ==================== ADMIN SCHEDULE ====================

DAYS_UZ = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba",
            4: "Juma", 5: "Shanba", 6: "Yakshanba"}


async def set_schedule(session: AsyncSession, day_of_week: int,
                       start_time: time, end_time: time, slot_duration: int = 60):
    result = await session.execute(
        select(AdminSchedule).where(AdminSchedule.day_of_week == day_of_week)
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        schedule.start_time = start_time
        schedule.end_time = end_time
        schedule.slot_duration_minutes = slot_duration
        schedule.is_active = True
    else:
        schedule = AdminSchedule(
            day_of_week=day_of_week, start_time=start_time,
            end_time=end_time, slot_duration_minutes=slot_duration
        )
        session.add(schedule)
    await session.commit()


async def remove_schedule(session: AsyncSession, day_of_week: int):
    stmt = delete(AdminSchedule).where(AdminSchedule.day_of_week == day_of_week)
    await session.execute(stmt)
    await session.commit()


async def get_all_schedules(session: AsyncSession) -> List[AdminSchedule]:
    result = await session.execute(
        select(AdminSchedule).where(AdminSchedule.is_active == True).order_by(AdminSchedule.day_of_week)
    )
    return result.scalars().all()


async def get_available_dates(session: AsyncSession, days_ahead: int = 14) -> List[date]:
    schedules = await get_all_schedules(session)
    if not schedules:
        return []
    active_days = {s.day_of_week for s in schedules}
    today = date.today()
    available = []
    for i in range(1, days_ahead + 1):
        d = today + timedelta(days=i)
        if d.weekday() in active_days:
            available.append(d)
    return available


async def get_available_slots(session: AsyncSession, target_date: date) -> List[time]:
    day_of_week = target_date.weekday()
    result = await session.execute(
        select(AdminSchedule).where(
            and_(AdminSchedule.day_of_week == day_of_week, AdminSchedule.is_active == True)
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        return []

    booked_result = await session.execute(
        select(Booking.booking_time).where(
            and_(Booking.booking_date == target_date,
                 Booking.status.in_(["pending", "confirmed"]))
        )
    )
    booked_times = {row[0] for row in booked_result.all()}

    slots = []
    current = datetime.combine(target_date, schedule.start_time)
    end = datetime.combine(target_date, schedule.end_time)
    delta = timedelta(minutes=schedule.slot_duration_minutes)

    while current + delta <= end:
        t = current.time()
        if t not in booked_times:
            slots.append(t)
        current += delta
    return slots


# ==================== BOOKING ====================

async def create_booking(session: AsyncSession, user_id: int, user_fullname: str,
                         user_phone: str, apartment_id: int,
                         booking_date: date, booking_time: time) -> Optional[Booking]:
    existing = await session.execute(
        select(Booking).where(
            and_(Booking.booking_date == booking_date,
                 Booking.booking_time == booking_time,
                 Booking.status.in_(["pending", "confirmed"]))
        )
    )
    if existing.scalar_one_or_none():
        return None

    booking = Booking(
        user_id=user_id, user_fullname=user_fullname, user_phone=user_phone,
        apartment_id=apartment_id, booking_date=booking_date, booking_time=booking_time,
        status="confirmed"
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


async def get_bookings_for_date(session: AsyncSession, target_date: date) -> List[Booking]:
    result = await session.execute(
        select(Booking).where(Booking.booking_date == target_date).order_by(Booking.booking_time)
    )
    return result.scalars().all()


async def get_upcoming_bookings(session: AsyncSession) -> List[Booking]:
    today = date.today()
    result = await session.execute(
        select(Booking).where(
            and_(Booking.booking_date >= today, Booking.status == "confirmed")
        ).order_by(Booking.booking_date, Booking.booking_time)
    )
    return result.scalars().all()


async def cancel_booking(session: AsyncSession, booking_id: int):
    stmt = update(Booking).where(Booking.id == booking_id).values(status="cancelled")
    await session.execute(stmt)
    await session.commit()


# ==================== CONSTRUCTION REPORTS ====================

async def add_construction_report(session: AsyncSession, building_id: int, title: str,
                                  description: str = None, media_file_id: str = None,
                                  media_type: str = "photo") -> ConstructionReport:
    report = ConstructionReport(
        building_id=building_id, title=title, description=description,
        media_file_id=media_file_id, media_type=media_type
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_construction_reports(session: AsyncSession, building_id: int) -> List[ConstructionReport]:
    result = await session.execute(
        select(ConstructionReport)
        .where(ConstructionReport.building_id == building_id)
        .order_by(ConstructionReport.created_at.desc())
    )
    return result.scalars().all()


# ==================== PRICE HISTORY ====================

async def get_price_change_text(session: AsyncSession, apartment_id: int) -> Optional[str]:
    result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.apartment_id == apartment_id)
        .order_by(PriceHistory.changed_at.desc())
        .limit(1)
    )
    history = result.scalar_one_or_none()
    if not history:
        return None
    if history.new_price > history.old_price:
        pct = round((history.new_price - history.old_price) / history.old_price * 100, 1)
        return f"📈 O'tgan safar bu kvartira {pct}% arzonroq edi!"
    elif history.new_price < history.old_price:
        pct = round((history.old_price - history.new_price) / history.old_price * 100, 1)
        return f"📉 Narx {pct}% ga tushdi — imkoniyatni boy bermang!"
    return None


# ==================== STATS ====================

async def get_stats(session: AsyncSession, building_id: int) -> dict:
    total = await session.execute(
        select(func.count(Apartment.id))
        .join(Floor).where(Floor.building_id == building_id)
    )
    sold = await session.execute(
        select(func.count(Apartment.id))
        .join(Floor).where(and_(Floor.building_id == building_id, Apartment.is_sold == True))
    )
    total_price = await session.execute(
        select(func.sum(Apartment.price))
        .join(Floor).where(and_(Floor.building_id == building_id, Apartment.is_sold == True))
    )
    installment_count = await session.execute(
        select(func.count(Apartment.id))
        .join(Floor).where(and_(Floor.building_id == building_id, Apartment.installment_available == True))
    )
    total_count = total.scalar() or 0
    sold_count = sold.scalar() or 0
    revenue = total_price.scalar() or 0
    inst_count = installment_count.scalar() or 0
    return {
        "total": total_count,
        "sold": sold_count,
        "available": total_count - sold_count,
        "revenue": revenue,
        "installment": inst_count,
    }


async def get_full_stats(session: AsyncSession) -> dict:
    users_count = await session.execute(select(func.count(BotUser.id)))
    today = date.today()
    bookings_total = await session.execute(select(func.count(Booking.id)))
    bookings_upcoming = await session.execute(
        select(func.count(Booking.id)).where(
            and_(Booking.booking_date >= today, Booking.status == "confirmed")
        )
    )
    bookings_past = await session.execute(
        select(func.count(Booking.id)).where(Booking.booking_date < today)
    )
    all_apts = await session.execute(select(func.count(Apartment.id)))
    sold_apts = await session.execute(
        select(func.count(Apartment.id)).where(Apartment.is_sold == True)
    )
    total_revenue = await session.execute(
        select(func.sum(Apartment.price)).where(Apartment.is_sold == True)
    )
    apartments_total = all_apts.scalar() or 0
    apartments_sold = sold_apts.scalar() or 0
    return {
        "users": users_count.scalar() or 0,
        "bookings_total": bookings_total.scalar() or 0,
        "bookings_upcoming": bookings_upcoming.scalar() or 0,
        "bookings_past": bookings_past.scalar() or 0,
        "apartments_total": apartments_total,
        "apartments_sold": apartments_sold,
        "apartments_available": apartments_total - apartments_sold,
        "total_revenue": total_revenue.scalar() or 0,
    }


# ==================== MULTI ADMIN ====================

async def is_admin_user(session: AsyncSession, user_id: int) -> bool:
    from app.config import ADMIN_ID
    if user_id == ADMIN_ID:
        return True
    result = await session.execute(
        select(AdminUser).where(AdminUser.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


async def is_superadmin(session: AsyncSession, user_id: int) -> bool:
    from app.config import ADMIN_ID
    if user_id == ADMIN_ID:
        return True
    result = await session.execute(
        select(AdminUser).where(
            and_(AdminUser.user_id == user_id, AdminUser.role == "superadmin")
        )
    )
    return result.scalar_one_or_none() is not None


async def add_admin(session: AsyncSession, user_id: int, name: str, role: str = "admin") -> AdminUser:
    existing = await session.execute(
        select(AdminUser).where(AdminUser.user_id == user_id)
    )
    admin = existing.scalar_one_or_none()
    if admin:
        admin.name = name
        admin.role = role
    else:
        admin = AdminUser(user_id=user_id, name=name, role=role)
        session.add(admin)
    await session.commit()
    return admin


async def remove_admin(session: AsyncSession, user_id: int):
    stmt = delete(AdminUser).where(AdminUser.user_id == user_id)
    await session.execute(stmt)
    await session.commit()


async def get_all_admins(session: AsyncSession) -> List[AdminUser]:
    result = await session.execute(select(AdminUser).order_by(AdminUser.id))
    return result.scalars().all()


# ==================== FAVORITES ====================

async def toggle_favorite(session: AsyncSession, user_id: int, apartment_id: int) -> bool:
    result = await session.execute(
        select(Favorite).where(
            and_(Favorite.user_id == user_id, Favorite.apartment_id == apartment_id)
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await session.delete(fav)
        await session.commit()
        return False
    else:
        fav = Favorite(user_id=user_id, apartment_id=apartment_id)
        session.add(fav)
        await session.commit()
        return True


async def get_user_favorites(session: AsyncSession, user_id: int) -> List[Apartment]:
    result = await session.execute(
        select(Apartment)
        .join(Favorite, Favorite.apartment_id == Apartment.id)
        .options(selectinload(Apartment.floor).selectinload(Floor.building))
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.added_at.desc())
    )
    return result.scalars().all()


async def is_favorite(session: AsyncSession, user_id: int, apartment_id: int) -> bool:
    result = await session.execute(
        select(Favorite).where(
            and_(Favorite.user_id == user_id, Favorite.apartment_id == apartment_id)
        )
    )
    return result.scalar_one_or_none() is not None


# ==================== FAQ ====================

async def create_faq(session: AsyncSession, question: str, answer: str, sort_order: int = 0) -> FAQ:
    faq = FAQ(question=question, answer=answer, sort_order=sort_order)
    session.add(faq)
    await session.commit()
    await session.refresh(faq)
    return faq


async def get_all_faq(session: AsyncSession) -> List[FAQ]:
    result = await session.execute(select(FAQ).order_by(FAQ.sort_order, FAQ.id))
    return result.scalars().all()


async def delete_faq(session: AsyncSession, faq_id: int):
    faq = await session.get(FAQ, faq_id)
    if faq:
        await session.delete(faq)
        await session.commit()


# ==================== INSTALLMENT ====================

async def set_installment(session: AsyncSession, apartment_id: int,
                          available: bool, initial_pct: float = 30.0, months: int = 12):
    stmt = update(Apartment).where(Apartment.id == apartment_id).values(
        installment_available=available,
        initial_payment_percent=initial_pct,
        installment_months=months
    )
    await session.execute(stmt)
    await session.commit()


def calc_installment(price: float, initial_pct: float, months: int) -> dict:
    initial = price * initial_pct / 100
    remaining = price - initial
    monthly = remaining / months if months > 0 else 0
    return {
        "initial": initial,
        "monthly": monthly,
        "remaining": remaining,
        "months": months,
        "initial_pct": initial_pct,
    }


# ==================== SETTINGS (MANZIL) ====================

async def get_setting(session: AsyncSession, key: str) -> Optional[str]:
    from app.database.models import Base
    # Settings stored as FAQ with special prefix
    result = await session.execute(
        select(FAQ).where(FAQ.question == f"__setting__{key}")
    )
    row = result.scalar_one_or_none()
    return row.answer if row else None


async def set_setting(session: AsyncSession, key: str, value: str):
    result = await session.execute(
        select(FAQ).where(FAQ.question == f"__setting__{key}")
    )
    row = result.scalar_one_or_none()
    if row:
        row.answer = value
    else:
        row = FAQ(question=f"__setting__{key}", answer=value, sort_order=-1)
        session.add(row)
    await session.commit()
