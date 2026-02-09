import os
from dotenv import load_dotenv

load_dotenv()  # loads .env into environment variables

class Settings:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    TENANT_ID = os.getenv("TENANT_ID")
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    SITE_ID = os.getenv("SITE_ID")
    DRIVE_ID = os.getenv("DRIVE_ID")

settings = Settings()
