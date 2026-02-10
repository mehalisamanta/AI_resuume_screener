"""
SharePoint Integration Utilities
"""

import streamlit as st
from config.settings import SHAREPOINT_AVAILABLE

if SHAREPOINT_AVAILABLE:
    from office365.sharepoint.client_context import ClientContext
    from office365.runtime.auth.user_credential import UserCredential

def connect_to_sharepoint(sharepoint_url, username, password):
    """Connect to SharePoint using credentials"""
    if not SHAREPOINT_AVAILABLE:
        st.error("SharePoint library not installed. Install with: pip install Office365-REST-Python-Client")
        return None
    
    try:
        credentials = UserCredential(username, password)
        ctx = ClientContext(sharepoint_url).with_credentials(credentials)
        web = ctx.web
        ctx.load(web)
        ctx.execute_query()
        return ctx
    except Exception as e:
        st.error(f"SharePoint connection failed: {str(e)}")
        return None