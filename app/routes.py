import os
from app import application, classes, db
from flask import redirect, render_template, url_for, request
from flask_login import current_user, login_user, login_required, logout_user
from plaid.errors import ItemError
from plaid_methods.methods import get_accounts, get_transactions, \
    token_exchange
from plaid import Client
import twilio
import twilio.rest
from twilio import twiml
from twilio.twiml.messaging_response import MessagingResponse


ENV_VARS = {
    "PLAID_CLIENT_ID": os.environ["PLAID_CLIENT_ID"],
    "PLAID_PUBLIC_KEY": os.environ["PLAID_PUBLIC_KEY"],
    "PLAID_SECRET": os.environ["PLAID_SECRET"],
    "PLAID_ENV": os.environ["PLAID_ENV"],
    "TWILIO_ACCOUNT_SID": os.environ["TWILIO_ACCOUNT_SID"],
    "TWILIO_AUTH_TOKEN": os.environ["TWILIO_AUTH_TOKEN"]
}

# setup plaid client
client = Client(
    ENV_VARS["PLAID_CLIENT_ID"],
    ENV_VARS["PLAID_SECRET"],
    ENV_VARS["PLAID_PUBLIC_KEY"],
    ENV_VARS["PLAID_ENV"],
)

# setup twilio client
twilio_client = twilio.rest.Client(
    ENV_VARS["TWILIO_ACCOUNT_SID"],
    ENV_VARS["TWILIO_AUTH_TOKEN"])


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


@application.route("/dashboard", methods=["POST", "GET"])
@login_required
def dashboard():
    # default transactions
    transactions = ''

    # get user session
    user_id = current_user.id

    # check if signed up in plaid
    plaid_dict = classes.PlaidItems.query.filter_by(
        user_id=user_id).first()

    if plaid_dict:  # if signed up in plaid
        print('dashboard: already signed up plaid')
        item_id = plaid_dict.item_id
        access_token = plaid_dict.access_token

        # get transaction data
        transactions = get_transactions(client, '2019-10-01', '2019-11-01',
                                        access_token)

    # get user session
    user_id = current_user.id

    habit_form = classes.HabitForm()
    print(habit_form.validate_on_submit())
    if habit_form.validate_on_submit():
        print('a')
        habit_name = habit_form.habit_name.data
        habit_category = habit_form.habit_category.data
        time_minute = habit_form.time_minute.data
        time_hour = habit_form.time_hour.data
        time_day_of_week = habit_form.time_day_of_week.data
        habit = classes.Habits(user_id, habit_name, habit_category,
                               time_minute, time_hour, time_day_of_week)
        db.session.add(habit)
        db.session.commit()
        return redirect(url_for("dashboard"))

    # find user habit
    habits = classes.Habits.query.filter_by(user_id=user_id).all()

    return render_template("dashboard.html",
                           user=current_user,
                           transactions=transactions,
                           habits=habits,
                           form=habit_form,
                           plaid_public_key=client.public_key,
                           plaid_environment=client.environment,
                           plaid_products=ENV_VARS.get("PLAID_PRODUCTS",
                                                       "transactions"),
                           plaid_country_codes=ENV_VARS.
                           get("PLAID_COUNTRY_CODES", "US")
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
        plaid_dict = classes.PlaidItems.query.\
            filter_by(user_id=user_id).first()
        if plaid_dict:  # if signed up in plaid
            print('access_plaid_token: already signed up plaid')
            item_id = plaid_dict.item_id
            access_token = plaid_dict.access_token

        else:  # if haven't signed up in plaid
            # get the plaid token response
            public_token = request.form["public_token"]
            response = token_exchange(client, public_token)
            item_id = response['item_id']
            access_token = response['access_token']

            # add plaid items
            plaid = classes.PlaidItems(user_id=user_id, item_id=item_id,
                                       access_token=access_token)
            db.session.add(plaid)
            db.session.commit()

    except ItemError as e:
        outstring = f"Failure: {e.code}"
        print(outstring)
        return outstring

    return redirect(url_for("dashboard"))

@application.route("/send_message", methods=['GET', 'POST'])
def send_message():
    twilio_number="+16462573594"
    customer_number="+14158192258"
    body="Would you like to save $5 today, please respond Y/N :)"
    
    msg = twilio_client.messages.create(
        body=body,
        to=customer_number,
        from_=twilio_number)
    return redirect(url_for("index"))

@application.route("/incoming", methods=["POST"])
def receive_message():
    number = request.form['From']
    response = request.form['Body']

    resp = MessagingResponse()
    resp.message(f"Hi, {number} Thanks for you response {response}")
    return str(resp)

@application.route("/yes", methods=["POST"])
def yes():
    pass

@application.route("/no", methods=["POST"])
def no():
    pass

