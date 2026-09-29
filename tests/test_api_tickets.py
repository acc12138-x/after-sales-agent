"""API 测试：工单等。"""


class TestTickets:
    def test_list_tickets(self, client):
        r = client.get("/tickets")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_users_meta(self, client):
        r = client.get("/users/meta")
        assert r.status_code == 200
        d = r.json()
        assert "roles" in d
        assert "all_permissions" in d
        assert len(d["roles"]) >= 4
        assert len(d["all_permissions"]) >= 15

    def test_sla_summary(self, client):
        r = client.get("/sla/summary")
        assert r.status_code == 200
        d = r.json()
        for k in ["total", "normal", "warning", "overdue"]:
            assert k in d

    def test_sla_rules(self, client):
        r = client.get("/sla/rules")
        assert r.status_code == 200
