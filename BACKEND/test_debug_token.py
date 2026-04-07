import sys
import types
import importlib


# Minimal redis mock so `plumbapp` can import in tests
class _MockRedisModule(types.SimpleNamespace):

    class Redis:

        @staticmethod
        def from_url(url):

            class Client:

                def ping(self):
                    return True

                def geoadd(self, *a, **k):
                    return None

                def hset(self, *a, **k):
                    return None

                def zrem(self, *a, **k):
                    return None

                def hdel(self, *a, **k):
                    return None

                def georadius(self, *a, **k):
                    return []

            return Client()


sys.modules["redis"] = _MockRedisModule()


app_mod = importlib.import_module("plumbapp.app")
app = app_mod.app


with app.test_client() as c:

    # Preflight OPTIONS
    opt = c.open("/api/bookings/debug/token", method="OPTIONS")
    print("OPTIONS status:", opt.status_code)

    r = c.get("/api/bookings/debug/token")
    print("GET without auth status:", r.status_code)
    print("GET without auth body:", r.get_data(as_text=True))

    # Test with a dummy Bearer token string
    r2 = c.get(
        "/api/bookings/debug/token",
        headers={"Authorization": "Bearer mytesttoken123"},
    )
    print("GET with Bearer token status:", r2.status_code)
    print("GET with Bearer token body:", r2.get_json())
