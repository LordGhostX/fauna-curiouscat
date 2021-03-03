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


def faunatimefilter(faunatime):
    return faunatime.to_datetime().strftime("%d/%m/%Y %H:%M UTC")


app.jinja_env.filters["faunatimefilter"] = faunatimefilter


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
                q.get(
                    q.match(q.index("users_index"), username)
                )
            )
            flash("The account you are trying to create already exists!", "danger")
        except:
            user = client.query(
                q.create(
                    q.collection("users"), {
                        "data": {
                            "username": username,
                            "password": encrypt_password(password),
                            "date": datetime.now(pytz.UTC)
                        }
                    }
                )
            )
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
                q.get(
                    q.match(q.index("users_index"), username)
                )
            )
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
        q.count(
            q.paginate(
                q.match(q.index("questions_index"), True, username),
                size=100_000
            )
        ),
        q.count(
            q.paginate(
                q.match(q.index("questions_index"), False, username),
                size=100_000
            )
        )
    ]
    answered_questions, unanswered_questions = client.query(queries)

    return render_template("dashboard.html", answered_questions=answered_questions["data"][0], unanswered_questions=unanswered_questions["data"][0])


@app.route("/dashboard/questions/")
@login_required
def questions():
    username = session["user"]["username"]
    question_type = request.args.get("type", "all").lower()

    if question_type == "answered":
        question_indexes = client.query(
            q.paginate(
                q.match(q.index("questions_index"), True, username),
                size=100_000
            )
        )
    elif question_type == "unanswered":
        question_indexes = client.query(
            q.paginate(
                q.match(q.index("questions_index"), False, username),
                size=100_000
            )
        )
    elif question_type == "all":
        question_indexes = client.query(
            q.paginate(
                q.union(
                    q.match(q.index("questions_index"), True, username),
                    q.match(q.index("questions_index"), False, username)
                ),
                size=100_000
            )
        )
    else:
        return redirect(url_for("questions"))

    questions = [
        q.get(
            q.ref(q.collection("questions"), i.id())
        ) for i in question_indexes["data"]
    ]
    return render_template("questions.html", questions=client.query(questions)[::-1])


@app.route("/dashboard/questions/<string:question_id>/", methods=["GET", "POST"])
@login_required
def reply_question(question_id):
    try:
        question = client.query(
            q.get(
                q.ref(q.collection("questions"), question_id)
            )
        )
        if question["data"]["user_asked"] != session["user"]["username"]:
            raise Exception()
    except:
        abort(404)

    if request.method == "POST":
        client.query(
            q.update(
                q.ref(q.collection("questions"), question_id), {
                    "data": {
                        "answer": request.form.get("reply").strip(),
                        "resolved": True
                    }
                }
            )
        )
        flash("You have successfully responded to this question!", "success")
        return redirect(url_for("reply_question", question_id=question_id))

    return render_template("reply-question.html", question=question)


@app.route("/u/<string:username>/")
def view_profile(username):
    try:
        user = client.query(
            q.get(
                q.match(q.index("users_index"), username)
            )
        )
    except:
        abort(404)

    question_indexes = client.query(
        q.paginate(
            q.match(q.index("questions_index"), True, username),
            size=100_000
        )
    )
    questions = [
        q.get(
            q.ref(q.collection("questions"), i.id())
        ) for i in question_indexes["data"]
    ]
    return render_template("view-profile.html", username=username, questions=client.query(questions)[::-1])


@app.route("/u/<string:username>/ask/", methods=["GET", "POST"])
def ask_question(username):
    try:
        user = client.query(
            q.get(
                q.match(q.index("users_index"), username)
            )
        )
    except:
        abort(404)

    if request.method == "POST":
        user_asking = request.form.get("user_asking", "").strip().lower()
        question_text = request.form.get("question").strip()

        question = client.query(
            q.create(
                q.collection("questions"), {
                    "data": {
                        "resolved": False,
                        "user_asked": username,
                        "question": question_text,
                        "user_asking": "anonymous" if user_asking == "" else user_asking,
                        "answer": "",
                        "date": datetime.now(pytz.UTC)
                    }
                }
            )
        )
        flash(f"You have successfully asked {username} a question!", "success")
        return redirect(url_for("ask_question", username=username))

    return render_template("ask-question.html", username=username)


@app.route("/q/<string:question_id>/")
def view_question(question_id):
    try:
        question = client.query(
            q.get(
                q.ref(q.collection("questions"), question_id)
            )
        )
    except:
        abort(404)

    return render_template("view-question.html", question=question)


if __name__ == "__main__":
    app.run(debug=True)
