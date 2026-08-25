import os
import gc
import sqlite3
import pandas as pd
import joblib
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

# Import EstateIQ AI services
from services.vector_service import vector_service
from services.property_matching import calculate_match_score
from services.ai_agent import ai_agent


app = Flask(__name__)

# ============================================================
# FLASK CONFIGURATION
# ============================================================

app.secret_key = os.getenv("SECRET_KEY", "sania-house-price-secret-key")


# ============================================================
# BASE DIRECTORY & PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "models", "california_housing_model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.pkl")


# ============================================================
# LAZY-LOADED ML MODELS (Prevents Serverless Timeout)
# ============================================================

model = None
scaler = None

def get_ml_models():
    """Lazily load trained model and scaler on first request."""
    global model, scaler
    if model is None or scaler is None:
        try:
            model = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
            gc.collect()
        except Exception as e:
            print(f"[EstateIQ Error] Failed loading ML model/scaler: {e}")
            raise RuntimeError(f"Pickle load failed ({type(e).__name__}): {e}")
    return model, scaler


# ============================================================
# DATABASE SETUP (Use /tmp for Vercel Read-Only Filesystem)
# ============================================================

# Use writable /tmp directory on Vercel serverless environments
if os.environ.get("VERCEL"):
    DATABASE = "/tmp/users.db"
else:
    DATABASE = os.path.join(BASE_DIR, "users.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    try:
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[EstateIQ DB Init Warning]: {e}")


# Initialize SQLite Database inside writable space
init_database()

# Safe lazy-initialization check for Qdrant Vector Collection
try:
    data_csv_path = os.path.join(BASE_DIR, "data", "properties.csv")
    if os.path.exists(data_csv_path):
        vector_service.init_collection(data_csv_path)
except Exception as e:
    print(f"[EstateIQ Vector DB Warning] Could not connect or initialize Qdrant: {e}")


# ============================================================
# AUTH & USER ROUTES
# ============================================================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        username=session.get("username"),
        email=session.get("email")
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter email and password.", "error")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["name"]
            session["email"] = user["email"]
            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not password:
        flash("All fields are required.", "error")
        return redirect(url_for("login"))

    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for("login"))

    hashed_password = generate_password_hash(password)
    conn = get_db_connection()

    try:
        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password)
        )
        conn.commit()
        flash("Account created successfully. Please login.", "success")
    except sqlite3.IntegrityError:
        flash("An account with this email already exists.", "error")
    finally:
        conn.close()

    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ============================================================
# HOUSE PRICE PREDICTION
# ============================================================

@app.route("/predict", methods=["POST"])
def predict():
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        med_inc = float(request.form["MedInc"])
        house_age = float(request.form["HouseAge"])
        ave_rooms = float(request.form["AveRooms"])
        ave_bedrms = float(request.form["AveBedrms"])
        population = float(request.form["Population"])
        ave_occup = float(request.form["AveOccup"])
        latitude = float(request.form["Latitude"])
        longitude = float(request.form["Longitude"])

        if ave_occup <= 0 or ave_rooms <= 0:
            raise ValueError("Average occupants and rooms must be greater than 0.")

        rooms_per_household = ave_rooms / ave_occup
        bedrooms_per_room = ave_bedrms / ave_rooms

        # Raw 2D array matching the scaler's expected NumPy structure
        input_data = [[
            med_inc, house_age, ave_rooms, ave_bedrms,
            population, ave_occup, latitude, longitude,
            rooms_per_household, bedrooms_per_room
        ]]

        loaded_model, loaded_scaler = get_ml_models()
        if loaded_model is None or loaded_scaler is None:
            raise RuntimeError("Machine Learning models failed to load.")

        scaled_input = loaded_scaler.transform(input_data)
        prediction_val = loaded_model.predict(scaled_input)[0] * 100000

        if prediction_val >= 1_000_000:
            formatted_price = f"${prediction_val / 1_000_000:.2f} Million"
        else:
            formatted_price = f"${prediction_val:,.2f}"

        prediction_text = f"Estimated House Price: {formatted_price}"

        return render_template(
            "index.html",
            prediction_text=prediction_text,
            username=session.get("username"),
            email=session.get("email")
        )

    except (KeyError, ValueError) as e:
        return render_template(
            "index.html",
            prediction_text=f"Invalid or missing input: {e}",
            username=session.get("username"),
            email=session.get("email")
        )
    except Exception as e:
        print("Prediction Error:", e)
        return render_template(
            "index.html",
            prediction_text=f"Prediction Error Details: {e}",
            username=session.get("username"),
            email=session.get("email")
        )


# ============================================================
# ESTATEIQ AI — VECTOR SEARCH & PROPERTY ROUTES
# ============================================================

@app.route("/properties")
def properties_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "properties.html",
        username=session.get("username")
    )


@app.route("/search-properties", methods=["POST"])
def search_properties():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        query = data.get("query", "3BHK near metro with parking")
        max_price = data.get("max_price")
        bedrooms = data.get("bedrooms")

        filters = {
            "max_price": max_price if max_price else None,
            "bedrooms": bedrooms if bedrooms else None
        }

        results = vector_service.search_properties(query=query, limit=10, filters=filters)

        ranked_results = []
        for prop in results:
            analysis = calculate_match_score(prop, filters)
            prop.update(analysis)
            ranked_results.append(prop)

        ranked_results.sort(key=lambda x: x["match_score"], reverse=True)

        return jsonify({"status": "success", "properties": ranked_results})

    except Exception as e:
        print("Search Properties Error:", e)
        return jsonify({"status": "error", "message": "Failed to complete property search."}), 500


@app.route("/property/<int:property_id>")
def property_detail(property_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        records = vector_service.client.retrieve(
            collection_name="estateiq_properties",
            ids=[property_id]
        )

        if not records:
            flash("Property not found.", "error")
            return redirect(url_for("properties_page"))

        prop_data = records[0].payload

        analysis = calculate_match_score(prop_data, {})
        prop_data.update(analysis)

        similar = vector_service.get_similar_properties(property_id=property_id, limit=3)

        return render_template(
            "property_detail.html",
            property=prop_data,
            similar_properties=similar,
            username=session.get("username")
        )
    except Exception as e:
        print(f"[Property Detail Error]: {e}")
        flash("Error loading property details.", "error")
        return redirect(url_for("properties_page"))


@app.route("/similar-properties", methods=["POST"])
def similar_properties():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        prop_id = int(data.get("property_id", 0))

        if not prop_id:
            return jsonify({"status": "error", "message": "Invalid property ID"}), 400

        results = vector_service.get_similar_properties(property_id=prop_id, limit=3)
        return jsonify({"status": "success", "similar": results})

    except Exception as e:
        print("Similar Properties Error:", e)
        return jsonify({"status": "error", "message": "Could not fetch similar properties."}), 500


# ============================================================
# ESTATEIQ AI — CHAT ASSISTANT ROUTES
# ============================================================

@app.route("/assistant")
def assistant_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "assistant.html",
        username=session.get("username")
    )


@app.route("/ai-assistant", methods=["POST"])
def ai_assistant():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"response": "Please enter a valid request or query."})

        response_text = ai_agent.process_chat(user_message)
        return jsonify({"response": response_text})

    except Exception as e:
        print("AI Assistant Route Error:", e)
        return jsonify({"response": "Sorry, I ran into an error processing your request."}), 500


# ============================================================
# RUN FLASK APPLICATION
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        debug=False,
        host="0.0.0.0",
        port=port
    )