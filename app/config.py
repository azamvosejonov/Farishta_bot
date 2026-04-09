import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "/admin_8899")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://botuser:botpass@db:5432/realestate")
OFFICE_ADDRESS = os.getenv("OFFICE_ADDRESS", "Toshkent sh., Chilonzor tumani, 7-kvartal, 15-uy")
OFFICE_LATITUDE = float(os.getenv("OFFICE_LATITUDE", "41.2995"))
OFFICE_LONGITUDE = float(os.getenv("OFFICE_LONGITUDE", "69.2401"))
MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")
