"""Route unit tests with Dash's DB/framework boundaries replaced by fakes.

These exercise authorization and publication, not a running Sanic server.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import test_world_manager as store_tests

ROOT = Path(__file__).resolve().parent.parent


class RouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = store_tests.WorldTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.store = fixture.store
        self.user = types.SimpleNamespace(moderator=True)
        owner = self

        class Blueprint:
            def __init__(self, *args, **kwargs): pass
            def get(self, *args, **kwargs): return lambda handler: handler
            post = get

        class Query:
            def where(self, *args): return self
            @property
            def gino(self): return self
            async def first(self): return owner.user

        def result(body=None, status=200, **kwargs):
            return types.SimpleNamespace(body=body, status=status, **kwargs)

        def login_auth():
            def decorate(handler):
                async def authenticated(request, *args, **kwargs):
                    if not request.ctx.session.get("logged_in"):
                        return result(status=302)
                    return await handler(request, *args, **kwargs)
                return authenticated
            return decorate

        async def file(path, **kwargs): return result(Path(path).read_bytes(), **kwargs)

        self.app = types.SimpleNamespace(ctx=types.SimpleNamespace(world_store=self.store))
        modules = {
            "jinja2": types.SimpleNamespace(ChoiceLoader=object, FileSystemLoader=object),
            "sanic": types.SimpleNamespace(Blueprint=Blueprint, response=types.SimpleNamespace(
                text=result, json=result, html=result, redirect=result, file=file)),
            "sqlalchemy": types.SimpleNamespace(func=types.SimpleNamespace(lower=lambda value: value)),
            "dash": types.SimpleNamespace(app=self.app, env=types.SimpleNamespace()),
            "dash.data.penguin": types.SimpleNamespace(Penguin=types.SimpleNamespace(username="name", query=Query())),
            "dash.routes.manager.login": types.SimpleNamespace(login_auth=login_auth),
        }
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("wand_test_routes", ROOT / "world_manager/routes.py")
            self.routes = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.routes)

    def request(self, **form):
        return types.SimpleNamespace(method="POST", args={}, files={}, form={"csrf": "token", **form},
            ctx=types.SimpleNamespace(session={"logged_in": True, "username": "mod", "world_csrf": "token"}))

    async def test_non_moderators_and_anonymous_users_cannot_publish(self):
        request = self.request(action="restore_all", revision="0")
        request.ctx.session["logged_in"] = False
        self.assertEqual((await self.routes.update(request)).status, 302)
        request.ctx.session["logged_in"] = True
        self.user.moderator = False
        self.assertEqual((await self.routes.update(request)).status, 403)
        self.user = None
        self.assertEqual((await self.routes.update(request)).status, 403)
        self.assertEqual(self.store.snapshot(), (0, {}))

    async def test_missing_invalid_and_unicode_csrf_cannot_publish(self):
        for token in ("", "wrong", "ñ"):
            with self.subTest(token=token):
                request = self.request(csrf=token, action="restore_all", revision="0")
                self.assertEqual((await self.routes.update(request)).status, 403)
        self.assertEqual(self.store.snapshot(), (0, {}))

    async def test_authorized_publication_changes_public_config_and_revision(self):
        request = self.request(action="save", room="100", asset="original", music="9", revision="0")
        result = await self.routes.update(request)
        self.assertEqual(result.status, 303)
        public = await self.routes.rooms(request, "en", "json")
        self.assertEqual(public.body["100"]["music_id"], 9)
        self.assertEqual((await self.routes.revision(request)).body, {"revision": 1})
        self.assertIn("cp_rooms(", (await self.routes.rooms(request, "es", "jsonp")).body)

    async def test_public_assets_and_configs_reject_invalid_paths(self):
        request = self.request()
        self.assertEqual((await self.routes.asset(request, "../../secret")).status, 404)
        self.assertEqual((await self.routes.rooms(request, "../en", "json")).status, 404)
        self.assertEqual((await self.routes.rooms(request, "en", "html")).status, 404)

    async def test_online_roster_is_only_available_to_moderators(self):
        from unittest.mock import AsyncMock
        self.app.ctx.redis = types.SimpleNamespace(mget=AsyncMock(return_value=[None] * 4))
        request = self.request(); request.method = "GET"
        request.ctx.session["logged_in"] = False
        self.assertEqual((await self.routes.online_data(request)).status, 302)
        request.ctx.session["logged_in"] = True
        self.user.moderator = False
        self.assertEqual((await self.routes.online_data(request)).status, 403)
        self.user.moderator = True
        data = await self.routes.online_data(request)
        self.assertEqual(data.status, 200)
        self.assertEqual(data.body["players"], [])
        self.assertEqual(data.headers["Cache-Control"], "no-store")
        self.app.ctx.redis.mget.side_effect = RuntimeError("offline")
        self.assertEqual((await self.routes.online_data(request)).status, 503)


if __name__ == "__main__":
    unittest.main()
