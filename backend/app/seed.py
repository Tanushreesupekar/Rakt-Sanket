from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Donor, Inventory


DISTRICTS = ("Amravati", "Akola", "Wardha", "Yavatmal")
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def seed_demo_data(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Donor)):
        return

    stock_levels = (46, 18, 32, 11, 22, 8, 57, 6)
    safety_levels = (38, 18, 32, 15, 22, 12, 48, 12)
    demand_levels = (4.2, 1.2, 3.8, 1.0, 1.5, 0.7, 5.4, 0.8)
    for district_index, district in enumerate(DISTRICTS):
        for group_index, blood_group in enumerate(BLOOD_GROUPS):
            adjustment = district_index * 5
            units = max(2, stock_levels[group_index] + adjustment - (8 if district_index == 1 and group_index in (1, 7) else 0))
            session.add(Inventory(
                district=district,
                blood_group=blood_group,
                units_available=units,
                avg_daily_demand=round(demand_levels[group_index] * (1 + district_index * 0.08), 2),
                safety_stock_units=safety_levels[group_index] + district_index * 2,
            ))

    names = (
        "Aarav Deshmukh", "Aditi Patil", "Ishaan Kulkarni", "Anaya Joshi", "Vivaan Shinde",
        "Saanvi Pawar", "Arjun More", "Ira Jadhav", "Reyansh Kale", "Meera Desai",
        "Kabir Chavan", "Avni Gawande", "Advait Bhosale", "Myra Mahajan", "Rohan Thakur",
        "Kiara Ingle", "Atharv Raut", "Sara Khan", "Vedant Pote", "Anvi Wankhede",
        "Samar Naik", "Tara Nair", "Omkar Patil", "Diya Rane", "Neil Kapse",
        "Nisha Kadu", "Yash Rathod", "Aarya Sable", "Dev Joshi", "Riya Kale",
        "Manav Bhoyar", "Aisha Sheikh", "Siddhant Gite", "Ishita Mankar", "Pranav Wagh",
        "Kavya Pande", "Hriday Pawar", "Tanvi Jagtap", "Aditya Borkar", "Mira Khot",
    )
    for index, name in enumerate(names):
        last_contact = datetime.now(timezone.utc) - timedelta(days=(index * 7) % 43) if index % 3 != 0 else None
        session.add(Donor(
            name=f"{name} (demo)",
            district=DISTRICTS[index % len(DISTRICTS)],
            blood_group=BLOOD_GROUPS[(index // len(DISTRICTS)) % len(BLOOD_GROUPS)],
            age=20 + index % 36,
            last_donation_date=date.today() - timedelta(days=96 + (index * 19) % 330),
            donations_count=1 + index % 12,
            response_rate=round(0.32 + (index % 7) * 0.09, 2),
            notifications_30d=index % 5,
            last_contact_at=last_contact,
        ))
    session.commit()
