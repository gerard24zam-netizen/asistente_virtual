import datetime

def obtener_servicio_google():
    # Tu lógica de credenciales aquí
    pass

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))

def marcar_confirmado(telefono_recibido, service, respuesta_texto):
    texto_limpio = respuesta_texto.strip().lower()
    emoji = "✅" if "confirm" in texto_limpio else "❌" if "reagendar" in texto_limpio else None
    
    if not emoji:
        return

    tel_buscado = limpiar_telefono(telefono_recibido)
    ahora = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat() + 'Z'
    eventos = service.events().list(calendarId='primary', timeMin=ahora).execute().get('items', [])

    for event in eventos:
        if tel_buscado in limpiar_telefono(event.get('summary', '')):
            base = event.get('summary', '').replace("✅", "").replace("❌", "").strip()
            event['summary'] = f"{emoji} {base}"
            service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
            print(f"ÉXITO: {event['summary']}")
            break
