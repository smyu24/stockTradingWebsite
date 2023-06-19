import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
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
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    table_user = db.execute("SELECT * FROM users WHERE id=:id", id=session["user_id"])
    table_total_stocks = db.execute("SELECT * FROM total_stocks WHERE id=:id", id=session["user_id"])
    total_stocks_quantity = db.execute("SELECT quantity FROM total_stocks WHERE id=:id", id=session["user_id"])
    current_price = []
    total_cash = 0
    prices = []
    total_stocks_stock = db.execute("SELECT stock FROM total_stocks WHERE id=:id", id=session["user_id"])
    for i in range(len(total_stocks_stock)):
        current_price = lookup(total_stocks_stock[i]["stock"])
        prices.append(current_price["price"])
        total_cash = current_price["price"] * total_stocks_quantity[i]["quantity"] + total_cash
    cash2 = table_user[0]["cash"]
    mult_total = []
    for i in range(len(prices)):
        mult_total.append(table_total_stocks[i]["quantity"] * prices[i])
    total_money = cash2 + total_cash #get the total cash in the account and add that to the amount, the total amount of stocks is worth
    return render_template("index.html", mult_total=mult_total, total_money=round(total_money, 2), prices=prices, cash=round(cash2, 2), table_user=table_user, table_total_stocks=table_total_stocks, current_price=current_price, index=index)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"): #if user didn't input a symbol
            return apology("Must Input a Symbol")
        elif not request.form.get("shares"): # if user didn't input a positive number of shares
            return apology("Must Input a amount")
        # find a way to exclude str
        if request.form.get("shares").isdigit() == False:
            return apology("Input a number")
        elif float(request.form.get("shares")) <= 0: # if amount of shares inputed is negative
            return apology("Input Amount of Shares Greater Than 0")
        elif float(request.form.get("shares")) != round(float(request.form.get("shares"))):
            return apology("Input A integer")
            #-----------------------
        sym_1 = lookup(request.form.get("symbol"))

        if sym_1 == None: #symbol brings back invalid
            return apology("Input Valid Symbol")

        cash_total = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"]) #total amount of cash that the person has
        total_cost = round(sym_1["price"], 2) * round(float(request.form.get("shares")), 2)
        if cash_total[0]["cash"] < total_cost: #if not enough cash
            return apology("Sorry not enough balance to make this transaction")

        #check if there has been previous activity with this symbol
        quantity_stock = db.execute("SELECT quantity FROM total_stocks WHERE stock=:stock AND id=:id", stock=sym_1["symbol"], id=session["user_id"])
        transaction = db.execute("INSERT INTO recites (id, stock, quantity, price, date) VALUES (:id, :stock, :quantity, :price, :date)", id=session["user_id"], stock=sym_1["symbol"], quantity=int(request.form.get("shares")), price=sym_1["price"], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        #if nothing went wrong take out the correct amount of money out
        take_cash = db.execute("UPDATE users SET cash=cash - :cost WHERE id=:id", cost=total_cost, id=session["user_id"])

        if len(quantity_stock) == 0: #if it is unique/new symbol
            db.execute("INSERT INTO total_stocks (id, stock, quantity) VALUES (:id, :stock, :quantity)", id=session["user_id"], stock=sym_1["symbol"], quantity=int(request.form.get("shares")))
        else: #the symbol has been bought before
            db.execute("UPDATE total_stocks SET quantity=quantity + :quantity WHERE stock=:stock AND id=:id", quantity=int(request.form.get("shares")), stock=sym_1["symbol"], id=session["user_id"])
        return redirect("/") #change to index
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    table_user = db.execute("SELECT username FROM users WHERE id=:id", id=session["user_id"])
    table_recites = db.execute("SELECT * FROM recites WHERE id=:id", id=session["user_id"])

    return render_template("history.html", table_user=table_user, table_recites=table_recites, index=index)



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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
        sym = request.form.get("symbol")

        if not request.form.get("symbol"): #if they dont provide a symbol
            return apology("Must Provide Stock")
        quote = []
        quote = lookup(sym) #looking up symbol

        if quote == None:
            return apology("Input Correct Symbol")

        return render_template("quoted.html", quote=quote) #send the information to quoted.html

    else: #if they are using "GET"
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"): #if username isn't provided
            return apology("Must Input A Username")
        elif not request.form.get("password"):
            return apology("Must Provide Password")
        elif not request.form.get("confirmation"): #if password comfirmation isn't provided
            return apology("Must Provide Password Confirmation")
        elif request.form.get("password") != request.form.get("confirmation"): #password and confirmation must match
            return apology("Passwords Must Match")

        #hash user's password
        hash = generate_password_hash(request.form.get("password"))
        user_name = request.form.get("username")
        #add user into database if they pass all restrictions
        U = db.execute("SELECT username FROM users WHERE username=:username", username=user_name)

        if len(U) != 0:
            return apology("Username is already in use")

        data = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=user_name, hash=hash)

        session["user_id"] = data

        # redirect the user
        return redirect("/")#later change to index.html
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Enter a Symbol")
        elif not request.form.get("shares"):
            return apology("Enter amount to sell")
        check = db.execute("SELECT stock, quantity FROM total_stocks WHERE id=:id AND stock=:stock", id=session["user_id"], stock=request.form.get("symbol"))
        if not check:
            return apology("You do not own this stock")
        elif int(request.form.get("shares")) > check[0]["quantity"]:
            return apology("Exceeds number of shares you have")
        #-----------------------------------------------------------
        sym_1 = lookup(request.form.get("symbol"))
        db.execute("INSERT INTO recites VALUES (:id, :stock, -:quantity, :price, :date)", id=session["user_id"], stock=sym_1["symbol"], quantity=int(request.form.get("shares")), price=sym_1["price"], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        db.execute("UPDATE total_stocks SET quantity=quantity - :quantity WHERE stock=:stock AND id=:id", quantity=int(request.form.get("shares")), stock=sym_1["symbol"], id=session["user_id"])
        empty_total = db.execute("SELECT quantity FROM total_stocks WHERE stock=:stock AND id=:id", stock=sym_1["symbol"], id=session["user_id"])
        if empty_total[0]["quantity"] == 0: #update it so that the stock is gone(deleted)
            db.execute("DELETE FROM total_stocks WHERE id=:id AND stock=:stock", id=session["user_id"], stock=sym_1["symbol"])
        #sell and add to money next
        db.execute("UPDATE users SET cash=:sym_1*:quantity+cash WHERE id=:id", sym_1=sym_1["price"], quantity=int(request.form.get("shares")), id=session["user_id"])
        return redirect("/")
    else:
        stocks = db.execute("SELECT stock FROM total_stocks WHERE id=:id", id=session["user_id"])
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
