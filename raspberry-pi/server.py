from flask import Flask, jsonify, request
import lgpio
import atexit

CHIP = 0

ZONES = {
    1: 4,    # GPIO4,  physical pin 7
    2: 17,   # GPIO17, physical pin 11
    3: 27,   # GPIO27, physical pin 13
    4: 22,   # GPIO22, physical pin 15
    5: 23,   # GPIO23, physical pin 16
    6: 24,   # GPIO24, physical pin 18
}

app = Flask(__name__)

chip = lgpio.gpiochip_open(CHIP)
state = {zone: False for zone in ZONES}


# ---------- GPIO CONTROL ----------

def zone_on(zone):
    # Safety: only one zone ON at a time
    for z in ZONES:
        if z != zone:
            zone_off(z)

    pin = ZONES[zone]
    lgpio.gpio_claim_output(chip, pin)
    lgpio.gpio_write(chip, pin, 0)  # LOW = relay ON
    state[zone] = True


def zone_off(zone):
    pin = ZONES[zone]
    lgpio.gpio_claim_input(chip, pin)  # release = OFF
    state[zone] = False


def all_off():
    for z in ZONES:
        zone_off(z)


def all_on():
    # ⚠️ This will still result in only ONE zone ON because of safety
    for z in ZONES:
        zone_on(z)


# ---------- API ----------

@app.route("/")
def index():
    return jsonify({
        "name": "sprinkler-controller",
        "zones": list(ZONES.keys()),
        "endpoints": [
            "GET /zone/<zone>",
            "POST /zone/<zone> with body: on/off",
            "POST /zone/<zone>/on",
            "POST /zone/<zone>/off",
            "POST /alloff",
            "POST /allon",
        ],
    })


@app.route("/zone/<int:zone>", methods=["GET", "POST"])
def api_zone(zone):
    if zone not in ZONES:
        return jsonify({"error": "invalid zone"}), 400

    if request.method == "POST":
        body = request.get_data(as_text=True).strip().lower()

        if body in ("on", "true", "1"):
            zone_on(zone)
        elif body in ("off", "false", "0"):
            zone_off(zone)
        else:
            return jsonify({
                "error": "invalid body",
                "expected": "on or off"
            }), 400

    return jsonify({
        "zone": zone,
        "gpio": ZONES[zone],
        "on": state[zone],
    })


@app.route("/zone/<int:zone>/on", methods=["POST"])
def api_zone_on(zone):
    if zone not in ZONES:
        return jsonify({"error": "invalid zone"}), 400

    zone_on(zone)
    return jsonify({"zone": zone, "on": True})


@app.route("/zone/<int:zone>/off", methods=["POST"])
def api_zone_off(zone):
    if zone not in ZONES:
        return jsonify({"error": "invalid zone"}), 400

    zone_off(zone)
    return jsonify({"zone": zone, "on": False})


@app.route("/alloff", methods=["GET", "POST"])
def api_alloff():
    all_off()
    return jsonify({"state": "all_off"})


@app.route("/allon", methods=["GET", "POST"])
def api_allon():
    all_on()
    return jsonify({"state": "all_on"})


# ---------- CLEANUP ----------

@atexit.register
def cleanup():
    all_off()
    lgpio.gpiochip_close(chip)


# ---------- MAIN ----------

if __name__ == "__main__":
    # Start safe
    all_off()

    app.run(
        host="0.0.0.0",
        port=5050,
        debug=False
    )
