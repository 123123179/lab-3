from flask import Flask, request, jsonify, make_response
from functools import wraps
import base64

app = Flask(__name__)

# "База" користувачів для HTTP Basic-аутентифікації
USERS = {
    "admin": "admin123",
    "user": "user123"
}

# Каталог товарів зберігаємо у звичайному dictionary (пам'ять програми)
# Кожен товар має як мінімум 3 параметри: id, name, price
items = {
    1: {
        "id": 1,
        "name": "Arabica",
        "price": 100.25,
        "color": "brown",
        "weight": 250
    },
    2: {
        "id": 2,
        "name": "Robusta",
        "price": 85.50,
        "color": "dark brown",
        "weight": 500
    }
}


def check_basic_auth(auth_header: str):
    """
    Розбір заголовка Authorization: Basic base64(username:password)
    Повертає username, якщо авторизація успішна, або None.
    """
    if not auth_header or not auth_header.startswith("Basic "):
        return None

    try:
        encoded_part = auth_header.split(" ", 1)[1]
        decoded_bytes = base64.b64decode(encoded_part)
        decoded_str = decoded_bytes.decode("utf-8")
        username, password = decoded_str.split(":", 1)
    except Exception:
        return None

    if USERS.get(username) == password:
        return username
    return None


def require_auth(f):
    """
    Декоратор для захисту ендпоінтів HTTP Basic-аутентифікацією.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        user = check_basic_auth(auth_header)

        if not user:
            # Якщо користувач не авторизований — повертаємо 401 та заголовок WWW-Authenticate
            resp = make_response(
                jsonify({"error": "Authentication required"}), 401
            )
            resp.headers["WWW-Authenticate"] = 'Basic realm="Catalog API"'
            return resp

        # За потреби можна зберегти імʼя користувача у request
        request.current_user = user
        return f(*args, **kwargs)

    return decorated


@app.route("/items", methods=["GET", "POST", "PUT", "DELETE"])
@require_auth
def items_collection():
    """
    /items
    GET    – повертає весь каталог товарів
    POST   – створює новий товар
    PUT    – повне оновлення каталогу (список товарів)
    DELETE – видаляє всі товари з каталогу
    Всі дані передаються та повертаються у форматі JSON.
    """
    if request.method == "GET":
        # Повертаємо список всіх товарів
        return jsonify(list(items.values())), 200

    if request.method == "POST":
        # Створення нового товару
        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400

        data = request.get_json()

        # Перевірка обовʼязкових полів
        required_fields = ["id", "name", "price"]
        if not all(field in data for field in required_fields):
            return jsonify({
                "error": "Fields 'id', 'name' and 'price' are required"
            }), 400

        try:
            item_id = int(data["id"])
        except ValueError:
            return jsonify({"error": "Field 'id' must be integer"}), 400

        if item_id in items:
            return jsonify({"error": "Item with this id already exists"}), 409

        # Формування запису товару
        new_item = {
            "id": item_id,
            "name": data["name"],
            "price": float(data["price"]),
            "color": data.get("color"),
            "weight": data.get("weight")
        }

        items[item_id] = new_item
        return jsonify(new_item), 201

    if request.method == "PUT":
        # Повне оновлення каталогу – очікуємо список товарів у JSON
        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400

        data = request.get_json()

        if not isinstance(data, list):
            return jsonify({"error": "Expected list of items"}), 400

        new_items = {}
        for raw_item in data:
            if not all(k in raw_item for k in ["id", "name", "price"]):
                return jsonify({
                    "error": "Each item must contain 'id', 'name', 'price'"
                }), 400
            try:
                item_id = int(raw_item["id"])
                price = float(raw_item["price"])
            except ValueError:
                return jsonify({
                    "error": "Fields 'id' must be int, 'price' must be number"
                }), 400

            new_items[item_id] = {
                "id": item_id,
                "name": raw_item["name"],
                "price": price,
                "color": raw_item.get("color"),
                "weight": raw_item.get("weight")
            }

        # Якщо всі елементи валідні – замінюємо каталог
        items.clear()
        items.update(new_items)

        return jsonify(list(items.values())), 200

    if request.method == "DELETE":
        # Видаляємо всі товари
        items.clear()
        return jsonify({"message": "All items deleted"}), 200


@app.route("/items/<int:item_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def item_detail(item_id: int):
    """
    /items/<id>
    GET    – отримати інформацію про конкретний товар
    PUT    – оновити товар (часткове або повне оновлення полів)
    DELETE – видалити товар
    Метод POST тут НЕ потрібен згідно умови.
    """
    if request.method == "GET":
        item = items.get(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        return jsonify(item), 200

    if request.method == "PUT":
        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400

        if item_id not in items:
            return jsonify({"error": "Item not found"}), 404

        data = request.get_json()

        # Дозволяємо часткове оновлення полів
        for field in ["name", "price", "color", "weight"]:
            if field in data:
                # Приводимо до типів для price / weight
                if field == "price":
                    try:
                        items[item_id][field] = float(data[field])
                    except ValueError:
                        return jsonify({"error": "Field 'price' must be number"}), 400
                elif field == "weight":
                    try:
                        items[item_id][field] = int(data[field])
                    except ValueError:
                        return jsonify({"error": "Field 'weight' must be integer"}), 400
                else:
                    items[item_id][field] = data[field]

        return jsonify(items[item_id]), 200

    if request.method == "DELETE":
        if item_id not in items:
            return jsonify({"error": "Item not found"}), 404

        deleted_item = items.pop(item_id)
        return jsonify({
            "message": "Item deleted",
            "item": deleted_item
        }), 200


if __name__ == "__main__":
    # Запуск сервісу
    app.run(host="127.0.0.1", port=5000, debug=True)