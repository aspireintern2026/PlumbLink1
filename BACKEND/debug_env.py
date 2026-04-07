from dotenv import load_dotenv
import os

load_dotenv()

print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_ANON_KEY:", os.getenv("SUPABASE_ANON_KEY"))
print("SUPABASE_SERVICE_ROLE_KEY:", os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
print("SECRET_KEY:", os.getenv("SECRET_KEY"))

