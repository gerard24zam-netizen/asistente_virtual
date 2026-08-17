import os
import json
import re
import requests
import datetime
import pytz
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

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def log(msg):
    print(f"DEBUG: {msg}", flush=True)

def obtener_servicio_calendar():
    try:
        creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
        if not creds_json:
            return None
        info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        log(f"Error calendar: {e}")
        return None

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

def extraer_nombre_limpio(titulo):
    titulo_limpio = titulo.replace(' ✅', '').replace(' ❌', '').replace('✅', '').replace('❌', '').strip()
    palabras = [p for p in titulo_limpio.split() if not p.isdigit()]
    nombre = " ".join(palabras).strip()
    return nombre if nombre else "Paciente"

def enviar_mensaje(telefono, tipo, contenido=None, template_params=None, template_name="confirmacion_cita"):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    
    if tipo == "template":
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "type": "template",
            "template": {
                "name": template_name, "language": {"code": "es_MX"},
                "components": [{"type": "body", "parameters": template_params}]
            }
        }
    else:
        payload = {"messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}}
        
    try:
        return requests.post(url, json=payload, headers=headers)
    except Exception as e:
        log(f"Error enviando mensaje: {e}")
        return None

def buscar_doctor_por_telefono(telefono_recibido):
    tel_buscado = limpiar_telefono(telefono_recibido)
    if not supabase:
        return None
    try:
        response = supabase.table("Doctores").select("*").execute()
        for doc in (response.data or []):
            wa_link = doc.get("wa_link") or doc.get("link") or ""
            if tel_buscado in limpiar_telefono(wa_link):
                return doc
    except Exception as e:
        log(f"Error buscando doctor por teléfono: {e}")
    return None

@app.route('/')
def home():
    return "API Activa", 200

@app.route('/ejecutar-proceso-diario', methods=['POST'])
def procesar_desde_supabase():
    if not supabase or not calendario:
        return jsonify({"error": "Falta configuración de Supabase o Google Calendar"}), 500

    try:
        response = supabase.table("Doctores").select("*").execute()
        doctores = response.data if response.data else []
    except Exception as e:
        log(f"Error consultando Supabase: {e}")
        return jsonify({"error": str(e)}), 500

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora = datetime.datetime.now(zona_mexico)
    fecha_hoy = str(ahora.date())

    nombres_dias = {
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles",
        "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sabado", "Sunday": "Domingo"
    }
    dia_actual_espanol = nombres_dias[ahora.strftime("%A")]

    inicio = ahora.replace(hour=0, minute=0, second=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora.replace(hour=23, minute=59, second=59).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    total_enviados = 0

    for doc in doctores:
        doc_nombre = doc.get("name") or doc.get("nombre") or "Dr. Gerardo"

        # --- VALIDACIÓN 1: Días de trabajo configurados y Excepciones de fin de semana ---
        dias_configurados = doc.get("dias_trabajo") or "Lunes,Martes,Miercoles,Jueves,Viernes"
        trabajar_fechas_str = doc.get("trabajar_fecha") or ""
        
        es_dia_laboral_normal = dia_actual_espanol in dias_configurados
        es_fecha_excepcion = fecha_hoy in [f.strip() for f in trabajar_fechas_str.split(",") if f.strip()]

        if not es_dia_laboral_normal and not es_fecha_excepcion:
            log(f"Hoy es {dia_actual_espanol} ({fecha_hoy}), día no laboral y sin excepciones para {doc_nombre}. Saltando ejecución.")
            continue

        # --- VALIDACIÓN 2: Pausa activa (Vacaciones o fin de semana largo) ---
        pausa_hasta = doc.get("pausa_hasta")
        if pausa_hasta and fecha_hoy <= pausa_hasta:
            log(f"El doctor {doc_nombre} se encuentra en pausa hasta {pausa_hasta}. Saltando ejecución.")
            continue

        cal_id = doc.get("calendar_id") or doc.get("email")
        if not cal_id:
            continue

        doc_ocupacion = doc.get("ocupation") or "Atención Psicológica"
        wa_link = doc.get("wa_link") or doc.get("link") or ""
        tel_doc = "".join(filter(str.isdigit, str(wa_link)))

        # Si ejecutó por excepción de fin de semana, limpiamos esa fecha ya procesada
        if es_fecha_excepcion and not es_dia_laboral_normal:
            fechas_pendientes = [f.strip() for f in trabajar_fechas_str.split(",") if f.strip() and f.strip() != fecha_hoy]
            nueva_fechas_str = ",".join(fechas_pendientes) if fechas_pendientes else None
            try:
                supabase.table("Doctores").update({"trabajar_fecha": nueva_fechas_str}).eq("calendar_id", cal_id).execute()
            except Exception as ex:
                log(f"Error limpiando trabajar_fecha en Supabase: {ex}")

        try:
            eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
        except Exception as e:
            log(f"Error leyendo calendario {cal_id}: {e}")
            continue

        # 1. Enviar plantilla jornada_doc solo si NO se ha enviado hoy
        jornada_registrada = doc.get("jornada_fecha")
        if tel_doc and jornada_registrada != fecha_hoy:
            total_citas_doc = len(eventos)
            params_jornada_doc = [
                {"type": "text", "text": doc_nombre},
                {"type": "text", "text": str(total_citas_doc)}
            ]
            resp_doc = enviar_mensaje(tel_doc, "template", template_params=params_jornada_doc, template_name="jornada_doc")
            if resp_doc and resp_doc.status_code < 400:
                log(f"Plantilla jornada_doc enviada al doctor {doc_nombre}")
                try:
                    supabase.table("Doctores").update({"jornada_fecha": fecha_hoy}).eq("calendar_id", cal_id).execute()
                except Exception as ex:
                    log(f"No se pudo guardar jornada_fecha en Supabase: {ex}")
        else:
            log(f"La plantilla jornada_doc ya había sido enviada hoy al doctor {doc_nombre}")

        # 2. Procesar y enviar recordatorios a los pacientes (Lógica intacta)
        for evento in eventos:
            titulo = evento.get('summary', '')
            descripcion = evento.get('description', '')
            
            if "✅" in titulo or "❌" in titulo:
                continue

            texto = f"{titulo} {descripcion}"
            digitos = "".join(filter(str.isdigit, texto))
            
            if len(digitos) >= 10:
                telefono_paciente = "52" + digitos[-10:]
                nombre_paciente = extraer_nombre_limpio(titulo)

                start_dt = evento.get('start', {}).get('dateTime', '')
                hora_str = "10:00 am"
                if start_dt:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(start_dt).astimezone(zona_mexico)
                        hora_str = dt_obj.strftime('%I:%M %p').lower()
                    except:
                        pass

                params = [
                    {"type": "text", "text": nombre_paciente},
                    {"type": "text", "text": doc_ocupacion},
                    {"type": "text", "text": "de hoy"},
                    {"type": "text", "text": hora_str},
                    {"type": "text", "text": doc_nombre}
                ]

                resp = enviar_mensaje(telefono_paciente, "template", template_params=params, template_name="confirmacion_cita")
                if resp and resp.status_code < 400:
                    total_enviados += 1
                    log(f"Recordatorio enviado a paciente {telefono_paciente}")

    return jsonify({"status": "ok", "enviados": total_enviados}), 200

def marcar_evento_calendario(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    if not supabase or not calendario:
        return None, None
    
    try:
        response = supabase.table("Doctores").select("*").execute()
        doctores = response.data if response.data else []
    except:
        doctores = [{"calendar_id": "gerard24zam@gmail.com", "nombre": "Dr. Gerardo", "wa_link": "https://wa.me/527226293417"}]

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    simbolo = "✅" if accion == 'confirmar' else "❌"

    for doc in doctores:
        cal_id = doc.get("calendar_id") or doc.get("email")
        if not cal_id:
            continue
        try:
            eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute()
            for evento in eventos_result.get('items', []):
                titulo = evento.get('summary', '')
                descripcion = evento.get('description', '')
                texto_completo = f"{titulo} {descripcion}"
                
                if tel_buscado in limpiar_telefono(texto_completo):
                    nombre_paciente = extraer_nombre_limpio(titulo)
                    titulo_limpio = titulo.replace(' ✅', '').replace(' ❌', '').replace('✅', '').replace('❌', '').strip()

                    if simbolo in titulo:
                        return doc, nombre_paciente
                    
                    nuevo_titulo = f"{titulo_limpio} {simbolo}"
                    
                    calendario.events().patch(
                        calendarId=cal_id, 
                        eventId=evento['id'], 
                        body={'summary': nuevo_titulo}
                    ).execute()
                    log(f"¡Calendario actualizado con {simbolo} para el evento: {nuevo_titulo}!")
                    return doc, nombre_paciente
        except Exception as e:
            log(f"Error actualizando calendario {cal_id}: {e}")
    return None, None

def procesar_webhook_asincrono(data):
    try:
        val = data['entry'][0]['changes'][0]['value']
        if 'messages' in val:
            msg = val['messages'][0]
            telefono_cliente = msg.get('from')
            
            texto = ""
            if msg.get('type') == 'button':
                texto = msg.get('button', {}).get('text', '').lower()
            elif msg.get('type') == 'text':
                texto = msg.get('text', {}).get('body', '').lower()
            
            log(f"Mensaje recibido de {telefono_cliente}: {texto}")

            # 1. Verificar si el mensaje viene de un DOCTOR registrado
            doc_encontrado = buscar_doctor_por_telefono(telefono_cliente)
            if doc_encontrado:
                doc_nombre = doc_encontrado.get("name") or doc_encontrado.get("nombre") or "Doctor"
                doc_cal_id = doc_encontrado.get("calendar_id")

                if any(k in texto for k in ["empecemos"]):
                    resp_doc = '¡Perfecto! es un buen momento para empezar el día, "Stein tu Asistente Virtual" *activado*'
                    enviar_mensaje(telefono_cliente, "text", contenido=resp_doc)
                    return

                elif any(k in texto for k in ["trabajo el fin de semana", "trabajar fin de semana", "trabajo sabado y domingo"]):
                    zona_mexico = pytz.timezone('America/Mexico_City')
                    ahora = datetime.datetime.now(zona_mexico)
                    hoy_date = ahora.date()
                    
                    sabado_date = hoy_date + datetime.timedelta(days=((5 - hoy_date.weekday() + 7) % 7))
                    domingo_date = hoy_date + datetime.timedelta(days=((6 - hoy_date.weekday() + 7) % 7))
                    trabajar_str = f"{sabado_date},{domingo_date}"
                    
                    try:
                        supabase.table("Doctores").update({
                            "trabajar_fecha": trabajar_str
                        }).eq("calendar_id", doc_cal_id).execute()
                    except Exception as e:
                        log(f"Error guardando trabajar_fecha en Supabase: {e}")
                        
                    resp_doc = f"Entendido Dr. {doc_nombre}, he habilitado la agenda para trabajar este fin de semana ({sabado_date} y {domingo_date}). *Stein tu Asistente Virtual*"
                    enviar_mensaje(telefono_cliente, "text", contenido=resp_doc)
                    return

                elif any(k in texto for k in ["trabajo este sabado", "trabajo el sabado"]):
                    zona_mexico = pytz.timezone('America/Mexico_City')
                    ahora = datetime.datetime.now(zona_mexico)
                    hoy_date = ahora.date()
                    sabado_date = hoy_date + datetime.timedelta(days=((5 - hoy_date.weekday() + 7) % 7))
                    
                    try:
                        supabase.table("Doctores").update({
                            "trabajar_fecha": str(sabado_date)
                        }).eq("calendar_id", doc_cal_id).execute()
                    except Exception as e:
                        log(f"Error guardando trabajar_fecha en Supabase: {e}")
                        
                    resp_doc = f"Entendido Dr. {doc_nombre}, he habilitado la agenda para trabajar este sábado {sabado_date}. *Stein tu Asistente Virtual*"
                    enviar_mensaje(telefono_cliente, "text", contenido=resp_doc)
                    return

                elif any(k in texto for k in ["trabajo este domingo", "trabajo el domingo"]):
                    zona_mexico = pytz.timezone('America/Mexico_City')
                    ahora = datetime.datetime.now(zona_mexico)
                    hoy_date = ahora.date()
                    domingo_date = hoy_date + datetime.timedelta(days=((6 - hoy_date.weekday() + 7) % 7))
                    
                    try:
                        supabase.table("Doctores").update({
                            "trabajar_fecha": str(domingo_date)
                        }).eq("calendar_id", doc_cal_id).execute()
                    except Exception as e:
                        log(f"Error guardando trabajar_fecha en Supabase: {e}")
                        
                    resp_doc = f"Entendido Dr. {doc_nombre}, he habilitado la agenda para trabajar este domingo {domingo_date}. *Stein tu Asistente Virtual*"
                    enviar_mensaje(telefono_cliente, "text", contenido=resp_doc)
                    return

                elif any(k in texto for k in ["hoy no trabajo", "no trabajo", "descanso"]):
                    zona_mexico = pytz.timezone('America/Mexico_City')
                    ahora = datetime.datetime.now(zona_mexico)
                    fecha_hoy = ahora.date()
                    
                    fecha_pausa_fin = fecha_hoy
                    
                    match_fecha = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', texto)
                    if match_fecha:
                        dia, mes, anio = map(int, match_fecha.groups())
                        try:
                            fecha_pausa_fin = datetime.date(anio, mes, dia)
                        except ValueError:
                            pass
                    else:
                        dias_semana_map = {
                            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, 
                            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
                        }
                        for nombre_dia, dia_num in dias_semana_map.items():
                            if nombre_dia in texto:
                                dias_a_sumar = (dia_num - fecha_hoy.weekday() + 7) % 7
                                if dias_a_sumar == 0:
                                    dias_a_sumar = 7
                                fecha_pausa_fin = fecha_hoy + datetime.timedelta(days=dias_a_sumar)
                                break

                    fecha_pausa_str = str(fecha_pausa_fin)
                    
                    try:
                        supabase.table("Doctores").update({
                            "jornada_fecha": str(fecha_hoy),
                            "pausa_hasta": fecha_pausa_str
                        }).eq("calendar_id", doc_cal_id).execute()
                    except Exception as e:
                        log(f"Error actualizando pausa en Supabase: {e}")

                    if fecha_pausa_fin > fecha_hoy:
                        resp_doc = f"Entendido Dr. {doc_nombre}, he pausado las notificaciones desde hoy hasta el {fecha_pausa_str}. Disfrute sus vacaciones o descanso. *Stein tu Asistente Virtual*"
                    else:
                        resp_doc = f"Siempre es bueno tomarse el día para darse un respiro, bajar el cortisol y despejar la mente, que descanse *{doc_nombre}*. Hasta mañana *Stein tu Asistente Virtual*"
                    
                    enviar_mensaje(telefono_cliente, "text", contenido=resp_doc)
                    return

            # 2. Si no es doctor, procesar como PACIENTE (Lógica intacta)
            if any(k in texto for k in ["si", "sí", "confirmo", "confirmar"]):
                doc, nombre_paciente = marcar_evento_calendario(telefono_cliente, 'confirmar')
                if doc:
                    doc_nombre = doc.get("name") or doc.get("nombre") or "Doctor"
                    wa_link = doc.get("wa_link") or doc.get("link") or ""
                    respuesta_texto = f"*¡Perfecto!* Se ha confirmado tu cita de hoy con {doc_nombre}. Dudas o aclaraciones, comunícate aquí: {wa_link}.\n *!Que tenga un excelente día¡*"
                    enviar_mensaje(telefono_cliente, "text", contenido=respuesta_texto)
                    
                    tel_doc = "".join(filter(str.isdigit, str(wa_link)))
                    if tel_doc:
                        enviar_mensaje(tel_doc, "text", contenido=f"✅ El paciente *{nombre_paciente}* ha confirmado su cita de hoy.")

            elif any(k in texto for k in ["no", "reagendar", "cancelar"]):
                doc, nombre_paciente = marcar_evento_calendario(telefono_cliente, 'reagendar')
                if doc:
                    doc_nombre = doc.get("name") or doc.get("nombre") or "Doctor"
                    wa_link = doc.get("wa_link") or doc.get("link") or ""
                    respuesta_texto = f"*Se ha cancelado tu cita.* Para reagendar, por favor comunícate con *{doc_nombre}*.\n *Da clic en el link de Whatsapp* aquí: {wa_link} con gusto atenderemos tu solicitud.\n *!Que tenga un excelente día¡*"
                    enviar_mensaje(telefono_cliente, "text", contenido=respuesta_texto)
                    
                    tel_doc = "".join(filter(str.isdigit, str(wa_link)))
                    if tel_doc:
                        enviar_mensaje(tel_doc, "text", contenido=f"❌ El paciente *{nombre_paciente}* indicó que necesita reagendar su cita de hoy.\n*es importante comunicarte con él, para que no pierda su cita*.")
    except Exception as e:
        log(f"Error en webhook asíncrono: {e}")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    hilo = threading.Thread(target=procesar_webhook_asincrono, args=(data,))
    hilo.start()
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
