import pytz
import hashlib
from functools import wraps
from datetime import datetime
from flask import *
from flask_bootstrap import Bootstrap
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient

app = Flask(__name__)
app.config["SECRET_KEY"] = "APP_SECRET_KEY"
Bootstrap(app)
client = FaunaClient(secret="your-secret-here")


def encrypt_password(password):
    return hashlib.sha512(password.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        try:
            user = client.query(
                q.get(q.match(q.index("users_index"), username)))
            flash("The account you are trying to create already exists!", "danger")
        except:
            user = client.query(q.create(q.collection("users"), {
                "data": {
                    "username": username,
                    "password": encrypt_password(password),
                    "date": datetime.now(pytz.UTC)
                }
            }))
            flash(
                "You have successfully created your account, you can proceed to login!", "success")
        return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/login/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        try:
            user = client.query(
                q.get(q.match(q.index("users_index"), username)))
            if encrypt_password(password) == user["data"]["password"]:
                session["user"] = {
                    "id": user["ref"].id(),
                    "username": user["data"]["username"]
                }
                return redirect(url_for("dashboard"))
            else:
                raise Exception()
        except:
            flash(
                "You have supplied invalid login credentials, please try again!", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/dashboard/")
@login_required
def dashboard():
    username = session["user"]["username"]
    queries = [
        q.count(q.paginate(
            q.match(q.index("questions_index"), True, username), size=100_000)),
        q.count(q.paginate(
            q.match(q.index("questions_index"), False, username), size=100_000))
    ]
    answered_questions, unanswered_questions = client.query(queries)

    return render_template("dashboard.html", answered_questions=answered_questions["data"][0], unanswered_questions=unanswered_questions["data"][0])


@app.route("/dashboard/questions/")
@login_required
def questions():
    return render_template("questions.html")


@app.route("/dashboard/questions/<string:question_id>/")
@login_required
def reply_question(question_id):
    return render_template("reply-question.html")


@app.route("/u/<string:user_id>/")
def view_profile(user_id):
    return render_template("view-profile.html")


@app.route("/u/<string:user_id>/ask/")
def ask_question(user_id):
    return render_template("questions.html")


if __name__ == "__main__":
    app.run(debug=True)
