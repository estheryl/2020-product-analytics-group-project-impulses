from app import application, classes, db
from flask import redirect, render_template, url_for, request
from flask_login import current_user, login_user, login_required, logout_user
from plaid.errors import ItemError
from plaid_methods.methods import get_accounts, get_transactions, token_exchange

import config
from app.classes import *


@application.route("/index")
@application.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@application.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    login_form = classes.LogInForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        user = classes.User.query.filter_by(email=email).first()
        if user is not None and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        else:
            return "Not a valid user"
    return render_template("login.html", form=login_form)


@application.route("/register", methods=["POST", "GET"])
def register():
    registration_form = classes.RegistrationForm()
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if registration_form.validate_on_submit():
        first_name = registration_form.first_name.data
        last_name = registration_form.last_name.data
        email = registration_form.email.data
        phone = registration_form.phone.data
        password = registration_form.password.data

        # Make sure email and phone number are unique
        user_count = (classes.User.query.filter_by(email=email).count(
        ) + classes.User.query.filter_by(phone=phone).count())

        # User information does not already exist in DB
        if user_count == 0:
            user = classes.User(first_name, last_name, email, phone, password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for("login"))
    return render_template("register.html", form=registration_form)


@application.route("/dashboard")
@login_required
def dashboard():
    # default transactions
    transactions = 'no transaction data'

    # get user session
    user_id = current_user.id

    # check if signed up in plaid
    plaid_obj = PlaidItems.query.filter_by(user_id=user_id)
    plaid_dict = plaid_obj.first()
    if plaid_dict:  # if signed up in plaid
        print('dashboard: already signed up plaid')
        item_id = plaid_dict.item_id
        access_token = plaid_dict.access_token
        print('dashboard: item_id: ', item_id)
        print('dashboard: access_token: ', access_token)

        # get transaction data
        transactions = get_transactions(config.client, '2019-10-01', '2019-11-01', access_token)

    return render_template("dashboard.html",
                           user=current_user,
                           transactions=transactions,
                           plaid_public_key=config.client.public_key,
                           plaid_environment=config.client.environment,
                           plaid_products=config.ENV_VARS.get("PLAID_PRODUCTS", "transactions"),
                           plaid_country_codes=config.ENV_VARS.get("PLAID_COUNTRY_CODES", "US")
                           )


@application.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@application.route("/access_plaid_token", methods=["POST"])
def access_plaid_token():
    try:
        # get user session
        user_id = current_user.id

        # check if signed up in plaid
        plaid_obj = PlaidItems.query.filter_by(user_id=user_id)
        plaid_dict = plaid_obj.first()
        if plaid_dict:  # if signed up in plaid
            print('access_plaid_token: already signed up plaid')
            item_id = plaid_dict.item_id
            access_token = plaid_dict.access_token
            print('access_plaid_token: item_id: ', item_id)
            print('access_plaid_token: access_token: ', access_token)

        else:  # if haven't signed up in plaid
            # get the plaid token response
            public_token = request.form["public_token"]
            response = token_exchange(config.client, public_token)
            item_id = response['item_id']
            access_token = response['access_token']
            print('item_id: ', item_id)
            print('access_token: ', access_token)

            # add plaid items
            plaid = classes.PlaidItems(user_id=user_id, item_id=response['item_id'], access_token=response['access_token'])
            db.session.add(plaid)
            db.session.commit()

    except ItemError as e:
        outstring = f"Failure: {e.code}"
        print(outstring)
        return outstring

    return render_template("dashboard.html",
                           user=current_user,
                           plaid_public_key=config.client.public_key,
                           plaid_environment=config.client.environment,
                           plaid_products=config.ENV_VARS.get("PLAID_PRODUCTS", "transactions"),
                           plaid_country_codes=config.ENV_VARS.get("PLAID_COUNTRY_CODES", "US")
                           )

