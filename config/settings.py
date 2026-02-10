"""
Configuration Settings
"""

# Check for optional dependencies
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    TFIDF_AVAILABLE = True
except ImportError:
    TFIDF_AVAILABLE = False

try:
    from office365.sharepoint.client_context import ClientContext
    from office365.runtime.auth.user_credential import UserCredential
    from office365.sharepoint.caml_query import CamlQuery
    SHAREPOINT_AVAILABLE = True
except ImportError:
    SHAREPOINT_AVAILABLE = False

# Page Configuration
PAGE_CONFIG = {
    "page_title": "AI Resume Screening System",
    "page_icon": "🎯",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Custom CSS
CUSTOM_CSS = """
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 20px 0;
    }
    .sub-header {
        text-align: center;
        color: #555;
        font-size: 1.2rem;
        margin-bottom: 30px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    .logo-container {
        text-align: center;
        padding: 20px 0;
    }
    .logo-container img {
        max-width: 200px;
        height: auto;
    }
    </style>
"""

# Job Description Templates
JD_TEMPLATES = {
    "Senior Python Dev": """Senior Python Developer - 5+ years

Required:
- 5+ years Python
- FastAPI/Django/Flask
- AWS (Lambda, EC2, S3)
- Docker, Kubernetes
- PostgreSQL/MongoDB
- CI/CD pipelines

Responsibilities:
- Design scalable backends
- Lead architecture
- Mentor developers
- Production deployment""",
    
    "Data Scientist": """Data Scientist - ML Focus

Required:
- 3+ years ML/AI
- Python (NumPy, Pandas, Scikit-learn)
- TensorFlow/PyTorch
- SQL, data warehousing
- Statistical analysis
- Gen AI experience (plus)

Responsibilities:
- Build ML models
- Large-scale data analysis
- A/B testing""",
    
    "DevOps Engineer": """DevOps Engineer - Cloud Infrastructure

Required:
- 4+ years DevOps
- AWS/Azure/GCP
- Terraform, Ansible
- Docker, Kubernetes
- CI/CD (Jenkins, GitLab)
- Monitoring (Prometheus, Grafana)

Responsibilities:
- Infrastructure automation
- Pipeline optimization
- System reliability"""
}

# Groq Model Configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE_PARSING = 0.1
GROQ_TEMPERATURE_MATCHING = 0.3
GROQ_TEMPERATURE_QUESTIONS = 0.4