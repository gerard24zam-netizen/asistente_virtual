import datetime

def obtener_servicio_google():
    # Tu lógica de credenciales aquí
    pass

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))

def marcar_confirmado(telefono_received, service, respuesta_texto):
    texto_limpio = respuesta_texto.strip().lower()
    service = obtener_servicio_calendar() # Usa la conexión que ya tienes configurada
    ahora = datetime.utcnow().isoformat() + 'Z'
    
    # Buscamos eventos desde hoy
    eventos_result = service.events().list(calendarId='primary', timeMin=ahora,
                                           singleEvents=True, orderBy='startTime').execute()
    eventos = eventos_result.get('items', [])

    for evento in eventos:
        descripcion = evento.get('description', '')
        # Si el teléfono del mensaje está en la descripción del evento...
        if telefono_recibido in descripcion:
            titulo_actual = evento.get('summary', '')
            if "✅" not in titulo_actual:
                evento['summary'] = f"✅ {titulo_actual}"
                service.events().update(calendarId='primary', eventId=evento['id'], body=evento).execute()
                print(f"Calendario actualizado: ✅ {titulo_actual}")
                return True
                
   # 1. Determinar el emoji según la respuesta escrita o de botones de Meta
    # Agregamos "confirmar" y variaciones de la plantilla oficial
    if any(x in texto_limpio for x in ["Si_ confirmo", "confirmar", "confirmo", "si", "sí", "correcto", "ok", "confirmacion"]):
        emoji = "✅"
    elif any(x in texto_limpio for x in ["No, reagendar", "cancelar", "reagendar", "no", "cancel", "no puedo", "cancelacion"]):
        emoji = "❌"
    else:
        print(f"⚠️ Respuesta no concluyente ('{respuesta_texto}'). No coincide con palabras clave ni botones.")
        return

    # 2. Extraer estrictamente los últimos 10 dígitos del WhatsApp entrante
    tel_buscado = "".join(filter(str.isdigit, str(telefono_received)))
    tel_buscado_10 = tel_buscado[-10:] if len(tel_buscado) >= 10 else tel_buscado

    if not tel_buscado_10:
        print("No se pudo extraer un número de teléfono válido de la notificación.")
        return

    # 3. Rango de tiempo seguro para evitar desfases de zona horaria
    ayer = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat() + 'Z'
    
    print(f"Buscando eventos en Calendar desde: {ayer} para el teléfono: {tel_buscado_10}")
    eventos = service.events().list(calendarId='primary', timeMin=ayer).execute().get('items', [])

    # 4. BÚSQUEDA INTELIGENTE (Cruza datos en Título y Descripción)
    for event in eventos:
        summary = event.get('summary', '')
        description = event.get('description', '') # Cacha las notas internas de la cita
        
        # Extraemos todos los números que existan en el título y en la descripción por separado
        nums_en_titulo = "".join(filter(str.isdigit, str(summary)))
        nums_en_descripcion = "".join(filter(str.isdigit, str(description)))
        
        # ¡EL FILTRO MAESTRO!: Si los 10 dígitos del paciente están en el título O en la descripción...
        if (tel_buscado_10 in nums_en_titulo) or (tel_buscado_10 in nums_en_descripcion):
            # Limpiamos residuos de emojis viejos para evitar acumular "✅ ✅ Cita"
            base = summary.replace("✅", "").replace("❌", "").strip()
            
            # Colocamos el emoji al inicio del título
            event['summary'] = f"{emoji} {base}"
            
            # Ejecutamos la actualización directamente en tu Google Calendar
            service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
            print(f"¡ÉXITO TOTAL! Evento actualizado en Calendar a: {event['summary']}")
            return # Terminamos el proceso con éxito
            
    print(f"Alerta: No se localizó ninguna cita con el teléfono {tel_buscado_10} en título ni descripción.")
