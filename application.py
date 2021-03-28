import os
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# db = SQL("sqlite:///finance.db")
db = SQL(os.getenv("DATABASE_URL"))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    id_number = session["user_id"]

    symbols = db.execute("SELECT symbol FROM portfolios WHERE user = ?", id_number)
    shares = db.execute("SELECT total_shares FROM portfolios WHERE user = ?", id_number)

    portfolio = []
    value = 0

    for i in range(0, len(symbols)):

        dictionary = lookup(symbols[i]["symbol"])
        dictionary["symbol"] = symbols[i]["symbol"]
        dictionary["shares"] = shares[i]["total_shares"]

        TOTAL = (shares[i]["total_shares"]) * (dictionary["price"])
        dictionary["TOTAL"] = TOTAL

        value = value + TOTAL

        portfolio.append(dictionary)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", id_number)[0]["cash"]

    all_money = cash + value

    return render_template("index.html", portfolio = portfolio, cash = cash, all_money = all_money)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        else:
            symbol = request.form.get("symbol")

            if lookup(symbol) == None:
                return apology("invalid symbol", 400)

        if not request.form.get("shares"):
            return apology("must input number of shares", 400)

        elif int(request.form.get("shares")) <= 0:
            return apology("must enter a positive integer", 400)

        shares = int(request.form.get("shares"))

        dictionary = lookup(symbol)

        stock_price = dictionary["price"]
        stock_name = dictionary["name"]
        cash_dict = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        cash = cash_dict[0]["cash"]
        cost = shares * stock_price

        if cost > cash:
            return apology("not enough cash to buy shares", 400)

        else:
            id_number = session["user_id"]
            cash = cash - cost
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, id_number)
            db.execute("INSERT INTO transactions (user_id, symbol, shares, past_price, total_cost) VALUES (?, ?, ?, ?, ?)", id_number, symbol, shares, stock_price, cost)

            stock = db.execute("SELECT * FROM portfolios WHERE (user = ?) AND (symbol = ?)", id_number, symbol)

            if len(stock) == 0:
                db.execute("INSERT INTO portfolios (user, symbol, total_shares) VALUES (?, ?, ?)", id_number, symbol, shares)

            else:
                balance = stock[0]["total_shares"] + shares

                if balance == 0:
                    db.execute("DELETE FROM portfolios WHERE (symbol = ?) AND (user = ?)", symbol, id_number)
                else:
                    db.execute("UPDATE portfolios SET total_shares = ? WHERE (user = ?) AND (symbol = ?)", balance, id_number, symbol)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    id_number = session["user_id"]

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", id_number)

    return render_template("history.html", transactions = transactions)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        else:
            symbol = request.form.get("symbol")

            if lookup(symbol) == None:
                return apology("invalid symbol", 400)

            else:
                dictionary = lookup(symbol)
                comp_name = dictionary["name"]
                cost = dictionary["price"]

                return render_template("lookup.html", stock_name = comp_name, stock_price = cost, stock_symbol = symbol)

        # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        if not request.form.get("confirmation"):
            return apology("must provide repeat password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        if request.form.get("password").isalpha() or request.form.get("password").isnumeric():
            return apology("password must contain both letters and numbers", 400)


        # Query database for username
        check = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(check) != 0:
            return apology("username taken", 400)

        hashed_pw = generate_password_hash(request.form.get("password"))

        # Query database for username
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), hashed_pw)

        return render_template("registered.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    id_number = session["user_id"]

    symbols = db.execute("SELECT symbol FROM portfolios WHERE user = ?", id_number)
    stocks_list = []

    for i in range(0, len(symbols)):
        stocks_list.append(symbols[i]["symbol"])

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        if not request.form.get("shares"):
            return apology("must input number of shares", 400)

        elif int(request.form.get("shares")) <= 0:
            return apology("must enter a positive integer", 400)

        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        dictionary = lookup(symbol)

        stock_price = dictionary["price"]
        stock_name = dictionary["name"]
        cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        salvage = shares * stock_price

        total_shares = db.execute("SELECT total_shares FROM portfolios WHERE (user = ?) AND (symbol = ?)", id_number, symbol)[0]["total_shares"]

        if shares > total_shares:
            return apology("not enough shares to sell", 400)

        else:
            cash = cash + salvage
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, id_number)

            shares = shares * (-1)

            db.execute("INSERT INTO transactions (user_id, symbol, shares, past_price, total_cost) VALUES (?, ?, ?, ?, ?)", id_number, symbol, shares, stock_price, salvage)

            stock = db.execute("SELECT * FROM portfolios WHERE (user = ?) AND (symbol = ?)", id_number, symbol)

            if len(stock) == 0:
                return apology("no such shares owned", 400)

            else:
                balance = stock[0]["total_shares"] + shares

                if balance == 0:
                    db.execute("DELETE FROM portfolios WHERE (symbol = ?) AND (user = ?)", symbol, id_number)
                elif balance < 0:
                    db.execute("DELETE FROM portfolios WHERE (symbol = ?) AND (user = ?)", symbol, id_number)
                    return apology("something is wrong", 400)
                else:
                    db.execute("UPDATE portfolios SET total_shares = ? WHERE (user = ?) AND (symbol = ?)", balance, id_number, symbol)

        return redirect("/")

    else:
        return render_template("sell.html", stocks = stocks_list)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():

    id_number = session["user_id"]

    current_username = db.execute("SELECT username FROM users WHERE id = ?", id_number)[0]["username"]

    if request.method == "POST":

        # Ensure password was submitted
        if not request.form.get("old_password"):
            return apology("must old provide password", 405)

        if not request.form.get("new_password"):
            return apology("must provide new password", 405)

        if not request.form.get("repeat_new_password"):
            return apology("must provide repeat new password", 405)

        elif request.form.get("new_password") != request.form.get("repeat_new_password"):
            return apology("new passwords do not match", 405)

        if request.form.get("new_password").isalpha() or request.form.get("new_password").isnumeric():
            return apology("password must contain both letters and numbers", 405)

        hashed_pw = generate_password_hash(request.form.get("new_password"))

        # change password
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hashed_pw, id_number)

        return render_template("changed.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("account.html", current_username = current_username)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
