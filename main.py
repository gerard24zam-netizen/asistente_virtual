from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# CONFIGURACIÓN (REEMPLAZA ESTO)
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"

def limpiar_telefono(tel):
    # Quita espacios y guiones
    t = str(tel).replace(" ", "").replace("-", "")
    # Si tiene 10 dígitos, agrega el 52
    if len(t) == 10:
        return "52" + t
    return t

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    nombre = data.get('nombre')
    tel_bruto = data.get('telefono')
    fecha = data.get('fecha')
    
    telefono = limpiar_telefono(tel_bruto)
    
    # ESTRUCTURA DE LA PLANTILLA
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {"code": "es_MX"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre},
                        {"type": "text", "text": fecha}
                        {"type": "text", "text": "10:00 AM"}       # {{3}} - AQUÍ VA TU TERCER DATO
                    ]
                }
            ]
        }
    }
    
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Meta respondió: {response.status_code} - {response.text}")
    return jsonify({"status": "procesado", "meta_code": response.status_code})

if __name__ == '__main__':
    app.run(port=5000)
