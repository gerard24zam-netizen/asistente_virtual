from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# CONFIGURACIÓN
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META"
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec"

def limpiar_telefono(tel):
    return "52" + "".join(filter(str.isdigit, str(tel)))[-10:]

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono = limpiar_telefono(data.get('telefono'))
    payload = {
        "messaging_product": "whatsapp", "to": telefono, "type": "template",
        "template": {
            "name": "confirmacion_cita", "language": {"code": "es_MX"},
            "components": [{"type": "body", "parameters": [
                {"type": "text", "text": data.get('nombre')},
                {"type": "text", "text": data.get('fecha')},
                {"type": "text", "text": data.get('hora')}
            ]}]
        }
    }
    resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", 
                         json=payload, headers={"Authorization": f"Bearer {META_TOKEN}"})
    return jsonify({"status": resp.status_code})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    if 'messages' in data['entry'][0]['changes'][0]['value']:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        texto = msg.get('text', {}).get('body', '').lower()
        if "si" in texto or "confirmar" in texto:
            # Notifica a Google Apps Script
            requests.post(URL_GOOGLE_GAS, json={"telefono": msg['from'][-10:]})
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
