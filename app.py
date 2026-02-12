"""
AI-Powered Resume Screening System - Main Application
Built with Groq for Ultra-Fast LLM Processing
"""

import os
import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from PIL import Image

# Load .env if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass  # python-dotenv not installed; rely on env vars / Streamlit secrets

from config.settings import PAGE_CONFIG, CUSTOM_CSS
from utils.groq_client import init_groq_client
from utils.sharepoint import SHAREPOINT_AVAILABLE, SHAREPOINT_ERROR
from ui.tabs import render_upload_tab, render_database_tab, render_matching_tab, render_analytics_tab

# ── Page Configuration ─────────────────────────────────────────────────────────
st.set_page_config(**PAGE_CONFIG)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Session State Initialisation ───────────────────────────────────────────────
_defaults = {
    'parsed_resumes': [],
    'candidates_df': None,
    'matched_results': None,
    'resume_texts': {},
    'resume_metadata': {},
    # SharePoint (Graph API) config
    'sharepoint_config': {
        'tenant_id': os.getenv('TENANT_ID', ''),
        'client_id': os.getenv('CLIENT_ID', ''),
        'client_secret': os.getenv('CLIENT_SECRET', ''),
        'site_id': os.getenv('SHAREPOINT_SITE_ID', ''),
        'drive_id': os.getenv('SHAREPOINT_DRIVE_ID', ''),
        'folder_path': 'Shared Documents/Resumes',
        'connected': False,
    },
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # Header
    st.markdown('<div class="nexturn-header">', unsafe_allow_html=True)
    try:
        logo = Image.open("logo.png")
        col1, col2, col3 = st.columns([1, 1.3, 1])
        with col2:
            st.image(logo, width=400)
    except FileNotFoundError:
        st.error("⚠️ Logo file 'logo.png' not found in the app folder")

    st.markdown('<hr style="margin: 20px 0; border: none; border-top: 2px solid #e0e0e0;">', unsafe_allow_html=True)
    st.markdown("""
    <h1 style="font-size: 3rem; font-weight: 700; color: #1a1a1a; text-align: center;
               margin: 15px 0 10px 0; letter-spacing: -0.5px;">
          Resume Screening System
    </h1>
    <p style="font-size: 1.15rem; color: #666; text-align: center; margin-bottom: 10px;">
         Powered by Groq | Automated Intelligent Recruitment
    </p>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("⚙️ Configuration")

        # ── Groq API Keys ──────────────────────────────────────────────────────
        st.subheader("🔑 Groq API Keys")

        groq_api_key = st.text_input(
            "Primary Groq API Key",
            type="password",
            value=st.session_state.get('groq_api_key', os.getenv('GROQ_API_KEY', '')),
            help="Get a free key at https://console.groq.com",
        )
        groq_fallback_key = st.text_input(
            "Fallback Groq API Key (optional)",
            type="password",
            value=st.session_state.get('groq_fallback_key', os.getenv('GROQ_FALLBACK_API_KEY', '')),
            help="Used automatically if the primary key fails or hits its rate limit.",
        )

        client = None
        fallback_client = None

        if groq_api_key:
            st.session_state['groq_api_key'] = groq_api_key
            try:
                client = init_groq_client(groq_api_key)
                st.success("✅ Primary key connected")
            except Exception:
                st.error("❌ Primary key invalid")

        else:
            st.warning("⚠️ Enter Primary API Key")

        if groq_fallback_key:
            st.session_state['groq_fallback_key'] = groq_fallback_key
            try:
                fallback_client = init_groq_client(groq_fallback_key)
                st.info("🔄 Fallback key ready")
            except Exception:
                st.warning("⚠️ Fallback key appears invalid")

        st.divider()

        # ── Privacy ────────────────────────────────────────────────────────────
        st.subheader("🛡️ Privacy Settings")
        mask_pii_enabled = st.checkbox(
            "Enable PII Masking",
            value=True,
            help="Redact emails and phone numbers before sending to LLM",
        )

        st.divider()

        # ── SharePoint (Microsoft Graph API) ───────────────────────────────────
        st.subheader("☁️ SharePoint (Azure App)")

        if not SHAREPOINT_AVAILABLE:
            st.error("⚠️ `msal` library not installed.")
            if SHAREPOINT_ERROR:
                with st.expander("Error details"):
                    st.code(SHAREPOINT_ERROR)
            st.code("pip install msal", language="bash")
        else:
            sp = st.session_state.sharepoint_config

            with st.expander("🔐 Azure AD Credentials", expanded=not sp.get('connected')):
                sp['tenant_id'] = st.text_input(
                    "Tenant ID", value=sp.get('tenant_id', ''),
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    key="sp_tenant",
                )
                sp['client_id'] = st.text_input(
                    "Client ID", value=sp.get('client_id', ''),
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    key="sp_client",
                )
                sp['client_secret'] = st.text_input(
                    "Client Secret", value=sp.get('client_secret', ''),
                    type="password", key="sp_secret",
                )

            with st.expander("📁 Site & Drive IDs", expanded=not sp.get('connected')):
                st.caption("Run `find_my_id.py` once to get these values.")
                sp['site_id'] = st.text_input(
                    "Site ID", value=sp.get('site_id', ''),
                    placeholder="tenant.sharepoint.com,guid,guid",
                    key="sp_site_id",
                )
                sp['drive_id'] = st.text_input(
                    "Drive ID", value=sp.get('drive_id', ''),
                    placeholder="b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    key="sp_drive_id",
                )
                sp['folder_path'] = st.text_input(
                    "Folder Path (in drive)",
                    value=sp.get('folder_path', 'Shared Documents/Resumes'),
                    placeholder="Demair  or  General/Resumes",
                    key="sp_folder",
                )

            if st.button("🔗 Connect to SharePoint", type="primary", use_container_width=True):
                required = [sp.get('tenant_id'), sp.get('client_id'),
                            sp.get('client_secret'), sp.get('site_id'), sp.get('drive_id')]
                if all(required):
                    with st.spinner("Authenticating with Azure AD…"):
                        try:
                            import msal
                            authority = f"https://login.microsoftonline.com/{sp['tenant_id']}"
                            msal_app = msal.ConfidentialClientApplication(
                                sp['client_id'],
                                authority=authority,
                                client_credential=sp['client_secret'],
                            )
                            token_res = msal_app.acquire_token_for_client(
                                scopes=["https://graph.microsoft.com/.default"]
                            )
                            if "access_token" in token_res:
                                sp['connected'] = True
                                st.session_state.sharepoint_config = sp
                                st.success("✅ Connected to SharePoint!")
                                st.rerun()
                            else:
                                st.error(f"Auth failed: {token_res.get('error_description')}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                else:
                    st.error("Please fill in all SharePoint credentials and IDs.")

            if sp.get('connected'):
                st.success("✅ SharePoint Connected")
                if st.button("🔌 Disconnect", use_container_width=True):
                    sp['connected'] = False
                    st.session_state.sharepoint_config = sp
                    st.rerun()

        st.divider()

        # ── Date Filter ────────────────────────────────────────────────────────
        st.subheader("📅 Resume Submission Date Range")
        use_date_filter = st.checkbox("Enable date range filter", value=False)

        start_date = end_date = None
        if use_date_filter:
            if st.session_state.candidates_df is not None and 'submission_date' in st.session_state.candidates_df.columns:
                try:
                    df_dates = pd.to_datetime(st.session_state.candidates_df['submission_date'])
                    min_date = df_dates.min().date()
                    max_date = df_dates.max().date()
                except Exception:
                    min_date = datetime.now().date() - timedelta(days=90)
                    max_date = datetime.now().date()
            else:
                min_date = datetime.now().date() - timedelta(days=90)
                max_date = datetime.now().date()

            date_range = st.slider(
                "Select date range",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date),
                format="YYYY-MM-DD",
            )
            start_date, end_date = date_range
            st.info(f"📅 Filtering: {start_date} to {end_date}")

        st.divider()

        # ── Top N ──────────────────────────────────────────────────────────────
        st.subheader("🎚️ Top Candidates to Review")
        top_n = st.select_slider(
            "Select number",
            options=[1, 2, 3, 5, 10, 15, 20],
            value=5,
        )
        if top_n <= 3:
            st.warning("⚡ Urgent hiring mode")
        elif top_n <= 5:
            st.info("📅 Standard recruitment")
        else:
            st.success("🕐 Comprehensive review")

    # ── Store config in session state ──────────────────────────────────────────
    st.session_state['mask_pii_enabled'] = mask_pii_enabled
    st.session_state['use_date_filter'] = use_date_filter
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date
    st.session_state['top_n'] = top_n
    st.session_state['client'] = client
    st.session_state['fallback_client'] = fallback_client

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload Resumes",
        "📊 Candidate Pool",
        "🎯 AI Matching",
        "📈 Analytics Dashboard",
    ])

    with tab1:
        render_upload_tab()
    with tab2:
        render_database_tab()
    with tab3:
        render_matching_tab()
    with tab4:
        render_analytics_tab()

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>AI Resume Screening System | Automated Intelligent Recruitment | Built with Streamlit & Groq</p>
        <p style="font-size: 0.85em;">© 2026 NEXTURN. All rights reserved.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()