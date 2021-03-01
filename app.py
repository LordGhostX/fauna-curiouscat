from flask import *
from flask_bootstrap import Bootstrap

app = Flask(__name__)
Bootstrap(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register/")
def register():
    return render_template("register.html")


@app.route("/login/")
def login():
    return render_template("login.html")


@app.route("/dashboard/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/dashboard/questions/")
def questions():
    return render_template("questions.html")


if __name__ == "__main__":
    app.run(debug=True)
