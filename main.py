import pytz
import sys
import re
import os
import json
import requests
import datetime
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- INICIALIZACIÓN ---
def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json:
        raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

# --- LÓGICA DE ACTUALIZACIÓN ---
def marcar_evento(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    print(f"DEBUG: Buscando cita para el teléfono: {tel_buscado} (Acción: {accion})")
    
    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    eventos_result = calendario.events().list(calendarId='gerard24zam@gmail.com', timeMin=inicio, timeMax=fin).execute()
    eventos = eventos_result.get('items', [])
    
    if not eventos:
        print("DEBUG: No se encontraron eventos hoy.")
        return False
        
    simbolo = "✅" if accion == 'confirmar' else "❌"
        
    for evento in eventos:
        titulo = evento.get('summary', '')
        descripcion = evento.get('description', '')
        
        # 1. ELIMINAR CORREOS: Esto quita cualquier cosa que parezca email para que los números del correo no confundan
        descripcion_sin_emails = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', descripcion)
        
        # 2. Unimos todo para buscar
        texto_completo = f"{titulo} {descripcion_sin_emails}"
        
        # 3. Limpiamos todos los números que aparecen en el texto
        numeros_en_evento = limpiar_telefono(texto_completo)
        
        # 4. Buscamos el teléfono buscado dentro de los números encontrados
        if tel_buscado in numeros_en_evento:
            if simbolo in titulo:
                print("DEBUG: El evento ya estaba marcado.")
                return True
            
            nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '').strip()} {simbolo}"
            evento['summary'] = nuevo_titulo
            calendario.events().update(calendarId='gerard24zam@gmail.com', eventId=evento['id'], body=evento).execute()
            print(f"DEBUG: Evento actualizado correctamente.")
            return True
            
    return False

# --- RUTAS ---
@app.route('/debug_calendarios', methods=['GET'])
def debug_calendarios():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    info = json.loads(creds_json)
    correo_asistente = info.get('client_email')
    return f"Copia este correo para dar permisos: {correo_asistente}"

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono_raw = data.get('telefono')
    
    # Aseguramos que el teléfono tenga el formato 52 + 10 dígitos
    tel_limpio = "".join(filter(str.isdigit, str(telefono_raw)))
    if len(tel_limpio) == 10:
        telefono = "52" + tel_limpio
    elif len(tel_limpio) == 12 and tel_limpio.startswith("52"):
        telefono = tel_limpio # Ya viene con el 52
    else:
        telefono = tel_limpio # Por si acaso, lo enviamos como venga
        
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
    
    # Imprimimos el resultado para debug
    print(f"DEBUG: Enviando mensaje a {telefono}. Status: {resp.status_code}, Response: {resp.text}")
    
    return jsonify({"status": resp.status_code})
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    print(f"DATOS RECIBIDOS: {data}")
    sys.stdout.flush()

    if 'messages' in data['entry'][0]['changes'][0]['value']:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        msg_type = msg.get('type')
        telefono_cliente = msg.get('from')
        texto = ""

        if msg_type == 'text':
            texto = msg.get('text', {}).get('body', '').lower()
        elif msg_type == 'button':
            texto = msg.get('button', {}).get('text', '').lower()

        if "si" in texto or "confirmo" in texto:
            print(f"DEBUG: Usuario confirmó: {telefono_cliente}")
            marcar_evento(telefono_cliente, 'confirmar')
            
        elif "no" in texto or "reagendar" in texto:
            print(f"DEBUG: Usuario rechazó: {telefono_cliente}")
            marcar_evento(telefono_cliente, 'reagendar')

    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
