import os
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, abort
from flask_cors import CORS

# Support both package and script execution
try:
    from backend.models import db, Expert, Availability, Booking
except Exception:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from models import db, Expert, Availability, Booking

import razorpay
import requests
import hashlib as _hashlib

app = Flask(__name__)
CORS(app)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

razor = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))


@app.get("/api/experts")
def list_experts():
    experts = Expert.query.all()
    return jsonify([{"id": e.id, "name": e.name, "specialty": e.specialty} for e in experts])


@app.get("/api/experts/<int:expert_id>/availability")
def expert_availability(expert_id):
    start = request.args.get("start")
    end = request.args.get("end")
    q = Availability.query.filter_by(expert_id=expert_id, is_booked=False)
    if start:
        q = q.filter(Availability.start_utc >= datetime.fromisoformat(start))
    if end:
        q = q.filter(Availability.end_utc <= datetime.fromisoformat(end))
    slots = q.order_by(Availability.start_utc.asc()).all()
    return jsonify([{"id": s.id, "start": s.start_utc.isoformat(), "end": s.end_utc.isoformat()} for s in slots])


@app.post("/api/bookings")
def create_booking():
    data = request.json or {}
    expert_id = data["expertId"]
    slot_id = data["slotId"]
    farmer_name = data["farmerName"]
    farmer_email = data["farmerEmail"]
    amount_inr = int(float(data["amountInr"]) * 100)  # paise
    commission_code = data.get("commissionCode")

    slot = Availability.query.filter_by(id=slot_id, expert_id=expert_id, is_booked=False).first()
    if not slot:
        abort(400, "Slot not available")

    order = razor.order.create({"amount": amount_inr, "currency": "INR"})
    booking = Booking(
        expert_id=expert_id,
        farmer_name=farmer_name,
        farmer_email=farmer_email,
        slot_start_utc=slot.start_utc,
        slot_end_utc=slot.end_utc,
        razorpay_order_id=order["id"],
        commission_code=commission_code,
    )
    db.session.add(booking)
    # lock slot tentatively
    slot.is_booked = True
    db.session.commit()
    return jsonify({"bookingId": booking.id, "razorpayOrderId": order["id"], "amount": order["amount"]})


@app.post("/api/payments/razorpay/webhook")
def razorpay_webhook():
    payload = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    expected = hmac.new(bytes(secret, "utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        return ("", 400)

    event = request.json or {}
    if event.get("event") == "payment.captured":
        order_id = event["payload"]["payment"]["entity"]["order_id"]
        payment_id = event["payload"]["payment"]["entity"]["id"]
        booking = Booking.query.filter_by(razorpay_order_id=order_id).first()
        if booking:
            booking.status = "paid"
            booking.razorpay_payment_id = payment_id
            db.session.commit()
            # TODO: enqueue emails and meeting creation here
    return ("", 200)


# ---------- Weather Advice Endpoint ----------

def _openweather_forecast(lat: float, lon: float):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return None, "OPENWEATHER_API_KEY not set"
    try:
        # 5 day / 3 hour forecast API, returns list with 'pop' (probability of precipitation)
        url = "https://api.openweathermap.org/data/2.5/forecast"
        r = requests.get(url, params={"lat": lat, "lon": lon, "appid": api_key}, timeout=10)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)


@app.get("/api/weather/advice")
def weather_advice():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except Exception:
        return jsonify({"error": "lat and lon are required as numbers"}), 400

    data, err = _openweather_forecast(lat, lon)
    if err:
        return jsonify({"error": err}), 400

    # Consider next 48 hours: first 16 entries (3h interval)
    lst = data.get("list", [])[:16]
    max_pop = 0.0
    for item in lst:
        pop = float(item.get("pop", 0.0))
        if pop > max_pop:
            max_pop = pop
    rain_risk = max_pop > 0.5
    advice = "Avoid spraying today due to rain risk." if rain_risk else "Spray now for best results."

    return jsonify({
        "lat": lat,
        "lon": lon,
        "maxPop": round(max_pop, 2),
        "rainRisk": rain_risk,
        "advice": advice,
        "source": "openweather_forecast_5day_3h",
        "threshold": 0.5,
    })


@app.post("/api/qr/verify")
def qr_verify():
    data = request.json or {}
    content = data.get("content", "")
    farmer_name = data.get("farmerName")
    farmer_email = data.get("farmerEmail")
    lat = data.get("lat")
    lon = data.get("lon")
    if not content:
        return jsonify({"error": "content is required"}), 400

    # Simulated authenticity check via hash whitelist/blacklist
    digest = _hashlib.sha256(content.encode("utf-8")).hexdigest()
    # For MVP: even-ending hex => genuine; odd-ending => warning (replace with real API later)
    is_genuine = int(digest[-1], 16) % 2 == 0
    result = "genuine" if is_genuine else "warning"

    # Persist scan
    try:
        from backend.models import QRScan
    except Exception:
        from models import QRScan
    scan = QRScan(content=content, sha256=digest, result=result,
                  farmer_name=farmer_name, farmer_email=farmer_email,
                  lat=lat, lon=lon)
    db.session.add(scan)
    db.session.commit()

    return jsonify({
        "result": "Genuine Product" if is_genuine else "Warning: Possible Fake",
        "sha256": digest,
        "storedId": scan.id,
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
