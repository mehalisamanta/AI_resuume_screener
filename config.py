import os
from dotenv import load_dotenv

# load_dotenv is for local fallback only
load_dotenv()

class Settings:
    """
    Reads from OS environment (GitHub Actions or Streamlit Secrets).
    """
    # No default strings like "your-tenant-id" here!
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TENANT_ID = os.getenv("AZURE_TENANT_ID")
    CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

    @classmethod
    def validate(cls):
        """Diagnostic check to see what the environment is actually providing"""
        required_vars = {
            "TENANT_ID": cls.TENANT_ID,
            "CLIENT_ID": cls.CLIENT_ID,
            "CLIENT_SECRET": cls.CLIENT_SECRET,
            "GROQ_KEY": cls.GROQ_API_KEY
        }
        
        missing = [name for name, val in required_vars.items() if not val]
        
        if missing:
            # This error will show in your Streamlit UI or GitHub logs
            raise EnvironmentError(
                f"❌ Connection Failed: The environment provided NO data for: {', '.join(missing)}. "
                "Check your GitHub Secrets or Streamlit Secrets dashboard."
            )
        else:
            print("✅ All secrets loaded from environment successfully.")

# Initialize and run diagnostic
settings = Settings()