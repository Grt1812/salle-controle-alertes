from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from dotenv import load_dotenv
import os
from supabase import create_client
from datetime import datetime, timedelta

# Charger .env
load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecret"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# LED simulées
etat_leds = {
    "local_1": False, "local_2": True, "local_3": False, "local_4": True,
    "local_5": False, "local_6": False, "local_7": True, "local_8": False
}

# Auth vérification
def est_connecte():
    return 'user' in session

def parse_date_iso(date_str):
    """
    Parse la date ISO venant de Supabase.
    Exemple de date : '2025-07-09T21:45:00.000Z'
    """
    try:
        # Enlever le suffixe Z si présent
        if date_str.endswith('Z'):
            date_str = date_str[:-1]
        # Enlever la partie millisecondes si présente
        if '.' in date_str:
            date_str = date_str.split('.')[0]
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        print(f"Erreur parse date '{date_str}': {e}")
        return None

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if est_connecte() else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    erreur = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user'] = user.user.email
            return redirect(url_for('dashboard'))
        except Exception:
            erreur = "Email ou mot de passe incorrect"
    return render_template('login.html', erreur=erreur)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not est_connecte():
        return redirect(url_for('login'))
    
    alertes = []
    try:
        # Récupération des alertes depuis Supabase, triées par date décroissante
        result = supabase.table("alertes").select("*").order("date_heure", desc=True).limit(2).execute()
        alertes_raw = result.data or []
        
        for alerte in alertes_raw:
            dt_obj = parse_date_iso(alerte.get("date_heure", ""))
            if dt_obj:
                alerte["date_heure_fmt"] = dt_obj.strftime("%d/%m/%Y %H:%M")
            else:
                alerte["date_heure_fmt"] = "Date inconnue"
            alertes.append(alerte)
    except Exception as e:
        print(f"Erreur récupération alertes: {e}")
        alertes = []

    return render_template("dashboard.html", alertes=alertes)

@app.route('/bloc')
def bloc():
    if not est_connecte():
        return redirect(url_for('login'))
    return render_template('bloc.html')

@app.route('/status')
def status_bloc():
    if not est_connecte():
        return redirect(url_for('login'))
    return jsonify(etat_leds)

@app.route('/led_off')
def led_off():
    if not est_connecte():
        return redirect(url_for('login'))
    id = request.args.get('id')
    key = f"local_{id}"
    if key in etat_leds:
        etat_leds[key] = False
        return jsonify({"status": "ok", "id": id})
    return jsonify({"status": "error", "message": "LED inconnue"}), 400

@app.route('/led_on')
def led_on():
    if not est_connecte():
        return redirect(url_for('login'))
    id = request.args.get('id')
    key = f"local_{id}"
    if key in etat_leds:
        etat_leds[key] = True
        return jsonify({"status": "ok", "id": id})
    return jsonify({"status": "error", "message": "LED inconnue"}), 400

@app.route('/ajouter_alerte', methods=['GET', 'POST'])
def ajouter_alerte():
    if not est_connecte():
        return redirect(url_for('login'))

    if request.method == 'POST':
        chambre = request.form.get('chambre')
        etat = request.form.get('etat')
        medecin = request.form.get('medecin')
        date_heure = datetime.now().isoformat()

        try:
            supabase.table("alertes").insert({
                "chambre": chambre,
                "etat": etat,
                "medecin": medecin,
                "date_heure": date_heure
            }).execute()
            return redirect(url_for('dashboard'))
        except Exception as e:
            return f"Erreur lors de l'ajout : {e}"

    return render_template('ajouter_alerte.html')

@app.route('/alertes_detaillees')
def alertes_detaillees():
    if not est_connecte():
        return redirect(url_for('login'))
    
    alertes = []
    try:
        result = supabase.table("alertes").select("*").order("date_heure", desc=True).execute()
        alertes_raw = result.data or []
        
        for alerte in alertes_raw:
            dt_obj = parse_date_iso(alerte.get("date_heure", ""))
            if dt_obj:
                alerte["date_heure_fmt"] = dt_obj.strftime("%d/%m/%Y %H:%M")
            else:
                alerte["date_heure_fmt"] = "Date inconnue"
            alertes.append(alerte)
    except Exception as e:
        print(f"Erreur récupération alertes détaillées: {e}")
        alertes = []

    return render_template("alertes_detaillees.html", alertes=alertes)

@app.route('/historique')
def historique():
    if not est_connecte():
        return redirect(url_for('login'))

    periode = request.args.get('periode')
    medecin_filter = request.args.get('medecin')
    now = datetime.now()

    alertes = []
    try:
        result = supabase.table("alertes").select("*").order("date_heure", desc=True).execute()
        alertes_raw = result.data or []

        for a in alertes_raw:
            dt_obj = parse_date_iso(a.get("date_heure", ""))
            if not dt_obj:
                continue
            a["date_heure_obj"] = dt_obj
            a["date_heure_fmt"] = dt_obj.strftime("%d/%m/%Y %H:%M")
            alertes.append(a)

    except Exception as e:
        print(f"Erreur historique alertes: {e}")

    if periode == "semaine":
        debut = now - timedelta(days=7)
        alertes = [a for a in alertes if a["date_heure_obj"] >= debut]
    elif periode == "mois":
        debut = now - timedelta(days=30)
        alertes = [a for a in alertes if a["date_heure_obj"] >= debut]

    if medecin_filter:
        alertes = [a for a in alertes if a.get("medecin") == medecin_filter]

    return render_template("historique.html", alertes=alertes, periode=periode, medecin=medecin_filter)

if __name__ == '__main__':
    app.run(debug=True)
