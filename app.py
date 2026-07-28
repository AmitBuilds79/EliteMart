import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session
from config import get_db_connection
import mysql.connector
from flask_mail import Mail, Message
import razorpay
from flask import flash
from flask import abort
from flask_login import login_required, current_user
from config import ADMIN_EMAILpip 
from config import get_db_connection, ADMIN_EMAIL

app = Flask(__name__)
app.secret_key = "elite123"

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'roastmass79@gmail.com'
app.config['MAIL_PASSWORD'] = 'cynmylngzmszvrms'
app.config['MAIL_DEFAULT_SENDER'] = 'roastmass79@gmail.com'
app.config['MAIL_TIMEOUT'] = 10


mail = Mail(app)



client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)
print(app.config["MAIL_SERVER"])
print(app.config["MAIL_PORT"])
print(app.config["MAIL_USERNAME"])

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

@app.route("/buy_now/<int:product_id>")
def buy_now(product_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO cart (user_id, product_id, quantity)
        SELECT %s, %s, 1
        WHERE NOT EXISTS (
            SELECT 1 FROM cart
            WHERE user_id=%s AND product_id=%s
        )
    """, (session["user_id"], product_id, session["user_id"], product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("checkout"))

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
INSERT INTO reviews (product_id, user_name, rating, comment)
VALUES (%s, %s, %s, %s)
""", (product_id, username, rating, review))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(f"/product/{product_id}")

@app.route("/delete_review/<int:review_id>/<int:product_id>", methods=["POST"])
def delete_review(review_id, product_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM reviews WHERE id=%s",
        (review_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("product_details", product_id=product_id))

@app.route("/add_to_wishlist/<int:product_id>")
def add_to_wishlist(product_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM wishlist WHERE user_id=%s AND product_id=%s",
        (session["user_id"], product_id)
    )

    item = cursor.fetchone()

    if not item:
        cursor.execute(
            "INSERT INTO wishlist(user_id, product_id) VALUES(%s,%s)",
            (session["user_id"], product_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("product_details", product_id=product_id))

@app.route("/wishlist")
def wishlist():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT products.*
        FROM wishlist
        JOIN products
        ON wishlist.product_id = products.id
        WHERE wishlist.user_id=%s
    """, (session["user_id"],))

    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("wishlist.html", products=products)

@app.route("/remove_from_wishlist/<int:product_id>")
def remove_from_wishlist(product_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM wishlist WHERE user_id=%s AND product_id=%s",
        (session["user_id"], product_id)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("wishlist"))

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

    # Product name + stock
    cursor.execute(
        "SELECT product_name, stock FROM products WHERE id=%s",
        (product_id,)
    )
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        flash("Product not found!", "danger")
        return redirect(url_for("home"))

    if product["stock"] <= 0:
        cursor.close()
        conn.close()
        flash(f"{product['product_name']} is Out of Stock!", "danger")
        return redirect(url_for("home"))

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

    flash(f"✅ {product['product_name']} has been added to your cart successfully!", "success")
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

    cursor.execute(
        "SELECT id FROM users WHERE full_name=%s",
        (session["user"],)
    )
    user = cursor.fetchone()

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

    total = sum(item["price"] * item["quantity"] for item in cart_items)

    # Razorpay Order
    razorpay_order = client.order.create({
        "amount": int(total * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    if request.method == "POST":

        address = request.form["address"]
        payment = request.form["payment"]

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
        total=total,
        razorpay_order=razorpay_order,
        razorpay_key=os.getenv("RAZORPAY_KEY_ID")
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

def admin_required():
    if not current_user.is_authenticated:
        abort(401)

    if current_user.email != ADMIN_EMAIL:
        abort(403)

@app.route("/admin")
@login_required
def admin_dashboard():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    orders = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_amount) FROM orders")
    revenue = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        products=products,
        orders=orders,
        revenue=revenue
    )

@app.route("/admin/products")
@login_required
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

@app.route("/admin/users")
@login_required
def admin_users():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, full_name, email
        FROM users
        ORDER BY id DESC
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_users.html", users=users)

@app.route("/admin/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
    cursor.execute("DELETE FROM orders WHERE user_id=%s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/admin/users")

@app.route("/admin/add_product", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
def admin_orders():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    print("Reading orders from database...")

    cursor.execute("""
SELECT
    orders.id,
    users.full_name,
    orders.total_amount AS total,
    orders.status,
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
@login_required
def update_order(id):

    print("Update route called")

    status = request.form["status"]
    print("Status =", status)
    print("Order ID =", id)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = %s
        WHERE id = %s
    """, (status, id))

    conn.commit()
    print(cursor.rowcount)

    cursor.close()
    conn.close()

    return redirect(url_for("admin_orders"))

@app.route("/admin/delete_product/<int:id>")
@login_required
def delete_product(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("admin_products"))



if __name__ == "__main__":
    app.run(debug=True)