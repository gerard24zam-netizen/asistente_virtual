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
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
API_KEY_SEGURIDAD = "MiClaveSuperSecreta123" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- CONFIGURACIÓN SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

RECORDATORIOS_ACTIVOS_MEMORIA = {}

def log_debug(mensaje):
    print(f"DEBUG: {mensaje}", flush=True)

# --- LÓGICA ENVÍO REPORTE DOCTOR ---
def enviar_plantilla_doctor(telefono, nombre, citas_count):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    payload = {
        "messaging_product": "whatsapp", "to": telefono, "type": "template",
        "template": {
            "name": "jordnada_doc", "language": {"code": "es"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(nombre)},
                    {"type": "text", "text": str(citas_count)}
                ]
            }]
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=headers)
        log_debug(f"Respuesta de Meta para {telefono} -> Status: {resp.status_code} | Body: {resp.text}")
        return resp
    except Exception as e:
        log_debug(f"Error al enviar petición HTTP a Meta: {e}")
        return None

def job_enviar_reporte_doctores():
    log_debug("Ejecutando proceso matutino de reportes para doctores...")
    if not supabase: 
        log_debug("Error: Supabase no está conectado.")
        return
    try:
        doctores = supabase.table("Doctores").select("*").execute().data
        
        # Rango horario ajustado a México para el conteo de citas
        zona_mexico = pytz.timezone('America/Mexico_City')
        ahora_mexico = datetime.datetime.now(zona_mexico)
        inicio_dia = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        fin_dia = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        hoy_str = ahora_mexico.strftime('%Y-%m-%d')
        
        for doc in doctores:
            log_debug(f"Revisando doctor: {doc.get('name') or doc.get('nombre')}")
            
            if doc.get("jornada_respondida_fecha") == hoy_str:
                log_debug("El doctor ya respondió hoy. Omitiendo envío.")
                continue

            cal_id = doc.get("calendar_id") or doc.get("email")
            if not cal_id: continue
            
            try:
                eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio_dia, timeMax=fin_dia, singleEvents=True).execute()
                count = len(eventos_result.get('items', []))
                log_debug(f"Citas encontradas en calendario {cal_id}: {count}")
            except Exception as e:
                log_debug(f"Error al consultar Google Calendar: {e}")
                count = 0
            
            telefono_doc = "".join(filter(str.isdigit, str(doc.get("wa_link", ""))))
            if telefono_doc and len(telefono_doc) >= 10:
                enviar_plantilla_doctor(telefono_doc, doc.get("name") or doc.get("nombre") or "Dr", count)
    except Exception as e:
        log_debug(f"Error crítico en job_enviar_reporte_doctores: {e}")

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.add_job(job_enviar_reporte_doctores, 'cron', hour=7, minute=0)
scheduler.start()

# --- LÓGICA DE PACIENTES (SIN CAMBIOS) ---
def get_doctor_data(doctor_id="default"):
    if supabase:
        try:
            response = supabase.table("Doctores").select("*").eq("id", doctor_id).execute()
            if response.data and len(response.data) > 0:
                row = response.data[0]
                return {
                    "id": str(row.get("id", "default")),
                    "nombre": str(row.get("name") or row.get("nombre", "Psic. Gerardo Zamora")).strip(),
                    "wa_link": str(row.get("wa_link") or row.get("link", "https://wa.me/527226293417")).strip(),
                    "ocupation": str(row.get("ocupation", "Atención Psicológica")).strip(),
                    "calendar_id": str(row.get("calendar_id") or row.get("email", "gerard24zam@gmail.com")).strip()
                }
        except Exception as e:
            log_debug(f"Error consultando Supabase: {e}")
    return {"id": "default", "nombre": "Psic. Gerardo Zamora", "wa_link": "https://wa.me/527226293417", "ocupation": "Atención Psicológica", "calendar_id": "gerard24zam@gmail.com"}

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
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}
        }
    try:
        return requests.post(url, json=payload, headers=headers)
    except: return None

def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: raise ValueError("No se encontró GOOGLE_TOKEN_JSON")
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
    inicio = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    simbolo = "✅" if accion == 'confirmar' else "❌"
    
    doctor_sugerido_id = "default"
    if tel_buscado in RECORDATORIOS_ACTIVOS_MEMORIA:
        doctor_sugerido_id = RECORDATORIOS_ACTIVOS_MEMORIA[tel_buscado]
    elif supabase:
        try:
            res_mem = supabase.table("recordatorios_activos").select("doctor_id").eq("telefono", tel_buscado).execute()
            if res_mem.data: doctor_sugerido_id = res_mem.data[0].get("doctor_id")
        except: pass

    doc_data = get_doctor_data(doctor_sugerido_id)
    cal_id = doc_data.get("calendar_id")
    if not cal_id: return None

    try:
        eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True, orderBy='startTime').execute()
        for evento in eventos_result.get('items', []):
            titulo = evento.get('summary', '')
            if tel_buscado in limpiar_telefono(titulo + evento.get('description', '')):
                if simbolo in titulo: return doctor_sugerido_id
                nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '').replace('✅', '').replace('❌', '').strip()} {simbolo}"
                calendario.events().patch(calendarId=cal_id, eventId=evento['id'], body={'summary': nuevo_titulo}).execute()
                return doctor_sugerido_id
    except: pass
    return None

def notificar_resumen_doctor(doc_id):
    if not doc_id: return
    doc_data = get_doctor_data(doc_id)
    tel_doctor = "".join(filter(str.isdigit, str(doc_data.get("wa_link", ""))))
    if not tel_doctor: return
    
    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    eventos = calendario.events().list(calendarId=doc_data.get("calendar_id"), timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
    
    def extraer_nombre(ev, d_id):
        titulo = ev.get('summary', '')
        p_nombre = "Paciente"
        match = re.search(r'\(([^)]+)\)', titulo)
        if match and match.group(1).lower() not in ['atención psicológica', 'atencion psicologica', 'consulta', 'cita']:
            p_nombre = match.group(1).strip()
        return p_nombre

    confirmados = [f"- {extraer_nombre(e, doc_id)}" for e in eventos if '✅' in e.get('summary', '')]
    cancelados = [f"- {extraer_nombre(e, doc_id)}" for e in eventos if '❌' in e.get('summary', '')]
    
    mensaje = f"📊 *Actualización de agenda*:\n\n✅ *Confirmados ({len(confirmados)}):*\n" + ("\n".join(confirmados) if confirmados else "Ninguno")
    mensaje += f"\n\n❌ *Cancelados ({len(cancelados)}):*\n" + ("\n".join(cancelados) if cancelados else "Ninguno")
    enviar_mensaje(tel_doctor, "text", contenido=mensaje)

# --- ENDPOINTS ---
@app.route('/disparar-reportes', methods=['POST'])
def endpoint_disparar():
    if request.headers.get("X-API-KEY") != API_KEY_SEGURIDAD: return "Acceso denegado", 403
    job_enviar_reporte_doctores()
    return jsonify({"status": "Proceso manual iniciado con éxito"}), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
        return "Forbidden", 403
    data = request.get_json()
    hilo = threading.Thread(target=procesar_webhook_asincrono, args=(data,))
    hilo.start()
    return "OK", 200

def procesar_webhook_asincrono(data):
    try:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        telefono_origen = msg.get('from')
        tipo = msg.get('type')
        hoy = datetime.datetime.now().strftime('%Y-%m-%d')
        if tipo == 'interactive':
            btn_title = msg['interactive']['button_reply']['title']
            if supabase:
                doctores = supabase.table("Doctores").select("*").execute().data
                for doc in doctores:
                    tel_doc = "".join(filter(str.isdigit, str(doc.get("wa_link", ""))))
                    if tel_doc == telefono_origen:
                        estado = True if "Empecemos" in btn_title else False
                        supabase.table("Doctores").update({"is_active_today": estado, "jornada_respondida_fecha": hoy}).eq("id", doc['id']).execute()
                        enviar_mensaje(telefono_origen, "text", contenido=f"Jornada actualizada: {'Activa' if estado else 'Pausada'}")
                        break
        elif tipo in ['text', 'button']:
            texto = msg.get('button', {}).get('text', '').lower() if tipo == 'button' else msg.get('text', {}).get('body', '').lower()
            if "si" in texto or "confirmo" in texto:
                doc_id = marcar_evento(telefono_origen, 'confirmar')
                if doc_id: notificar_resumen_doctor(doc_id)
            elif "no" in texto or "reagendar" in texto:
                doc_id = marcar_evento(telefono_origen, 'reagendar')
                if doc_id: notificar_resumen_doctor(doc_id)
    except Exception as e: log_debug(f"Error en webhook: {e}")

if __name__ == '__main__':
    app.run(port=5000)
