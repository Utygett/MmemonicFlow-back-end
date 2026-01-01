import uuid as uuidlib
from uuid import UUID

from fastapi.testclient import TestClient

from app.models.user_study_group import UserStudyGroup
from app.models.user_study_group_deck import UserStudyGroupDeck


def _unique_email() -> str:
    return f"g{uuidlib.uuid4().hex[:10]}@example.com"


def register_and_login(client: TestClient, password: str = "password123") -> tuple[str, str]:
    email = _unique_email()

    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    data = r.json()

    access_token = data.get("access_token") or data.get("accesstoken")
    assert access_token, data
    return email, access_token


def get_me_id(client: TestClient, token: str) -> str:
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def create_group(client: TestClient, token: str, title: str = "Group") -> str:
    r = client.post(
        "/api/groups/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title, "description": None, "parentid": None},
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()

    group_id = data.get("id")
    assert group_id, data
    return group_id


def create_deck(client: TestClient, token: str, title: str = "Deck") -> str:
    r = client.post(
        "/api/decks/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title, "description": None, "color": None},
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()

    deck_id = data.get("deck_id") or data.get("deckid")
    assert deck_id, data
    return deck_id


class TestGroupDeckLinks:
    def test_put_add_deck_to_group_success(self, client: TestClient, db):
        _, token = register_and_login(client)
        user_id = get_me_id(client, token)

        group_id = create_group(client, token, title="G1")
        deck_id = create_deck(client, token, title="D1")

        put = client.put(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert put.status_code == 204, put.text

        ug = (
            db.query(UserStudyGroup)
            .filter(
                UserStudyGroup.user_id == UUID(user_id),
                UserStudyGroup.source_group_id == UUID(group_id),
            )
            .first()
        )
        assert ug is not None

        link = (
            db.query(UserStudyGroupDeck)
            .filter(
                UserStudyGroupDeck.user_group_id == ug.id,
                UserStudyGroupDeck.deck_id == UUID(deck_id),
            )
            .first()
        )
        assert link is not None

        g = client.get(
            f"/api/groups/{group_id}/decks",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200, g.text
        decks = g.json()
        assert any((d.get("deck_id") or d.get("deckid")) == deck_id for d in decks), decks

    def test_put_add_deck_to_group_idempotent(self, client: TestClient, db):
        _, token = register_and_login(client)
        user_id = get_me_id(client, token)

        group_id = create_group(client, token, title="G1")
        deck_id = create_deck(client, token, title="D1")

        r1 = client.put(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 204, r1.text

        r2 = client.put(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 204, r2.text

        ug = (
            db.query(UserStudyGroup)
            .filter(
                UserStudyGroup.user_id == UUID(user_id),
                UserStudyGroup.source_group_id == UUID(group_id),
            )
            .first()
        )
        assert ug is not None

        links = (
            db.query(UserStudyGroupDeck)
            .filter(
                UserStudyGroupDeck.user_group_id == ug.id,
                UserStudyGroupDeck.deck_id == UUID(deck_id),
            )
            .all()
        )
        assert len(links) == 1

    def test_delete_remove_deck_from_group_success(self, client: TestClient, db):
        _, token = register_and_login(client)
        user_id = get_me_id(client, token)

        group_id = create_group(client, token, title="G1")
        deck_id = create_deck(client, token, title="D1")

        add = client.put(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert add.status_code == 204, add.text

        delete = client.delete(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204, delete.text

        ug = (
            db.query(UserStudyGroup)
            .filter(
                UserStudyGroup.user_id == UUID(user_id),
                UserStudyGroup.source_group_id == UUID(group_id),
            )
            .first()
        )
        assert ug is not None

        link = (
            db.query(UserStudyGroupDeck)
            .filter(
                UserStudyGroupDeck.user_group_id == ug.id,
                UserStudyGroupDeck.deck_id == UUID(deck_id),
            )
            .first()
        )
        assert link is None

    def test_delete_idempotent_when_missing(self, client: TestClient):
        _, token = register_and_login(client)

        group_id = create_group(client, token, title="G1")
        deck_id = create_deck(client, token, title="D1")

        delete = client.delete(
            f"/api/groups/{group_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204, delete.text

    def test_add_deck_to_group_unauthorized(self, client: TestClient):
        group_id = str(uuidlib.uuid4())
        deck_id = str(uuidlib.uuid4())

        r = client.put(f"/api/groups/{group_id}/decks/{deck_id}")
        assert r.status_code == 401, r.text

    def test_add_private_foreign_deck_forbidden(self, client: TestClient):
        # user1 creates deck (по текущей логике /api/decks/ создаёт is_public=False)
        _, token1 = register_and_login(client)
        deck_id = create_deck(client, token1, title="U1 deck (private)")

        # user2 tries to add it into his group
        _, token2 = register_and_login(client)
        group2_id = create_group(client, token2, title="U2 group")

        r = client.put(
            f"/api/groups/{group2_id}/decks/{deck_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r.status_code == 403, r.text

    def test_add_deck_to_foreign_group_returns_404(self, client: TestClient):
        # user1 owns group
        _, token1 = register_and_login(client)
        group1_id = create_group(client, token1, title="U1 group")

        # user2 tries to use that group id
        _, token2 = register_and_login(client)
        deck2_id = create_deck(client, token2, title="U2 deck")

        r = client.put(
            f"/api/groups/{group1_id}/decks/{deck2_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r.status_code == 404, r.text
