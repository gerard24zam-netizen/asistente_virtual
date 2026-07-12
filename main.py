from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Configuración
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "TOKEN_SECRETO_META"
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec"

@app.route('/', methods=['GET'])
def home():
    return "Servidor Operativo", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    print(f"DEBUG: Llegó petición a /recordatorios: {data}") # ESTO DEBE APARECER EN TUS LOGS
    
    telefono = "".join(filter(str.isdigit, str(data.get('telefono', ''))))
    if not telefono.startswith('52'): telefono = '52' + telefono
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {"code": "es_MX"},
            "components": [{"type": "body", "parameters": [
                {"type": "text", "text": data.get('nombre', 'Paciente')},
                {"type": "text", "text": data.get('hora', '00:00')}
            ]}]
        }
    }
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", json=payload, headers=headers)
    
    print(f"DEBUG: Respuesta Meta: {resp.text}")
    return jsonify({"status": resp.status_code})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
