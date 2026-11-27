from flask import Flask, render_template, request, redirect, url_for, session,flash
from datetime import date, timedelta
from database import init_db, query, execute

app = Flask(__name__)
app.secret_key = "medicine_stock_secret"

init_db()

# =========================
# LOGIN REQUIRED DECORATOR
# =========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "username" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "username" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":

            session["username"] = username

            flash("Login successful!")

            return redirect(url_for("dashboard"))

        else:
            flash("Invalid username or password!")

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.pop("username", None)

    flash("You have been logged out.")

    return redirect(url_for("login"))

# =========================
# DASHBOARD
# =========================

@app.route("/")
def dashboard():

    stats = query("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(quantity), 0) AS units,
            COUNT(*) FILTER (WHERE quantity <= 10) AS low_stock,
            COUNT(*) FILTER (WHERE expiry_date < CURRENT_DATE) AS expired,
            COUNT(*) FILTER (
                WHERE expiry_date BETWEEN CURRENT_DATE
                AND CURRENT_DATE + INTERVAL '30 days'
            ) AS near_expiry
        FROM medicines
    """)
    stats = stats[0]
    recent = query("""
        SELECT * FROM medicines
        ORDER BY id DESC
        LIMIT 5
    """)

    alerts = query("""
        SELECT * FROM medicines
        WHERE quantity <= 10
        OR expiry_date <= CURRENT_DATE + INTERVAL '30 days'
        ORDER BY expiry_date
        LIMIT 5
    """)
    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent,
        alerts=alerts,
        today=date.today()
    )

# =========================
# MEDICINES
# =========================
@app.route("/medicines")
def medicines():

    search = request.args.get("q", "")
    if search:
        data = query("""
            SELECT * FROM medicines
            WHERE name ILIKE %s
            OR category ILIKE %s
            OR supplier ILIKE %s
            ORDER BY id DESC
    """, (
        "%"+ search + "%",
        "%" + search + "%",
        "%" + search + "%"
    ))
    else:
      data =query("""
        select * from medicines
        order by id DESC
    """)
    return render_template(
        "medicines.html",
        medicines=data,
        search=search,
        today=date.today(),
        timedelta=timedelta
    )


@app.route("/add", methods=["GET", "POST"])
def add_medicine():

    if request.method == "POST":

        name = request.form["name"].strip()
        category = request.form["category"]
        quantity = request.form["quantity"]
        price = request.form["price"]
        expiry = request.form["expiry_date"]
        supplier = request.form["supplier"]

        try:

            if not name:
                raise ValueError

            if int(quantity) < 0 or float(price) < 0:
                raise ValueError

            execute("""
                INSERT INTO medicines
                (name, category, quantity, price, expiry_date, supplier)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                name, category, quantity,
                price, expiry, supplier
            ))

            flash("Medicine added successfully!")
            return redirect(url_for("medicines"))

        except ValueError:
            flash("Please enter valid medicine details.")

    return render_template("medicine_form.html", medicine=None)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_medicine(id):

    medicine = query(
        "SELECT * FROM medicines WHERE id=%s",
        (id,)
    )

    if not medicine:
        flash("Medicine not found.")
        return redirect(url_for("medicines"))

    medicine = medicine[0]

    if request.method == "POST":

        try:

            name = request.form["name"].strip()
            category = request.form["category"]
            quantity = int(request.form["quantity"])
            price = float(request.form["price"])
            expiry = request.form["expiry_date"]
            supplier = request.form["supplier"]

            if not name or quantity < 0 or price < 0:
                raise ValueError

            execute("""
                UPDATE medicines
                SET name=%s, category=%s, quantity=%s,
                price=%s, expiry_date=%s, supplier=%s
                WHERE id=%s
            """, (
                name, category, quantity,
                price, expiry, supplier, id
            ))

            flash("Medicine updated successfully!")
            return redirect(url_for("medicines"))

        except ValueError:
            flash("Please enter valid details.")

    return render_template(
        "medicine_form.html",
        medicine=medicine
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete_medicine(id):

    execute(
        "DELETE FROM medicines WHERE id=%s",
        (id,)
    )

    flash("Medicine deleted successfully!")
    return redirect(url_for("medicines"))


@app.route("/stock/<int:id>", methods=["POST"])
def update_stock(id):

    action = request.form["action"]
    amount = int(request.form["amount"])

    if amount <= 0:
        flash("Quantity must be greater than zero.")
        return redirect(url_for("medicines"))

    if action == "in":

        execute("""
            UPDATE medicines
            SET quantity=quantity+%s
            WHERE id=%s
        """, (amount, id))

    elif action == "out":

        execute("""
            UPDATE medicines
            SET quantity=GREATEST(quantity-%s, 0)
            WHERE id=%s
        """, (amount, id))

    flash("Stock updated successfully!")
    return redirect(url_for("medicines"))


# =========================
# SUPPLIERS
# =========================
@app.route("/suppliers")
def suppliers():
    try:
       data = query("""
        SELECT supplier,
        COUNT(*) AS medicines,
        SUM(quantity) AS total_stock
        FROM medicines
        GROUP BY supplier
        ORDER BY supplier
        """)
    
       return render_template("suppliers.html", suppliers=data)
    except Exception as e:
        return f"suppliers page error:{e}"

# =========================
# REPORTS
# =========================
@app.route("/reports")
def reports():

    data = query("""
        SELECT category,
        COUNT(*) AS total,
        SUM(quantity) AS stock,
        SUM(quantity*price) AS value
        FROM medicines
        GROUP BY category
    """)

    total_value = query("""
        SELECT COALESCE(SUM(quantity*price), 0) AS value
        FROM medicines
    """)[0]["value"]

    return render_template(
        "reports.html",
        reports=data,
        total_value=total_value
    )
if __name__ == "__main__":
    app.run(debug=True)