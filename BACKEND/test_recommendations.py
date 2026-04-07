import sys
import types
import importlib
import json


# Minimal redis mock for tests
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
    r = c.get("/api/recommendations")
    print(r.status_code)
    print(json.dumps(r.get_json(), indent=2))
