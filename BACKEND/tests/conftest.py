import pytest
import warnings

# Suppress general DeprecationWarnings from dependencies
# (pydantic, supabase, storage3)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pydantic.config.Extra.*")
warnings.filterwarnings("ignore", message=".*PydanticDeprecatedSince20.*")
warnings.filterwarnings("ignore", message=".*timeout.*deprecated.*")
warnings.filterwarnings("ignore", message=".*verify.*deprecated.*")


@pytest.fixture
def sample_fixture():
    return "Hello, World!"