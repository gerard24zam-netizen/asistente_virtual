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

# --- CONFIGURACIÓN SUPABASE & SAAS ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def log_debug(mensaje):
    print(f"DEBUG: {mensaje}", flush=True)

def get_doctor_data(doctor_id="default"):
    if supabase:
        try:
            log_debug(f"Consultando Supabase para el doctor_id: '{doctor_id}'")
            response = supabase.table("Doctores").select("*").eq("id", doctor_id).execute()
            if response.data and len(response.data) > 0:
                row = response.data[0]
                log_debug(f"¡Doctor encontrado en Supabase!: {row}")
                return {
                    "id": str(row.get("id", "default")),
                    "nombre": str(row.get("name") or row.get("nombre", "Psic. Gerardo Zamora")).strip(),
                    "wa_link": str(row.get("wa_link") or row.get("link", "https://wa.me/527226293417")).strip(),
                    "ocupation": str(row.get("ocupation", "Atención Psicológica")).strip(),
                    "calendar_id": str(row.get("calendar_id") or row.get("email", "gerard24zam@gmail.com")).strip()
                }
        except Exception as e:
            log_debug(f"Error consultando Supabase para doctor_id {doctor_id}: {e}")
            
    return {
        "id": "default",
        "nombre": "Psic. Gerardo Zamora",
        "wa_link": "https://wa.me/527226293417",
        "ocupation": "Atención Psicológica",
        "calendar_id": "gerard24zam@gmail.com"
    }

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
        resp = requests.post(url, json=payload, headers=headers)
        log_debug(f"Mensaje enviado a {telefono}. Status: {resp.status_code}")
        if resp.status_code >= 400:
            log_debug(f"Respuesta de error de Meta: {resp.text}")
        return resp
    except Exception as e:
        log_debug(f"Excepción al enviar mensaje a Meta: {e}")
        return None

def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

def registrar_recordatorio_activo(telefono, doctor_id):
    if not supabase or not telefono or not doctor_id:
        return
        
    try:
        tel_limpio = limpiar_telefono(telefono)
        response = supabase.table("recordatorios_activos").upsert({
            "telefono": tel_limpio,
            "doctor_id": str(doctor_id),
            "updated_at": datetime.datetime.now().isoformat()
        }, on_conflict="telefono").execute()
        
        log_debug(f"Memoria actualizada: Teléfono {tel_limpio} asociado ESTRICTAMENTE al doctor_id {doctor_id}")
        
    except Exception as e:
        error_str = str(e)
        if "PGRST205" in error_str or "does not exist" in error_str:
            log_debug("AVISO DE SUPABASE: La tabla 'recordatorios_activos' no existe todavía.")
        else:
            log_debug(f"Error inesperado al guardar recordatorio activo en Supabase: {error_str}")

def marcar_evento(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    simbolo = "✅" if accion == 'confirmar' else "❌"
    
    # 1. Recuperar estrictamente el doctor_id asociado a este teléfono en Supabase
    doctor_sugerido_id = "default"
    if supabase:
        try:
            res_mem = supabase.table("recordatorios_activos").select("doctor_id").eq("telefono", tel_buscado).execute()
            if res_mem.data and len(res_mem.data) > 0:
                doctor_sugerido_id = res_mem.data[0].get("doctor_id")
                log_debug(f"Doctor recuperado de memoria para el teléfono {tel_buscado}: '{doctor_sugerido_id}'")
        except Exception as e:
            log_debug(f"Error consultando recordatorios_activos: {e}")

    # 2. Obtener los datos y calendario de ESE doctor exclusivamente
    doc_data = get_doctor_data(doctor_sugerido_id)
    cal_id = doc_data.get("calendar_id") or doc_data.get("email")
    
    if not cal_id:
        log_debug(f"Error: No se encontró calendar_id para el doctor {doctor_sugerido_id}")
        return None

    try:
        log_debug(f"Buscando cita exclusivamente en el calendario de: {doctor_sugerido_id} ({cal_id})")
        eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
        eventos = eventos_result.get('items', [])
        
        for evento in eventos:
            titulo = evento.get('summary', '')
            descripcion = evento.get('description', '')
            descripcion_sin_emails = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', descripcion)
            texto_completo = f"{titulo} {descripcion_sin_emails}"
            numeros_en_evento = limpiar_telefono(texto_completo)
            
            if tel_buscado in numeros_en_evento:
                log_debug(f"¡Cita encontrada exitosamente en el calendario correcto ({doctor_sugerido_id})!")
                if simbolo in titulo: 
                    return doctor_sugerido_id
                
                titulo_limpio = titulo.replace(' ✅', '').replace(' ❌', '').replace('✅', '').replace('❌', '').strip()
                nuevo_titulo = f"{titulo_limpio} {simbolo}"
                
                try:
                    calendario.events().patch(
                        calendarId=cal_id, 
                        eventId=evento['id'], 
                        body={'summary': nuevo_titulo}
                    ).execute()
                    log_debug(f"Evento actualizado con '{simbolo}' en el calendario de: {cal_id}")
                except Exception as patch_err:
                    log_debug(f"ERROR AL ACTUALIZAR CALENDARIO ({cal_id}): {patch_err}")
                
                return doctor_sugerido_id
    except Exception as e:
        log_debug(f"Error al revisar el calendario {cal_id}: {e}")
        
    log_debug(f"ADVERTENCIA: No se encontró coincidencia del teléfono {tel_buscado} en el calendario del doctor {doctor_sugerido_id}.")
    return None

def notificar_resumen_doctor(doc_id):
    if not doc_id:
        log_debug("doc_id recibido es nulo, no se puede enviar resumen.")
        return

    log_debug(f"Iniciando notificación de resumen exclusivamente para el doctor_id: '{doc_id}'")
    doc_data = get_doctor_data(doc_id)
    
    wa_link = doc_data.get("wa_link", "https://wa.me/527226293417")
    cal_id = doc_data.get("calendar_id", "gerard24zam@gmail.com")
    
    tel_doctor = "".join(filter(str.isdigit, str(wa_link)))
    log_debug(f"Resumen dirigido a '{doc_data['nombre']}' -> WhatsApp destino: {tel_doctor} (Calendario: {cal_id})")

    if not tel_doctor:
        log_debug("El teléfono del doctor está vacío, no se puede enviar resumen.")
        return

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    try:
        eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
        eventos = eventos_result.get('items', [])
        
        confirmados = []
        cancelados = []

        for evento in eventos:
            titulo = evento.get('summary', '')
            start_dt = evento.get('start', {}).get('dateTime', '')
            hora_str = ""
            if start_dt:
                try:
                    dt_obj = datetime.datetime.fromisoformat(start_dt).astimezone(zona_mexico)
                    hora_str = dt_obj.strftime('%H:%M')
                except:
                    pass
            
            nombre_raw = titulo.replace('✅', '').replace('❌', '')
            nombre_limpio = re.sub(r'\d{10}', '', nombre_raw)
            nombre_limpio = re.sub(r'[-–—_•.]', ' ', nombre_limpio)
            nombre_paciente = re.sub(r'\s+', ' ', nombre_limpio).strip() or "Paciente"

            if '✅' in titulo:
                confirmados.append(f"- {nombre_paciente} a las {hora_str} hrs")
            elif '❌' in titulo:
                cancelados.append(f"- {nombre_paciente} a las {hora_str} hrs")

        mensaje = f"📊 *Actualización de agenda (Resumen)*:\n\n"
        mensaje += f"✅ *Confirmados ({len(confirmados)}):*\n"
        if confirmados:
            mensaje += "\n".join(confirmados) + "\n"
        else:
            mensaje += "Ninguno aún\n"
        
        mensaje += f"\n❌ *Cancelados / Reagendados ({len(cancelados)}):*\n"
        if cancelados:
            mensaje += "\n".join(cancelados)
        else:
            mensaje += "Ninguno"

        enviar_mensaje(tel_doctor, "text", contenido=mensaje)
        log_debug(f"Resumen enviado exitosamente a {doc_data['nombre']} ({tel_doctor})")
    except Exception as e:
        log_debug(f"Error al armar o enviar resumen al doctor: {e}")

@app.route('/')
def home():
    return "Bot de citas multi-tenant activo y funcionando correctamente", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    tel_limpio = "".join(filter(str.isdigit, str(data.get('telefono'))))
    telefono = "52" + tel_limpio if len(tel_limpio) == 10 else tel_limpio
    
    doctor_id = data.get('doctor_id', 'default')
    doc_data = get_doctor_data(doctor_id)
    
    registrar_recordatorio_activo(telefono, doctor_id)
    
    p_nombre = str(data.get('nombre') or '').strip()
    if not p_nombre: p_nombre = "Paciente"
    
    p_ocupacion = str(doc_data.get('ocupation') or '').strip()
    if not p_ocupacion: p_ocupacion = "Atención Psicológica"
    
    p_fecha = str(data.get('fecha') or '').strip()
    if not p_fecha: p_fecha = "hoy"
    
    p_hora = str(data.get('hora') or '').strip()
    if not p_hora: p_hora = "00:00"
    
    p_doc = str(doc_data.get('nombre') or '').strip()
    if not p_doc: p_doc = "Doctor"

    params = [
        {"type": "text", "text": p_nombre},
        {"type": "text", "text": p_ocupacion},
        {"type": "text", "text": p_fecha},
        {"type": "text", "text": p_hora},
        {"type": "text", "text": p_doc}
    ]
    
    resp = enviar_mensaje(telefono, "template", template_params=params)
    if resp and resp.status_code < 400:
        return jsonify({"status": 200})
    return jsonify({"status": 400, "error": "Error al enviar mensaje por Meta"})

def procesar_calendarios_diarios():
    log_debug("Iniciando el proceso diario masivo de calendarios...")
    
    if not supabase:
        log_debug("Error: Supabase no está disponible para obtener los doctores.")
        return

    try:
        res = supabase.table("Doctores").select("*").execute()
        doctores = res.data if res.data else []
    except Exception as e:
        log_debug(f"Error al obtener doctores de Supabase en proceso diario: {e}")
        return

    if not doctores:
        doctores = [{"id": "default", "calendar_id": "gerard24zam@gmail.com", "ocupation": "Atención Psicológica"}]

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    for doc in doctores:
        doc_id = doc.get("id", "default")
        cal_id = doc.get("calendar_id") or doc.get("email")
        if not cal_id:
            continue

        log_debug(f"Revisando calendario para doctor: {doc_id} ({cal_id})")
        doc_data = get_doctor_data(doc_id)

        try:
            eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
            eventos = eventos_result.get('items', [])

            for evento in eventos:
                titulo = evento.get('summary', '')
                descripcion = evento.get('description', '')
                
                if "✅" in titulo or "❌" in titulo:
                    continue

                descripcion_limpia = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', ' ', descripcion) if descripcion else ""
                texto_para_buscar = f"{titulo} {descripcion_limpia}"
                
                match = re.search(r'\d{10}', texto_para_buscar)
                if not match:
                    continue

                telefono_encontrado = match.group(0)
                telefono_meta = "52" + telefono_encontrado

                registrar_recordatorio_activo(telefono_meta, doc_id)

                start_dt = evento.get('start', {}).get('dateTime', '')
                hora_str = ""
                if start_dt:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(start_dt).astimezone(zona_mexico)
                        hora_str = dt_obj.strftime('%H:%M')
                    except:
                        hora_str = "00:00"

                nombre_limpio = re.sub(r'\d{10}', '', titulo)
                nombre_limpio = re.sub(r'[-–—_•.]', ' ', nombre_limpio)
                nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
                p_nombre = nombre_limpio if nombre_limpio else "Paciente"

                p_ocupacion = str(doc_data.get('ocupation') or '').strip() or "Atención Psicológica"
                p_fecha = "hoy"
                p_hora = hora_str if hora_str else "00:00"
                p_doc = str(doc_data.get('nombre') or '').strip() or "Doctor"

                params = [
                    {"type": "text", "text": p_nombre},
                    {"type": "text", "text": p_ocupacion},
                    {"type": "text", "text": p_fecha},
                    {"type": "text", "text": p_hora},
                    {"type": "text", "text": p_doc}
                ]

                resp = enviar_mensaje(telefono_meta, "template", template_params=params)
                if resp and resp.status_code < 400:
                    log_debug(f"Recordatorio enviado exitosamente a {telefono_meta} para el doctor {doc_id}")
                else:
                    log_debug(f"Fallo al enviar recordatorio a {telefono_meta} para el doctor {doc_id}")

        except Exception as err_cal:
            log_debug(f"Error procesando calendario {cal_id}: {err_cal}")

@app.route('/ejecutar-proceso-diario', methods=['POST'])
def detonar_proceso_diario():
    hilo = threading.Thread(target=procesar_calendarios_diarios)
    hilo.start()
    return jsonify({"status": 200, "message": "Proceso diario iniciado en segundo plano"}), 200

def procesar_webhook_asincrono(data):
    try:
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            msg = data['entry'][0]['changes'][0]['value']['messages'][0]
            telefono_cliente = msg.get('from')
            texto = msg.get('button', {}).get('text', '').lower() if msg.get('type') == 'button' else msg.get('text', {}).get('body', '').lower()

            log_debug(f"Mensaje recibido de cliente {telefono_cliente}: '{texto}'")

            if "si" in texto or "confirmo" in texto:
                doc_id_encontrado = marcar_evento(telefono_cliente, 'confirmar')
                if doc_id_encontrado:
                    doc = get_doctor_data(doc_id_encontrado)
                    texto_confirmacion = f"Perfecto, hemos confirmado tu cita para el día de hoy con {doc['nombre']}. Dudas o aclaraciones, comunícate aquí: {doc['wa_link']}"
                    enviar_mensaje(telefono_cliente, "text", contenido=texto_confirmacion)
                    notificar_resumen_doctor(doc_id_encontrado)
                else:
                    log_debug(f"No se pudo asociar la confirmación del número {telefono_cliente} a ningún doctor.")
                
            elif "no" in texto or "reagendar" in texto:
                doc_id_encontrado = marcar_evento(telefono_cliente, 'reagendar')
                if doc_id_encontrado:
                    doc = get_doctor_data(doc_id_encontrado)
                    texto_reagendar = f"Entendido. Para reagendar, comunícate con {doc['nombre']} aquí: {doc['wa_link']}"
                    enviar_mensaje(telefono_cliente, "text", contenido=texto_reagendar)
                    notificar_resumen_doctor(doc_id_encontrado)
                else:
                    log_debug(f"No se pudo asociar la cancelación del número {telefono_cliente} a ningún doctor.")
    except Exception as e:
        log_debug(f"Error crítico en proceso asíncrono de webhook: {e}")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    
    hilo = threading.Thread(target=procesar_webhook_asincrono, args=(data,))
    hilo.start()
    
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
