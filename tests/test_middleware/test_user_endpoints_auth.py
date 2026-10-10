"""Tests de la autenticación opcional en los endpoints "de usuario".

Con REQUIRE_KEY_USER_ENDPOINTS=false (por defecto) siguen siendo públicos para no
romper al bot; con true exigen X-API-Key válida (el bot y la miniapp la mandan).
"""

from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.main import app as real_app
from src.middleware import auth as auth_module
from src.middleware.auth import get_api_key, require_auth_user_endpoints

KEY = "clave-secreta-de-prueba"


def _settings(require: bool):
    return SimpleNamespace(admin_api_key=KEY, require_key_user_endpoints=require)


def _mini_app() -> TestClient:
    mini = FastAPI()

    @mini.get("/user", dependencies=[Depends(require_auth_user_endpoints)])
    async def user_endpoint():
        return {"ok": True}

    return TestClient(mini)


class TestRequireAuthUserEndpoints:
    def test_flag_off_keeps_endpoint_public(self, monkeypatch):
        monkeypatch.setattr(auth_module, "get_settings", lambda: _settings(False))
        assert _mini_app().get("/user").status_code == 200

    def test_flag_on_without_key_is_401(self, monkeypatch):
        monkeypatch.setattr(auth_module, "get_settings", lambda: _settings(True))
        assert _mini_app().get("/user").status_code == 401

    def test_flag_on_wrong_key_is_401(self, monkeypatch):
        monkeypatch.setattr(auth_module, "get_settings", lambda: _settings(True))
        response = _mini_app().get("/user", headers={"X-API-Key": "otra"})
        assert response.status_code == 401

    def test_flag_on_right_key_is_200(self, monkeypatch):
        monkeypatch.setattr(auth_module, "get_settings", lambda: _settings(True))
        response = _mini_app().get("/user", headers={"X-API-Key": KEY})
        assert response.status_code == 200

    def test_key_with_non_ascii_characters_does_not_crash(self, monkeypatch):
        """compare_digest sobre bytes: una clave con tildes/ñ da 401, no 500."""
        monkeypatch.setattr(auth_module, "get_settings", lambda: _settings(True))
        mini = FastAPI()

        @mini.get("/admin")
        async def admin_endpoint(_key: str = Depends(get_api_key)):
            return {"ok": True}

        response = TestClient(mini).get("/admin", headers={"X-API-Key": "clavé-ñ".encode("utf-8")})
        assert response.status_code == 401


def _routes_requiring_user_auth():
    protegidas = []
    for route in real_app.routes:
        path = getattr(route, "path", "")
        es_usuario = "/images/alerts" in path or "/subscriptions/me/" in path
        if es_usuario:
            deps = [d.dependency for d in getattr(route, "dependencies", [])]
            protegidas.append((path, require_auth_user_endpoints in deps))
    return protegidas


def test_all_user_routes_use_the_dependency():
    """Guardia de regresión: ninguna ruta de usuario puede quedarse sin la dependencia."""
    rutas = _routes_requiring_user_auth()
    assert rutas, "no se encontraron rutas de usuario (¿cambió el prefijo?)"
    sin_proteger = [path for path, ok in rutas if not ok]
    assert sin_proteger == []


def test_image_alert_default_time_is_0730():
    from src.schemas.image import AlertCreateSchema

    schema = AlertCreateSchema(user_id=1)
    assert schema.alert_time == "07:30"
