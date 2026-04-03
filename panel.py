from flask import Flask, request, session, redirect, render_template, jsonify
from flask_socketio import SocketIO
import json, os, hashlib, requests

app = Flask(__name__)
app.secret_key = os.getenv("PANEL_SECRET", "super-secret-key")

socketio = SocketIO(app, cors_allowed_origins="*")

DATA = "data/"

# ===== UTILS =====
def load(f):
    try:
        return json.load(open(DATA + f))
    except:
        return {}

def save(f, d):
    json.dump(d, open(DATA + f, "w"), indent=2)

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ===== AUTO CREATE ADMIN =====
def ensure_admin():
    users = load("users.json")

    if "admin" not in users:
        users["admin"] = {
            "password": hash_pass("admin123")
        }
        save("users.json", users)
        print("⚠️ Admin created: admin / admin123")

# ===== AUTH =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("user")
        p = request.form.get("pass")

        users = load("users.json")

        if u in users and users[u]["password"] == hash_pass(p):
            session["user"] = u
            return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def require_login():
    return "user" in session


# ===== DASHBOARD =====
@app.route("/")
def home():
    if not require_login():
        return redirect("/login")

    stats = load("users_stats.json")
    groups = load("groups.json")
    rep = load("rep.json")

    return render_template(
        "dashboard.html",
        stats=stats,
        groups=groups,
        rep=rep
    )

# ===== API =====
@app.route("/api/stats")
def api_stats():
    return jsonify(load("users_stats.json"))

@app.route("/api/groups")
def api_groups():
    return jsonify(load("groups.json"))

@app.route("/api/rep")
def api_rep():
    return jsonify(load("rep.json"))
@app.route("/lock")
def lock():
    g = load("groups.json")
    for gid in g:
        g[gid]["lock"] = True
    save("groups.json", g)
    return "OK"

@app.route("/unlock")
def unlock():
    g = load("groups.json")
    for gid in g:
        g[gid]["lock"] = False
    save("groups.json", g)
    return "OK"

@app.route("/setpost", methods=["POST"])
def setpost():
    text = request.form.get("text")
    delay = int(request.form.get("delay",60))

    t = load("post_template.json")
    for gid in load("groups.json"):
        t[gid] = {"text":text,"delay":delay}

    save("post_template.json", t)
    return "OK"
    
# ===== CONTROL =====
@app.route("/api/lock", methods=["POST"])
def lock_group():
    data = request.json
    gid = str(data.get("gid"))

    g = load("groups.json")

    if gid in g:
        g[gid]["lock"] = not g[gid].get("lock", False)
        save("groups.json", g)

    return jsonify({"status": "ok"})

# ===== BAN USER REAL =====
@app.route("/api/ban", methods=["POST"])
def ban_user():
    data = request.json
    uid = data.get("uid")
    gid = data.get("gid")

    token = os.getenv("BOT_TOKEN")

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/banChatMember",
            json={"chat_id": gid, "user_id": uid}
        )
    except:
        pass

    return jsonify({"status": "banned"})

# ===== REALTIME LOG =====
@app.route("/log", methods=["POST"])
def log():
    socketio.emit("log", request.json)
    return "ok"

# ===== RUN =====
def run():
    ensure_admin()

    port = int(os.getenv("PORT", 8080))
    print(f"🌐 PANEL running on {port}")

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True
    )
