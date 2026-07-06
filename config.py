import os
from dotenv import load_dotenv

load_dotenv()

Token=os.getenv("BOT_TOKEN", "").strip()
AI_TOKEN = os.getenv("AI_TOKEN", "").strip()