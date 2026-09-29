"""API 测试：认证。"""


class TestAuth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_login_success(self, client):
        r = client.post("/auth/login", json={"name": "管理员", "password": "admin123"})
        assert r.status_code == 200
        d = r.json()
        assert "token" in d
        assert d["user"]["role"] == "admin"

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", json={"name": "管理员", "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        r = client.post("/auth/login", json={"name": "不存在", "password": "x"})
        assert r.status_code == 401

    def test_me_requires_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, client, auth_headers):
        r = client.get("/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "管理员"

    def test_engineer_permissions(self, client):
        r = client.post("/auth/login", json={"name": "张工", "password": "engineer123"})
        assert r.status_code == 200
        perms = r.json()["user"]["effective_permissions"]
        assert "ticket.accept" in perms
        assert "refund.approve" not in perms
