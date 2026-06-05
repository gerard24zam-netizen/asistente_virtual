import json
import os
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configuración Morelia
tz_morelia = timezone(timedelta(hours=-6))
SCOPES = ['https://www.googleapis.com/auth/calendar']

def obtener_servicio_google():
    # Línea 1: Obtener la variable de entorno
    token_json_str = os.getenv("GOOGLE_TOKEN_JSON")
    # Línea 2: Cargar el JSON
    token_dict = json.loads(token_json_str)
    # Línea 3: Crear credenciales
    creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
    # Línea 4: Construir servicio
    return build('calendar', 'v3', credentials=creds)
    
def limpiar_telefono(tel):
    # Esto elimina cualquier carácter que no sea número
    return "".join(filter(str.isdigit, str(tel)))

for event in eventos.get('items', []):
        titulo_actual = event.get('summary', '')
        
        # Verificamos si el teléfono está en el título (como ya lo haces)
        if tel_buscado in titulo_actual.replace(" ", "").replace("-", "").replace(":", ""):
            
            # --- AQUÍ ESTÁ EL CAMBIO: APLICAR EL CAMBIO Y GUARDAR ---
            if emoji:
                # Evitamos duplicar el emoji si ya existe
                if emoji not in titulo_actual:
                    event['summary'] = f"{emoji} {titulo_actual}"
                    
                    # ¡ESTA ES LA LÍNEA QUE FALTA!
                    service.events().update(
                        calendarId='primary', 
                        eventId=event['id'], 
                        body=event
                    ).execute()
                    
                    print(f"Evento actualizado: {event['summary']}")
    
    # Lógica de estados
    texto_limpio = respuesta_texto.strip().lower()
    if "si, confirmo" in texto_limpio or "confirm" in texto_limpio:
        emoji = "✅"
    elif "no, reagendar" in texto_limpio or "reagendar" in texto_limpio:
        emoji = "❌"
    else:
        return

    for event in eventos:
        titulo_actual = event.get('summary', '')
        if tel_buscado in titulo_actual.replace(" ", "").replace("-", "").replace("+", ""):
            titulo_base = titulo_actual.replace("✅", "").replace("❌", "").strip()
            event['summary'] = f"{emoji} {titulo_base}"
            service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
            return True
    return False

if __name__ == "__main__":
    # Esto es solo para pruebas manuales
    service = obtener_servicio_google()
    print("Servicio cargado correctamente.")
