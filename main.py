import sys
import re
import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

def limpiar_telefono(cadena):
    # Extrae solo los dígitos (del 0 al 9)
    return re.sub(r'\D', '', str(cadena))

def obtener_servicio_calendar():
    # Leemos el JSON desde la variable de entorno que configuramos en Render
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json:
        raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def limpiar_telefono(tel):
    return "52" + "".join(filter(str.isdigit, str(tel)))[-10:]

# --- LÓGICA DE ACTUALIZACIÓN DE CALENDARIO ---
def marcar_evento(telefono_recibido, accion):
    # 1. Normalizar el teléfono
    tel_buscado = limpiar_telefono(telefono_recibido)[-10:]
    print(f"DEBUG: Buscando cita para el teléfono: {tel_buscado}")
    
    # 2. Definir rango (ajustado a hoy)
    import datetime
    # Asegúrate de que las fechas sean correctas
    hoy = datetime.datetime.utcnow() 
    inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = hoy.replace(hour=23, minute=59, second=59, microsecond=0)
    
    print(f"DEBUG: Buscando eventos entre {inicio} y {fin}")
    
    eventos = calendario.getEvents(inicio, fin)
    
    if not eventos:
        print("DEBUG: ¡No se encontraron eventos hoy en ese rango!")
        return False
        
    print(f"DEBUG: Se encontraron {len(eventos)} eventos hoy.")
    
    for evento in eventos:
        titulo = evento.summary
        titulo_limpio = limpiar_telefono(titulo)
        print(f"DEBUG: Analizando evento: '{titulo}' -> Limpio: '{titulo_limpio}'")
        
        if tel_buscado in titulo_limpio:
            print(f"DEBUG: ¡MATCH! Encontrado evento para {tel_buscado}")
            # Quitamos marcas previas
            nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '')} ✅"
            print(f"DEBUG: Cambiando título a: {nuevo_titulo}")
            
            evento.update({'summary': nuevo_titulo})
            print("DEBUG: Evento actualizado exitosamente.")
            return True
    
    print("DEBUG: Fin del ciclo. Ningún evento coincidió con el teléfono.")
    return False
# --- RUTAS ---
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
    # ESTO DEBE SER LO PRIMERO QUE HACE LA FUNCIÓN
    print("--- RECIBÍ UNA PETICIÓN EN EL WEBHOOK ---")
    sys.stdout.flush() 

    if request.method == 'GET':
        if request.args.get("hub.verify_token") == "TOKEN_SECRETO_META":
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    # Aquí capturamos lo que llega
    try:
        data = request.get_json()
        print(f"DATOS RECIBIDOS: {data}")
        sys.stdout.flush()
    except Exception as e:
        print(f"ERROR AL LEER JSON: {e}")
        sys.stdout.flush()
        return "Error", 400

    # ... el resto de tu lógica sigue aquí abajo ...
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
