from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META"
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbzIubYFyLXBMXifHbRRn3B4g45ic4xsKd_59sJviYMXNcJ9VBpy6wRl5W0PXfGGiAw66Q/exec"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token incorrecto", 403
    
    # Procesar respuesta del paciente
    data = request.get_json()
    try:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        telefono = msg.get('from')[-10:] # Últimos 10 dígitos
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
    print(f"DEBUG: Datos recibidos en Render: {data}") # <-- Veremos qué llega aquí
    
    telefono = "".join(filter(str.isdigit, str(data.get('telefono', ''))))
    if not telefono.startswith('52'): telefono = '52' + telefono
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {"code": "es_MX"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": data.get('nombre', 'Paciente')},
                    {"type": "text", "text": data.get('hora', '00:00')}
                ]
            }]
        }
    }
    
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    
    try:
        resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", json=payload, headers=headers)
        # Esto imprimirá el error real si Meta rechaza el mensaje
        print(f"DEBUG: Respuesta de Meta: {resp.status_code} - {resp.text}")
        return jsonify({"status": resp.status_code, "response": resp.text})
    except Exception as e:
        print(f"DEBUG: Error crítico de conexión: {str(e)}")
        return jsonify({"error": str(e)}), 500
