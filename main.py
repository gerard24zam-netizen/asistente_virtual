import pytz
import sys
import re
import os
import json
import requests
import datetime
import threading
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

# --- CONFIGURACIÓN SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

RECORDATORIOS_ACTIVOS_MEMORIA = {}

def log_debug(mensaje):
    print(f"DEBUG: {mensaje}", flush=True)

def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: return None
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_telefono_paciente(evento):
    """Limpia el texto y extrae el número de 10 dígitos de forma robusta."""
    texto = f"{evento.get('summary', '')} {evento.get('description', '')} {evento.get('location', '')}"
    clean_text = re.sub(r'[\s\-\(\)\+]', '', texto)
    
    match = re.search(r'(?:521?)?(\d{10})', clean_text)
    if match:
        return match.group(1)
        
    digitos = "".join(filter(str.isdigit, texto))
    if len(digitos) >= 10:
        if digitos.startswith("52") and len(digitos) >= 12:
            idx = 3 if len(digitos) >= 13 and digitos[2] == '1' else 2
            return digitos[idx:idx+10]
        return digitos[-10:]
    return None

def extraer_nombre_paciente(evento):
    titulo = evento.get('summary', '')
    match_parentesis = re.search(r'\(([^)]+)\)', titulo)
    if match_parentesis:
        texto_interior = match_parentesis.group(1).strip()
        if texto_interior.lower() not in ['atención psicológica', 'atencion psicologica', 'consulta', 'cita']:
            return texto_interior
    return "Paciente"

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

def registrar_recordatorio_activo(telefono, doctor_id):
    if not telefono or not doctor_id: return
    tel_limpio = limpiar_telefono(telefono)
    RECORDATORIOS_ACTIVOS_MEMORIA[tel_limpio] = str(doctor_id)

# --- FUNCIONES DE ENVÍO DE MENSAJES ---
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
    else:
        payload = {"messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}}
        
    try:
        resp = requests.post(url, json=payload, headers=headers)
        log_debug(f"Respuesta Meta (General): {resp.status_code} - {resp.text}")
        return resp
    except Exception as e:
        log_debug(f"Error en envío: {e}")
        return None

def enviar_plantilla_doctor(telefono, nombre, citas_count):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    payload = {
        "messaging_product": "whatsapp", 
        "to": telefono, 
        "type": "template",
        "template": {
            "name": "jornada_doc", 
            "language": {"code": "es_MX"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": nombre},
                    {"type": "text", "text": str(citas_count)}
                ]
            }]
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=headers)
        log_debug(f"Respuesta Meta (Doctor {nombre}): {resp.status_code} - {resp.text}")
        return resp
    except Exception as e:
        log_debug(f"Error en enviar_plantilla_doctor: {e}")
        return None

def enviar_recordatorios_a_pacientes(doc, hoy):
    cal_id = doc.get("calendar_id") or doc.get("email")
    if not cal_id: return
    
    zona_mexico = pytz.timezone('America/Mexico_City')
    inicio_mexico = datetime.datetime.now(zona_mexico).replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = datetime.datetime.now(zona_mexico).replace(hour=23, minute=59, second=59, microsecond=0)
    
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
    
    contador = 0
    for evento in eventos:
        tel = extraer_telefono_paciente(evento)
        p_nombre = extraer_nombre_paciente(evento)
        
        if tel and len(tel) == 10:
            registrar_recordatorio_activo(tel, doc['id'])
            params = [{"type": "text", "text": p_nombre}]
            resp = enviar_mensaje(tel, "template", template_params=params)
            if resp and resp.status_code in [200, 201]:
                contador += 1
                log_debug(f"✅ Recordatorio enviado exitosamente al paciente {p_nombre} ({tel})")
            else:
                log_debug(f"❌ Error enviando a Meta para el paciente {p_nombre} ({tel})")
        else:
            log_debug(f"⚠️ No se pudo extraer teléfono válido del evento: {evento.get('summary')}")
            
    # Notificar resumen al doctor
    tel_doc = "".join(filter(str.isdigit, str(doc.get("wa_link", ""))))
    if tel_doc:
        enviar_mensaje(tel_doc, "text", contenido=f"📊 Se han enviado {contador} recordatorios de cita a los pacientes programados para hoy.")

# --- ENDPOINTS ---
@app.route('/disparar-reportes', methods=['POST'])
def endpoint_disparar_reportes():
    log_debug("Iniciando jornada matutina...")
    if not supabase:
        return jsonify({"status": "Error: Supabase no inicializado"}), 500
    
    try:
        doctores = supabase.table("Doctores").select("*").execute().data
        if not doctores:
            return jsonify({"status": "Sin doctores"}), 200

        zona_mexico = pytz.timezone('America/Mexico_City')
        inicio_mexico = datetime.datetime.now(zona_mexico).replace(hour=0, minute=0, second=0, microsecond=0)
        fin_mexico = datetime.datetime.now(zona_mexico).replace(hour=23, minute=59, second=59, microsecond=0)
        
        inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        hoy = datetime.datetime.now(zona_mexico).strftime('%Y-%m-%d')
        
        for doc in doctores:
            doc_nombre = doc.get('name') or doc.get('nombre') or 'Psic. Gerardo Zamora'
            cal_id = doc.get("calendar_id") or doc.get("email")
            if not cal_id: continue
            
            try:
                eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
                count = len(eventos)
            except:
                count = 0
            
            wa_raw = doc.get("wa_link") or doc.get("link") or ""
            telefono_doc = "".join(filter(str.isdigit, str(wa_raw)))
            
            if telefono_doc and len(telefono_doc) >= 10:
                # 1. Enviar plantilla interactiva al doctor
                enviar_plantilla_doctor(telefono_doc, doc_nombre, count)
                log_debug(f"✅ Reporte enviado al doctor {doc_nombre} con {count} citas.")
                
                # 2. Enviar recordatorios a los pacientes
                enviar_recordatorios_a_pacientes(doc, hoy)

        return jsonify({"status": "Rutina ejecutada con éxito"}), 200
    except Exception as e:
        log_debug(f"Error crítico en endpoint: {e}")
        return jsonify({"status": str(e)}), 500

@app.route('/ejecutar-proceso-diario', methods=['POST'])
def endpoint_proceso_diario():
    return endpoint_disparar_reportes()

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
        return "Forbidden", 403
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
