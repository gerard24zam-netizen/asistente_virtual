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
from supabase import create_client

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- CONFIGURACIÓN SUPABASE & SAAS ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Diccionario de respaldo (Red de seguridad por si Supabase no responde)
CONTACTOS_DOCTORES = {
    "default": {
        "nombre": "Psic. Gerardo Zamora",
        "wa_link": "https://wa.me/527226293417"
    }
}

def get_doctor_data(doctor_id="default"):
    """
    Busca al doctor en Supabase y normaliza las llaves para evitar errores.
    """
    if supabase:
        try:
            response = supabase.table("Doctores").select("*").eq("id", doctor_id).execute()
            if response.data and len(response.data) > 0:
                row = response.data[0]
                print(f"DEBUG: Datos obtenidos de Supabase para {doctor_id}")
                return {
                    "nombre": row.get("nombre") or row.get("name", "Psic. Gerardo Zamora"),
                    "wa_link": row.get("wa_link") or row.get("link", "https://wa.me/527226293417")
                }
        except Exception as e:
            print(f"DEBUG: Error consultando Supabase: {e}")
    
    # Respaldo automático local
    print(f"DEBUG: Usando respaldo local para {doctor_id}")
    return CONTACTOS_DOCTORES.get(doctor_id, CONTACTOS_DOCTORES["default"])

# --- FUNCIÓN DE ENVÍO CENTRALIZADA ---
def enviar_mensaje(telefono, tipo, contenido=None, template_params=None):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    
    if tipo == "template":
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "type": "template",
            "template": {
                "name": "confirmacion_cita", "language": {"code": "es_MX"},
                "components": [{"type": "body", "parameters": template_params}]
            }
        }
    else: # tipo == "text"
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}
        }
        
    resp = requests.post(url, json=payload, headers=headers)
    print(f"DEBUG: Enviado a {telefono}. Status: {resp.status_code}")
    return resp

# --- LÓGICA DE ACTUALIZACIÓN DE CALENDARIO ---
def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

def marcar_evento(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    simbolo = "✅" if accion == 'confirmar' else "❌"
    
    # 1. Obtenemos todos los doctores dados de alta en Supabase
    doctores_registrados = []
    if supabase:
        try:
            res = supabase.table("Doctores").select("*").execute()
            if res.data:
                doctores_registrados = res.data
        except Exception as e:
            print(f"DEBUG: Error obteniendo lista de doctores: {e}")
            
    # Respaldo por si Supabase no responde
    if not doctores_registrados:
        doctores_registrados = [{
            "id": "default",
            "calendar_id": "gerard24zam@gmail.com"
        }]
        
    # 2. Buscamos en el calendario de cada doctor registrado en la BD
    for doc in doctores_registrados:
        cal_id = doc.get("calendar_id") or doc.get("email") or "gerard24zam@gmail.com"
        doc_id_actual = doc.get("id", "default")
        
        try:
            eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
            eventos = eventos_result.get('items', [])
            
            for evento in eventos:
                titulo = evento.get('summary', '')
                descripcion = evento.get('description', '')
                descripcion_sin_emails = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', descripcion)
                texto_completo = f"{titulo} {descripcion_sin_emails}"
                numeros_en_evento = limpiar_telefono(texto_completo)
                
                if tel_buscado in numeros_en_evento:
                    if simbolo in titulo: 
                        return doc_id_actual
                    nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '').strip()} {simbolo}"
                    evento['summary'] = nuevo_titulo
                    calendario.events().update(calendarId=cal_id, eventId=evento['id'], body=evento).execute()
                    print(f"DEBUG: Evento actualizado en el calendario de: {cal_id}")
                    return doc_id_actual
        except Exception as e:
            print(f"DEBUG: No se pudo revisar el calendario {cal_id}: {e}")
            
    return "default"

# --- RUTAS ---
@app.route('/')
def home():
    return "Bot de citas multi-tenant activo y funcionando correctamente", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    tel_limpio = "".join(filter(str.isdigit, str(data.get('telefono'))))
    telefono = "52" + tel_limpio if len(tel_limpio) == 10 else tel_limpio
    
    params = [
        {"type": "text", "text": data.get('nombre')},
        {"type": "text", "text": data.get('fecha')},
        {"type": "text", "text": data.get('hora')}
    ]
    enviar_mensaje(telefono, "template", template_params=params)
    return jsonify({"status": 200})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    if 'messages' in data['entry'][0]['changes'][0]['value']:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        telefono_cliente = msg.get('from')
        texto = msg.get('button', {}).get('text', '').lower() if msg.get('type') == 'button' else msg.get('text', {}).get('body', '').lower()

        if "si" in texto or "confirmo" in texto:
            marcar_evento(telefono_cliente, 'confirmar')
            
        elif "no" in texto or "reagendar" in texto:
            # marcar_evento localiza el evento y nos devuelve el ID del doctor propietario
            doc_id_encontrado = marcar_evento(telefono_cliente, 'reagendar')
            
            # Consultamos los datos de ese doctor en Supabase de forma dinámica
            doc = get_doctor_data(doc_id_encontrado)
            
            texto_reagendar = f"Entendido. Para reagendar, comunícate con {doc['nombre']} aquí: {doc['wa_link']}"
            enviar_mensaje(telefono_cliente, "text", contenido=texto_reagendar)
            
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
