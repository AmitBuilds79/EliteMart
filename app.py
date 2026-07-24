import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session
from config import get_db_connection
import mysql.connector

app = Flask(__name__)
app.secret_key = "elite123"


print("DB_HOST =", os.environ.get("DB_HOST"))
print("DB_PORT =", os.environ.get("DB_PORT"))
# Database Connection Test
try:
    conn = get_db_connection()
    print("Database Connected Successfully")
    conn.close()
except Exception as e:
    print("Database Connection Failed")
    print(e)


# Home Page
@app.route("/")
def home():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT
        products.*,
        categories.category_name
    FROM products
    JOIN categories
    ON products.category_id = categories.id
    """)

    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("index.html", products=products)

@app.route("/product/<int:product_id>")
def product_details(product_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Product
    cursor.execute(
        "SELECT * FROM products WHERE id=%s",
        (product_id,)
    )
    product = cursor.fetchone()

    # Reviews
    cursor.execute("""
        SELECT * FROM reviews
        WHERE product_id = %s
        ORDER BY created_at DESC
    """, (product_id,))
    reviews = cursor.fetchall()

    # Average Rating
    cursor.execute("""
        SELECT
            ROUND(AVG(rating), 1) AS avg_rating,
            COUNT(*) AS total_reviews
        FROM reviews
        WHERE product_id = %s
    """, (product_id,))
    rating_data = cursor.fetchone()

    cursor.close()
    conn.close()

    if product is None:
        return "Product Not Found"

    return render_template(
        "product_details.html",
        product=product,
        reviews=reviews,
        rating_data=rating_data
    )

@app.route("/add_review/<int:product_id>", methods=["POST"])
def add_review(product_id):

    username = session.get("user")

    if not username:
        return redirect("/login")

    rating = request.form["rating"]
    review = request.form["review"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reviews (product_id, username, rating, review)
        VALUES (%s, %s, %s, %s)
    """, (product_id, username, rating, review))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(f"/product/{product_id}")

@app.route("/search")
def search():
    query = request.args.get("q", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
    """
    SELECT * FROM products
    WHERE product_name LIKE %s
       OR description LIKE %s
    """,
    ("%" + query + "%", "%" + query + "%")
)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("index.html", products=products, query=query)


# Register
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        address = request.form["address"]

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, phone, password, address)
                VALUES (%s, %s, %s, %s, %s)
            """, (full_name, email, phone, password, address))

            conn.commit()

        except mysql.connector.IntegrityError:
            cursor.close()
            conn.close()
            return "❌ Email already exists!"

        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]          
            session["user"] = user["full_name"]
                
            return redirect(url_for("home"))

        else:
            return "❌ Invalid Email or Password"

    return render_template("login.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    # Logged-in user ki ID
    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )
    user = cursor.fetchone()

    # Product stock check
    cursor.execute(
        "SELECT stock FROM products WHERE id=%s",
        (product_id,)
    )
    product = cursor.fetchone()

    if product["stock"] <= 0:
        cursor.close()
        conn.close()
        return "Product is Out of Stock!"

    # Check if product already exists in cart
    cursor.execute("""
        SELECT id, quantity
        FROM cart
        WHERE user_id=%s AND product_id=%s
    """, (user["id"], product_id))

    cart_item = cursor.fetchone()

    if cart_item:
        # Increase quantity
        cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE id=%s
        """, (cart_item["id"],))
    else:
        # Insert new row
        cursor.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (%s, %s, 1)
        """, (user["id"], product_id))


    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("home"))

@app.route("/cart")
def cart():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )

    user = cursor.fetchone()

    cursor.execute("""
        SELECT cart.id,
               products.product_name,
               products.price,
               products.image,
               cart.quantity
        FROM cart
        JOIN products
        ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user["id"],))

    cart_items = cursor.fetchall()

    total = 0
    for item in cart_items:
        total += item["price"] * item["quantity"]

    cursor.close()
    conn.close()

    return render_template(
    "cart.html",
    cart_items=cart_items,
    total=total
)
@app.route("/remove_from_cart/<int:cart_id>")
def remove_from_cart(cart_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )
    user = cursor.fetchone()

    cursor.execute(
    "DELETE FROM cart WHERE id=%s",
    (cart_id,)
)

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("cart"))

@app.route("/increase_quantity/<int:cart_id>")
def increase_quantity(cart_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE cart SET quantity = quantity + 1 WHERE id=%s",
        (cart_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("cart"))


@app.route("/decrease_quantity/<int:cart_id>")
def decrease_quantity(cart_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE cart SET quantity = quantity - 1 WHERE id=%s AND quantity > 1",
        (cart_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    # Logged in user
    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )
    user = cursor.fetchone()

    # Cart Items
    cursor.execute("""
        SELECT
            products.id AS product_id,
            products.product_name,
            products.price,
            products.stock,
            cart.quantity
        FROM cart
        JOIN products
        ON cart.product_id = products.id
        WHERE cart.user_id=%s
    """, (user["id"],))

    cart_items = cursor.fetchall()

    total = 0
    for item in cart_items:
        total += item["price"] * item["quantity"]

    if request.method == "POST":

        address = request.form["address"]
        payment = request.form["payment"]

        # Stock Check
        for item in cart_items:

            if item["stock"] < item["quantity"]:
                cursor.close()
                conn.close()
                return f'{item["product_name"]} is Out of Stock'

        # Create Order
        cursor.execute("""
    INSERT INTO orders
    (user_id, total, status)
    VALUES (%s, %s, 'Pending')
""", (user["id"], total))

        conn.commit()

        order_id = cursor.lastrowid

        # Save Order Items & Reduce Stock
        for item in cart_items:

            cursor.execute("""
                INSERT INTO order_items
                (order_id,product_id,quantity,price)
                VALUES (%s,%s,%s,%s)
            """, (
                order_id,
                item["product_id"],
                item["quantity"],
                item["price"]
            ))
            print("Reducing stock:", item["product_id"], item["quantity"])

            # Reduce Stock
            cursor.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE id=%s
            """, (
                item["quantity"],
                item["product_id"]
            ))

            print("Rows Updated:", cursor.rowcount)

        conn.commit()

        # Empty Cart
        cursor.execute(
            "DELETE FROM cart WHERE user_id=%s",
            (user["id"],)
        )

        conn.commit()

        cursor.close()
        conn.close()

        return render_template(
            "order_success.html",
            total=total,
            address=address,
            payment=payment
        )

    cursor.close()
    conn.close()

    return render_template(
        "checkout.html",
        total=total
    )


@app.route("/my_orders")
def my_orders():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )
    user = cursor.fetchone()
    cursor.fetchall()
    cursor.execute("""
        SELECT *
        FROM orders
        WHERE user_id=%s
        ORDER BY id DESC
    """, (user["id"],))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("my_orders.html", orders=orders)

@app.route("/order_details/<int:order_id>")
def order_details(order_id):

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            products.product_name,
            products.image,
            order_items.quantity,
            order_items.price
        FROM order_items
        JOIN products
        ON order_items.product_id = products.id
        WHERE order_items.order_id=%s
    """, (order_id,))

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("order_details.html", items=items)

@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/products")
def admin_products():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
SELECT
    products.*,
    categories.category_name
FROM products
JOIN categories
ON products.category_id = categories.id
""")
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_products.html", products=products)
@app.route("/admin/add_product", methods=["GET", "POST"])
def add_product():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Categories fetch
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    if request.method == "POST":

        category_id = request.form["category_id"]
        name = request.form["name"]
        price = request.form["price"]
        stock = request.form["stock"]

        image = request.files["image"]
        filename = secure_filename(image.filename)

        if filename:
            image.save(os.path.join("static", "images", filename))

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products(product_name, category_id, description, price, stock, image)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, category_id, "", price, stock, filename))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("admin_products"))

    cursor.close()
    conn.close()

    return render_template("add_product.html", categories=categories)

@app.route("/admin/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        category_id = request.form["category_id"]
        name = request.form["name"]
        price = request.form["price"]
        stock = request.form["stock"]

        cursor.execute("""
            UPDATE products
            SET product_name=%s,
                category_id=%s,
                price=%s,
                stock=%s
            WHERE id=%s
        """, (name, category_id, price, stock, id))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("admin_products"))

    cursor.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()

    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "edit_product.html",
        product=product,
        categories=categories
    )

@app.route("/admin/orders")
def admin_orders():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    print("Reading orders from database...")

    cursor.execute("""
SELECT
    orders.id,
    users.full_name,
    orders.total_amount AS total,
    orders.order_status AS status,
    orders.order_date
FROM orders
JOIN users
ON orders.user_id = users.id
ORDER BY orders.id DESC
""")

    orders = cursor.fetchall()

    print(orders)

    cursor.close()
    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/update_order/<int:id>", methods=["POST"])
def update_order(id):

    print("Update route called")

    status = request.form["status"]
    print("Status =", status)
    print("Order ID =", id)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET order_status = %s
        WHERE id = %s
    """, (status, id))

    conn.commit()
    print(cursor.rowcount)

    cursor.close()
    conn.close()

    return redirect(url_for("admin_orders"))

@app.route("/admin/delete_product/<int:id>")
def delete_product(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("admin_products"))

@app.route("/add_to_wishlist/<int:product_id>")
def add_to_wishlist(product_id):

    user_id = session.get("user_id")

    if not user_id:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM wishlist WHERE user_id=%s AND product_id=%s",
        (user_id, product_id)
    )

    item = cursor.fetchone()

    if not item:
        cursor.execute(
            "INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)",
            (user_id, product_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(f"/product/{product_id}")

if __name__ == "__main__":
    app.run(debug=True)