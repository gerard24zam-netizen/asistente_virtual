from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" # El que pusiste en el Webhook de Meta
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbwwpy4hrxa8flB7C19EN8UAGMGZhfXzI5L4CuK9OXpyL-OoSX6x2ziZ5bM9oqkrRIDmqA/exec"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token incorrecto", 403
    
    data = request.get_json()
    try:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        telefono = msg.get('from')[-10:] # Ajusta si necesitas formato distinto
        texto = msg.get('text', {}).get('body', '').lower()
        
        # Lógica de respuesta
        if any(x in texto for x in ["si", "confirmar", "confirmado"]):
            requests.post(URL_GOOGLE_GAS, json={"telefono": telefono, "accion": "confirmado"})
        elif any(x in texto for x in ["no", "cancelar", "reagendar"]):
            requests.post(URL_GOOGLE_GAS, json={"telefono": telefono, "accion": "reagendar"})
    except: pass
    return "OK", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono = "".join(filter(str.isdigit, str(data.get('telefono', ''))))
    if not telefono.startswith('52'): telefono = '52' + telefono
    
    # ESTRUCTURA DE PLANTILLA META (Debes tenerla creada en Meta Business Suite)
    payload = {
        "messaging_product": "whatsapp", "to": telefono, "type": "template",
        "template": {
            "name": "confirmacion_cita", # EL NOMBRE EXACTO DE TU PLANTILLA
            "language": {"code": "es_MX"},
            "components": [{"type": "body", "parameters": [
                {"type": "text", "text": data.get('nombre', 'Paciente')},
                {"type": "text", "text": data.get('hora', '00:00')}
            ]}]
        }
    }
    resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", 
                         json=payload, headers={"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"})
    return jsonify({"status": resp.status_code})

if __name__ == '__main__':
    app.run(port=5000)
