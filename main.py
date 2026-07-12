from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# CONFIGURACIÓN
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"

def limpiar_telefono(tel):
    # Elimina espacios, guiones y cualquier carácter no numérico
    t = "".join(filter(str.isdigit, str(tel)))
    # Si tiene 10 dígitos, agregamos prefijo México 52
    if len(t) == 10:
        return "52" + t
    return t

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    
    # Extraemos datos
    nombre = data.get('nombre', 'Paciente')
    telefono_bruto = data.get('telefono')
    fecha = data.get('fecha', 'hoy')
    hora = data.get('hora', 'por definir')
    
    telefono = limpiar_telefono(telefono_bruto)
    
    # Payload exacto de 3 parámetros para Meta
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
                        {"type": "text", "text": nombre}, # {{1}}
                        {"type": "text", "text": fecha},  # {{2}}
                        {"type": "text", "text": hora}    # {{3}}
                    ]
                }
            ]
        }
    }
    
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Meta respondió: {response.status_code} - {response.text}")
    return jsonify({"status": "recibido", "meta_code": response.status_code})

if __name__ == '__main__':
    app.run(port=5000)
