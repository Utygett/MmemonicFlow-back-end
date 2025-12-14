#!/bin/bash

# ===============================
# Настройки
# ===============================
BASE_URL="http://localhost:8000/cards"
USER_ID="601dcf57-ce0e-4832-a0c5-f3e86fc70498"
CARD_ID="d0b5300e-aa29-4925-b883-16e0e81aa890"

echo "=============================="
echo "1️⃣ Получение всех карточек"
echo "=============================="
curl -s -X GET "$BASE_URL/" | jq

echo -e "\n\n=============================="
echo "2️⃣ Прогресс конкретной карточки"
echo "=============================="
curl -s -X GET "$BASE_URL/$CARD_ID/progress" | jq

echo -e "\n\n=============================="
echo "3️⃣ Получение карточек для повторения"
echo "=============================="
curl -s -X GET "$BASE_URL/review?user_id=$USER_ID&limit=5" | jq

echo -e "\n\n=============================="
echo "4️⃣ Отправка рейтинга 'good' для карточки"
echo "=============================="
curl -s -X POST "$BASE_URL/$CARD_ID/review?user_id=$USER_ID" \
-H "Content-Type: application/json" \
-d '{"rating":"good"}' | jq

echo -e "\n\n=============================="
echo "5️⃣ Проверка прогресса после обновления"
echo "=============================="
curl -s -X GET "$BASE_URL/$CARD_ID/progress" | jq
