from supabase import Client, create_client

from app.config import settings


def create_service_role_client() -> Client:
    """Create a backend client for privileged, explicitly authorized operations."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def create_user_client(access_token: str) -> Client:
    """Create an anon-key client whose database requests use one user's JWT."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client
