"""Python Flask WebApp Auth0 integration example
"""
from functools import wraps
import json
from os import environ as env
from werkzeug.exceptions import HTTPException

from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for
from flask import request
from authlib.flask.client import OAuth
from six.moves.urllib.parse import urlencode
import sqlalchemy as db

import constants

from plaid import Client
from plaid.errors import ItemError
from plaid_methods.methods import get_accounts, get_transactions, token_exchange

# Load ENV_FILE
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

# env.get
DB_PASSWORD = env.get(constants.DB_PASSWORD)
AUTH0_CALLBACK_URL = env.get(constants.AUTH0_CALLBACK_URL)
AUTH0_CLIENT_ID = env.get(constants.AUTH0_CLIENT_ID)
AUTH0_CLIENT_SECRET = env.get(constants.AUTH0_CLIENT_SECRET)
AUTH0_DOMAIN = env.get(constants.AUTH0_DOMAIN)
AUTH0_BASE_URL = 'https://' + AUTH0_DOMAIN
AUTH0_AUDIENCE = env.get(constants.AUTH0_AUDIENCE)
ENV_VARS = {
    "PLAID_CLIENT_ID": env.get(constants.PLAID_CLIENT_ID),
    "PLAID_PUBLIC_KEY": env.get(constants.PLAID_PUBLIC_KEY),
    "PLAID_SECRET": env.get(constants.PLAID_SECRET),
    "PLAID_ENV": env.get(constants.PLAID_ENV)
}


# setup plaid client
client = Client(
    ENV_VARS["PLAID_CLIENT_ID"],
    ENV_VARS["PLAID_SECRET"],
    ENV_VARS["PLAID_PUBLIC_KEY"],
    ENV_VARS["PLAID_ENV"],
)

# setup application
application = Flask(__name__, static_url_path='/public', static_folder='./public')
application.secret_key = constants.SECRET_KEY
application.debug = True


@application.errorhandler(Exception)
def handle_auth_error(ex: Exception) -> jsonify:
    """
    Handle authentication error
    :param ex: Exception
    :return: A json type of response
    """
    response = jsonify(message=str(ex))
    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


oauth = OAuth(application)

auth0 = oauth.register(
    'auth0',
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=AUTH0_BASE_URL,
    access_token_url=AUTH0_BASE_URL + '/oauth/token',
    authorize_url=AUTH0_BASE_URL + '/authorize',
    client_kwargs={
        'scope': 'openid profile email',
    },
)


def requires_auth(f):
    @wraps(f)
    def decorated(*args: str, **kwargs: int) -> f:
        """
        If PROFILE_KEY is not in session, redirect to login page
        If PROFILE_KEY is in session, return function f
        :param args: *args
        :param kwargs: *kwargs
        :return: function f(*args, **kwargs)
        """
        if constants.PROFILE_KEY not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated


# Controllers API
@application.route('/')
def home() -> render_template:
    """
    Render to home.html
    :return: render_template('home.html')
    """
    return render_template('home.html')


@application.route('/callback')
def callback_handling() -> redirect:
    """
    Handle Auth0's callback, and redirect to dashboard.html
    :return: function redirect('/dashboard')
    """
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    session[constants.JWT_PAYLOAD] = userinfo
    session[constants.PROFILE_KEY] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'picture': userinfo['picture']
    }
    return redirect('/dashboard')


@application.route('/login')
def login() -> auth0.authorize_redirect:
    """
    Redirect to Auth0's login page
    :return: method auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=AUTH0_AUDIENCE)
    """
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=AUTH0_AUDIENCE)


@application.route('/logout')
def logout() -> redirect:
    """
    Clear the session and redirect to home.html
    :return: function redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))
    """
    session.clear()
    params = {'returnTo': url_for('home', _external=True), 'client_id': AUTH0_CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))


@application.route('/dashboard')
@requires_auth
def dashboard() -> render_template:
    """
    Render to dashboard.html
    :return: function render_template('dashboard.html', userinfo, userinfo_pretty)
    """
    # connect to database
    engine = db.create_engine(
        "postgres+psycopg2://masteruser:" + DB_PASSWORD + "@maindb.cuwtgivgs05r.us-west-1.rds.amazonaws.com:5432/postgres")
    connection = engine.connect()

    # user info
    user_info = session[constants.PROFILE_KEY],
    user_info_pretty_str = json.dumps(session[constants.JWT_PAYLOAD], indent=4)
    user_info_pretty_dict = session[constants.JWT_PAYLOAD]

    # check if sign up
    signup_flag = False
    signup_obj = connection.execute("SELECT auth_id FROM dw.user WHERE auth_id = '" + user_info[0]['user_id'] + "'")
    if len(signup_obj.fetchall()) > 0:  # if there is something in the signup object
        print('signed up already')
        signup_flag = True

    # signup: insert user info to database
    if not signup_flag:
        connection.execute("insert into dw.user values (" +
                           "default, " +  # user_id
                           "'" + user_info[0]['user_id'] + "', " +  # auth_id
                           "'" + user_info_pretty_dict['given_name'] + "', " +  # first_name
                           "'" + user_info_pretty_dict['family_name'] + "', " +  # last_name
                           "'" + user_info_pretty_dict['email'] + "', " +  # email
                           "'4157678665', " +  # phone
                           "'01/01/2020', " +  # signup_date
                           "'Activate'" +  # status
                           ");")

    # get the user_id in dw.user
    user_id_obj = connection.execute(
        "SELECT user_id FROM dw.user WHERE auth_id = '" + user_info[0]['user_id'] + "'")
    user_id = str(user_id_obj.first()[0])

    # check if signed up in plaid
    signup_flag = False
    signup_obj = connection.execute(
        "SELECT access_token, item_id FROM dw.plaid_items WHERE user_id = " + user_id)
    signup_dict = signup_obj.fetchone()
    if len(signup_dict) > 0:  # if there is something in the signup object
        print('plaid signed up already')
        signup_flag = True
        access_token = signup_dict['access_token']
        item_id = signup_dict['item_id']
        print('dashboard access_token: ', access_token)
        print('dashboard item_id: ', item_id)

    # show the user's transactions
    show_transaction = connection.execute("SELECT * FROM dw.user")
    for row in show_transaction:
        print('transaction: ', row)

    # show user info
    return render_template('dashboard.html',
                           userinfo=user_info[0],
                           userinfo_pretty=user_info_pretty_str,
                           plaid_public_key=client.public_key,
                           plaid_environment=client.environment,
                           plaid_products=ENV_VARS.get("PLAID_PRODUCTS", "transactions"),
                           plaid_country_codes=ENV_VARS.get("PLAID_COUNTRY_CODES", "US"),
                           )


@application.route("/access_token", methods=["POST"])
def access_token():
    # connect to database
    engine = db.create_engine(
        "postgres+psycopg2://masteruser:" + DB_PASSWORD + "@maindb.cuwtgivgs05r.us-west-1.rds.amazonaws.com:5432/postgres")
    connection = engine.connect()

    # get the public token from form
    public_token = request.form["public_token"]

    try:
        # user info
        user_info = session[constants.PROFILE_KEY]
        user_info_pretty_str = json.dumps(session[constants.JWT_PAYLOAD], indent=4)

        # get the user_id in dw.user
        user_id_obj = connection.execute(
            "SELECT user_id FROM dw.user WHERE auth_id = '" + user_info['user_id'] + "'")
        user_id = str(user_id_obj.first()[0])

        # check if signed up in plaid
        signup_flag = False
        signup_obj = connection.execute(
            "SELECT access_token, item_id FROM dw.plaid_items WHERE user_id = " + user_id)
        signup_dict = signup_obj.fetchone()
        if len(signup_dict) > 0:  # if there is something in the signup object
            print('plaid signed up already')
            signup_flag = True
            access_token = signup_dict['access_token']
            item_id = signup_dict['item_id']
            print('access_token: ', access_token)
            print('item_id: ', item_id)

        # signup: insert plaid info to database
        if not signup_flag:
            # get the plaid token response
            response = token_exchange(client, public_token)
            print('response: ', response)

            connection.execute("insert into dw.plaid_items values (" +
                               "default, " +  # plaid_id
                               "'" + user_id + "', " +  # user_id
                               "'" + response['item_id'] + "', " +  # item_id
                               "'" + response['access_token'] + "'" +  # access_token
                               ");")

    except ItemError as e:
        outstring = f"Failure: {e.code}"
        print(outstring)
        return outstring

    # return redirect(url_for('dashboard'))
    return render_template('dashboard.html',
                           userinfo=user_info,
                           userinfo_pretty=user_info_pretty_str,
                           plaid_public_key=client.public_key,
                           plaid_environment=client.environment,
                           plaid_products=ENV_VARS.get("PLAID_PRODUCTS", "transactions"),
                           plaid_country_codes=ENV_VARS.get("PLAID_COUNTRY_CODES", "US"),
                           )


if __name__ == "__main__":
    # testing local
    # application.run(host='0.0.0.0', port=env.get('PORT', 3000))

    # deployment
    application.run(threaded=True, debug=True, port=5000)
