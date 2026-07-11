import datetime

def obtener_servicio_google():
    # Tu lógica de credenciales aquí
    pass

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))

def marcar_confirmado(telefono_recibido, service, respuesta_texto):
    texto_limpio = respuesta_texto.strip().lower()
    
    # 1. Identificar el estatus según la palabra clave recibida
    if any(x in texto_limpio for x in ["confirmo", "si", "sí", "correcto", "ok"]):
        emoji = "✅"
    elif any(x in texto_limpio for x in ["reagendar", "no", "cancel", "no puedo"]):
        emoji = "❌"
    else:
        print(f"Respuesta no concluyente ('{respuesta_texto}'), no se modifica el calendario.")
        return

    # 2. Extraer los últimos 10 dígitos del WhatsApp entrante
    tel_buscado = limpiar_telefono(telefono_recibido)
    tel_buscado_10 = tel_buscado[-10:] if len(tel_buscado) >= 10 else tel_buscado

    # 3. CORRECCIÓN DE ZONA HORARIA: Restamos 1 día completo al tiempo UTC 
    # para asegurar que abarque los eventos de hoy en México, sin importar la hora de la prueba.
    ayer = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat() + 'Z'
    
    print(f"Buscando eventos en Calendar desde: {ayer} para el teléfono: {tel_buscado_10}")
    eventos = service.events().list(calendarId='primary', timeMin=ayer).execute().get('items', [])

    # 4. Buscar coincidencia exacta por los 10 dígitos del teléfono
    for event in eventos:
        summary = event.get('summary', '')
        tel_evento = limpiar_telefono(summary)
        tel_evento_10 = tel_evento[-10:] if len(tel_evento) >= 10 else tel_evento
        
        # Comparamos los 10 dígitos del evento contra los 10 dígitos de WhatsApp
        if tel_evento_10 == tel_buscado_10 and len(tel_evento_10) == 10:
            # Limpiamos emojis viejos si existen para evitar duplicados (ej: ✅ ❌ Cita)
            base = summary.replace("✅", "").replace("❌", "").strip()
            
            # Construimos el nuevo título con su emoji correspondiente
            event['summary'] = f"{emoji} {base}"
            service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
            print(f"¡ÉXITO EN CALENDAR! Evento actualizado correctamente a: {event['summary']}")
            break
    else:
        print(f"No se encontró ningún evento coincidente para el teléfono {tel_buscado_10} en el rango de búsqueda.")
