import os

TEST_ENVIRONMENT = {
    "SUPABASE_URL": "https://project.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "DATABASE_URL": "postgresql://postgres:password@db.project.supabase.co:5432/postgres",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_CHAT_MODEL": "openai:gpt-5-mini",
    "ALLOWED_ORIGINS": "http://localhost:5173",
}

if os.environ.get("RUN_RETRIEVAL_INTEGRATION") != "1":
    for name, value in TEST_ENVIRONMENT.items():
        os.environ.setdefault(name, value)
