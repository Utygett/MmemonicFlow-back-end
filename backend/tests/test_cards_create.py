import uuid

from backend.tests.conftest import register_and_login, create_deck


def test_create_card_owner_ok(client):
    _, token = register_and_login(client)
    deck_id = create_deck(client, token, title="My Deck")

    payload = {
        "deck_id": deck_id,
        "title": "Card 1",
        "type": "basic",
        "levels": [{"question": "q1", "answer": "a1"}],
    }

    r = client.post(
        "/api/cards/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 201, r.text
    data = r.json()

    assert "card_id" in data
    assert data["deck_id"] == deck_id

    # Проверяем, что карточка реально появилась в колоде
    r2 = client.get(
        f"/api/decks/{deck_id}/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, r2.text
    cards = r2.json()
    assert any(c.get("card_id") == data["card_id"] for c in cards), cards


def test_create_card_forbidden_not_owner(client):
    # user1 creates deck
    _, token1 = register_and_login(client)
    deck_id = create_deck(client, token1, title="Owner Deck")

    # user2 tries to create card in чужой deck
    _, token2 = register_and_login(client)

    payload = {
        "deck_id": deck_id,
        "title": "Hack",
        "type": "basic",
        "levels": [{"question": "q", "answer": "a"}],
    }
    r = client.post(
        "/api/cards/",
        headers={"Authorization": f"Bearer {token2}"},
        json=payload,
    )
    assert r.status_code == 403, r.text


def test_create_card_unauthorized(client):
    payload = {
        "deck_id": str(uuid.uuid4()),
        "title": "Card",
        "type": "basic",
        "levels": [{"question": "q", "answer": "a"}],
    }
    r = client.post("/api/cards/", json=payload)
    assert r.status_code == 401, r.text


def test_create_card_deck_not_found(client):
    _, token = register_and_login(client)

    payload = {
        "deck_id": str(uuid.uuid4()),
        "title": "Card",
        "type": "basic",
        "levels": [{"question": "q", "answer": "a"}],
    }
    r = client.post(
        "/api/cards/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 404, r.text


def test_create_card_validation_levels_empty(client):
    _, token = register_and_login(client)
    deck_id = create_deck(client, token)

    payload = {
        "deck_id": deck_id,
        "title": "Card",
        "type": "basic",
        "levels": [],
    }
    r = client.post(
        "/api/cards/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 422, r.text


def test_create_card_validation_title_empty(client):
    _, token = register_and_login(client)
    deck_id = create_deck(client, token)

    payload = {
        "deck_id": deck_id,
        "title": "   ",
        "type": "basic",
        "levels": [{"question": "q", "answer": "a"}],
    }
    r = client.post(
        "/api/cards/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 422, r.text
