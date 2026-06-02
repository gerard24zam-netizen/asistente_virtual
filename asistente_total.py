import os
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configuración Morelia
tz_morelia = timezone(timedelta(hours=-6))
SCOPES = ['https://www.googleapis.com/auth/calendar']

def obtener_servicio_google():
    """Autentica al usuario."""
    # Nota: En la nube, usarás variables de entorno para cargar las credenciales
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('calendar', 'v3', credentials=creds)

def marcar_confirmado(telefono_recibido, service, respuesta_texto):
    """Función maestra para actualizar el calendario."""
    ahora = datetime.now(tz_morelia)
    manana = (ahora + timedelta(days=1)).date()
    
    inicio_manana = datetime(manana.year, manana.month, manana.day, 0, 0, 0, tzinfo=tz_morelia).isoformat()
    fin_manana = datetime(manana.year, manana.month, manana.day, 23, 59, 59, tzinfo=tz_morelia).isoformat()
    
    eventos_result = service.events().list(
        calendarId='primary',
        timeMin=inicio_manana,
        timeMax=fin_manana,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    eventos = eventos_result.get('items', [])
    tel_buscado = telefono_recibido.replace(" ", "").replace("-", "").replace("+", "")
    
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