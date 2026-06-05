import datetime
from googleapiclient.discovery import build

def obtener_servicio_google():
    # ... (tu código de credenciales actual, no lo cambies) ...
    return build('calendar', 'v3', credentials=creds)

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))

def marcar_confirmado(telefono_recibido, service, respuesta_texto):
    # 1. IDENTIFICAR EMOJI (Lógica de estados)
    texto_limpio = respuesta_texto.strip().lower()
    emoji = None
    if "si, confirmo" in texto_limpio or "confirm" in texto_limpio:
        emoji = "✅"
    elif "no, reagendar" in texto_limpio or "reagendar" in texto_limpio:
        emoji = "❌"
    
    if not emoji:
        print("Respuesta no reconocida")
        return

    # 2. BUSCAR EVENTO Y ACTUALIZAR
    tel_buscado = limpiar_telefono(telefono_recibido)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    eventos_result = service.events().list(calendarId='primary', timeMin=now).execute()
    eventos = eventos_result.get('items', [])

    for event in eventos:
        titulo_actual = event.get('summary', '')
        titulo_limpio = limpiar_telefono(titulo_actual)
        
        if tel_buscado in titulo_limpio:
            # Quitamos emojis previos si existen para limpiar
            titulo_base = titulo_actual.replace("✅ ", "").replace("❌ ", "").strip()
            # Aplicamos nuevo emoji
            nuevo_titulo = f"{emoji} {titulo_base}"
            
            event['summary'] = nuevo_titulo
            
            # GUARDAR EN GOOGLE
            service.events().update(
                calendarId='primary', 
                eventId=event['id'], 
                body=event
            ).execute()
            
            print(f"ÉXITO: Se actualizó a {nuevo_titulo}")
            return # Salimos después de actualizar
            
    print("No se encontró cita para este teléfono")
