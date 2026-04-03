from flask import Flask, request, session, redirect, render_template
from flask_socketio import SocketIO
import json, os

app = Flask(__name__)
app.secret_key="secret"
socketio = SocketIO(app, cors_allowed_origins="*")

DATA="data/"

def load(f):
    try: return json.load(open(DATA+f))
    except: return {}

def save(f,d):
    json.dump(d, open(DATA+f,"w"), indent=2)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["user"]
        p=request.form["pass"]

        users=load("users.json")

        if u in users and users[u]["password"]==p:
            session["user"]=u
            return redirect("/")

    return render_template("login.html")

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/log", methods=["POST"])
def log():
    socketio.emit("log", request.json)
    return "ok"

def run():
    port=int(os.getenv("PORT",8080))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
