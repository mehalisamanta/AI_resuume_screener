"""
Groq Client Initialization - with primary/fallback API key support
"""

import streamlit as st
from groq import Groq, AuthenticationError, APIStatusError


def init_groq_client(api_key: str):
    """Initialize and cache Groq client (no fallback)."""
    return Groq(api_key=api_key)


def create_groq_completion(client, fallback_client, **kwargs):
    """
    Attempt a chat completion with the primary client.
    If it fails due to auth / rate-limit / quota, transparently retry
    with the fallback client (if one is configured).

    All kwargs are forwarded directly to client.chat.completions.create().
    Returns the response object.
    """
    try:
        return client.chat.completions.create(**kwargs)
    except (AuthenticationError, APIStatusError) as primary_err:
        if fallback_client is None:
            raise

        st.warning(
            f"⚠️ Primary Groq key failed ({type(primary_err).__name__}). "
            "Switching to fallback key…",
            icon="🔄",
        )
        try:
            return fallback_client.chat.completions.create(**kwargs)
        except Exception as fallback_err:
            st.error(f"❌ Fallback key also failed: {fallback_err}")
            raise fallback_err
    except Exception as e:
        # For any other error try fallback before giving up
        if fallback_client is None:
            raise
        st.warning(
            f"⚠️ Primary Groq key encountered an error ({e}). "
            "Trying fallback key…",
            icon="🔄",
        )
        return fallback_client.chat.completions.create(**kwargs)