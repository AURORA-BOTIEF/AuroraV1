import json
import boto3
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client('ses')

ADMIN_EMAIL = "juan.ossa@netec.com"


def _compuerta_de_enlaces_muertos(event) -> bool:
    """True when the post-generation audit says dead public links must fail the course."""
    fuentes = [event]
    entrada = event.get("input") if isinstance(event, dict) else None
    if isinstance(entrada, dict):
        fuentes.append(entrada)
    for fuente in fuentes:
        auditoria = fuente.get("audit_result") if isinstance(fuente, dict) else None
        if not isinstance(auditoria, dict):
            continue
        payload = auditoria.get("Payload")
        if not isinstance(payload, dict):
            continue
        compuerta = payload.get("gate")
        if isinstance(compuerta, dict) and compuerta.get("bloquea") is True:
            return True
    return False


def construir_notificacion(
    status,
    project_folder,
    error_message,
    execution_arn,
    admin_email=ADMIN_EMAIL,
    advertencias_parciales=None,
):
    """Subject and bodies for success, failure, needs_review, and partial warnings.

    needs_review is not a successful delivery: the copy names the labs that
    still have high-confidence findings. Low-confidence lab warnings are not a
    reason to use this status. A succeeded run whose Setup Guide, post-generation
    audit, or decks failed is a warning, not a clean success and not a gate failure.
    """
    proyecto = project_folder or "Proyecto Desconocido"
    detalle = error_message or "Hallazgos de alta confianza pendientes de revisión."
    arn = execution_arn or "N/A"
    parciales = [p for p in (advertencias_parciales or []) if p]
    if status == "link_audit_failed":
        subject = f"🚫 Curso no entregado por enlaces muertos: {proyecto}"
        intro = (
            f"La generación del curso para el proyecto '{proyecto}' no se entregó. "
            "La auditoría encontró enlaces públicos muertos (HTTP 404, 410 o un dominio "
            "que no existe). Los códigos 403, 429 y 5xx no detienen el curso. "
            "El detalle está en labguide/enlaces.json."
        )
        color = "#d32f2f"
        titulo = "Enlaces públicos muertos"
    elif status == "needs_review":
        subject = f"⚠️ Curso pendiente de revisión: {proyecto}"
        intro = (
            f"La generación del curso para el proyecto '{proyecto}' no se entregó. "
            "Quedaron hallazgos de alta confianza después del último reintento "
            "(cantidades o duración del temario, objetivos, ficheros no declarados, "
            "entorno u otras validaciones de alta confianza). El borrador queda para revisión."
        )
        color = "#ed6c02"
        titulo = "Curso pendiente de revisión"
    elif status == "failed":
        subject = f"❌ Error en Generación de Curso: {proyecto}"
        intro = f"La generación del curso para el proyecto '{proyecto}' ha fallado."
        color = "#d32f2f"
        titulo = "Error en Generación de Curso"
    elif parciales:
        warning_list = ", ".join(parciales)
        subject = f"⚠️ Generación de curso con advertencias: {proyecto}"
        outcome = (
            f"El contenido principal del curso '{proyecto}' se generó, "
            f"pero falló: {warning_list}. Revisa el estado del curso en Aurora."
        )
        body_text = f"""
        Hola,
        
        {outcome}
        
        Ya puedes ver y editar el contenido del curso en el panel de Aurora.
        
        Execution ARN: {arn}
        
        Saludos,
        Sistema de Generación de Cursos de Netec
        """
        body_html = f"""
        <html>
        <head></head>
        <body>
          <h1 style="color: #ed6c02;">Generación de curso con advertencias</h1>
          <p>Hola,</p>
          <p>{outcome}</p>
          <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <strong>Componentes con error:</strong> {warning_list}
          </div>
          <p>Ya puedes ver y editar el contenido del curso en el panel de Aurora.</p>
          <div style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin: 20px 0; font-size: 12px;">
            <strong>Execution ARN:</strong><br>
            <code>{arn}</code>
          </div>
          <br>
          <p>Saludos,</p>
          <p>Sistema de Generación de Cursos de Netec</p>
        </body>
        </html>
        """
        return subject, body_text, body_html
    else:
        subject = f"✅ Generación de Curso Completada: {proyecto}"
        body_text = f"""
        Hola,
        
        La generación del curso para el proyecto '{proyecto}' ha finalizado exitosamente.
        
        Ya puedes ver y editar el contenido del curso en el panel de Aurora.
        
        Execution ARN: {arn}
        
        Saludos,
        Sistema de Generación de Cursos de Netec
        """
        body_html = f"""
        <html>
        <head></head>
        <body>
          <h1 style="color: #2e7d32;">Generación de Curso Completada</h1>
          <p>Hola,</p>
          <p>La generación del curso para el proyecto <b>{proyecto}</b> ha finalizado exitosamente.</p>
          <p>Ya puedes ver y editar el contenido del curso en el panel de Aurora.</p>
          <div style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin: 20px 0; font-size: 12px;">
            <strong>Execution ARN:</strong><br>
            <code>{arn}</code>
          </div>
          <br>
          <p>Saludos,</p>
          <p>Sistema de Generación de Cursos de Netec</p>
        </body>
        </html>
        """
        return subject, body_text, body_html

    body_text = f"""
        Hola,
        
        {intro}
        
        Detalle:
        {detalle}
        
        Execution ARN: {arn}
        
        Por favor contacta al administrador para soporte: {admin_email}
        
        Saludos,
        Sistema de Generación de Cursos de Netec
        """
    body_html = f"""
        <html>
        <head></head>
        <body>
          <h1 style="color: {color};">{titulo}</h1>
          <p>Hola,</p>
          <p>{intro}</p>
          <div style="background-color: #fff8e1; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <strong>Detalle:</strong><br>
            <pre style="white-space: pre-wrap; word-wrap: break-word;">{detalle}</pre>
          </div>
          <div style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin: 20px 0; font-size: 12px;">
            <strong>Execution ARN:</strong><br>
            <code>{arn}</code>
          </div>
          <p>Por favor contacta al administrador para soporte: <a href="mailto:{admin_email}">{admin_email}</a></p>
          <br>
          <p>Saludos,</p>
          <p>Sistema de Generación de Cursos de Netec</p>
        </body>
        </html>
        """
    return subject, body_text, body_html


def lambda_handler(event, context):
    """
    Lambda function to send a notification email upon workflow completion (success or failure).
    Expected input (event):
    {
        "project_folder": "string",
        "user_email": "string" (optional),
        "status": "success" | "failed" (optional, default success),
        "error": "string" (optional, for failure messages),
        ... other workflow outputs
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract parameters
    project_folder = event.get('project_folder')
    if not project_folder and 'input' in event:
        project_folder = event['input'].get('project_folder', 'Proyecto Desconocido')
    
    status = event.get('status', 'success')
    
    # Extract execution ARN
    execution_arn = event.get('execution_arn', 'N/A')
    
    # Robust error extraction
    error_message = event.get('error')
    if not error_message and 'input' in event:
        error_message = event['input'].get('error')
        
    # If error is a dictionary (from Catch block), format it
    if isinstance(error_message, dict):
        error_message = json.dumps(error_message, indent=2)
    
    if not error_message:
        error_message = 'Error desconocido'
    
    # Try to find user email in various places with detailed logging
    user_email = event.get('user_email')
    logger.info(f"user_email from event.get('user_email'): {user_email}")
    
    if not user_email and 'input' in event:
        user_email = event['input'].get('user_email')
        logger.info(f"user_email from event['input'].get('user_email'): {user_email}")
        
    # Configuration
    sender_email = "netecgeminiai@gmail.com"  # Verified sender
    admin_email = ADMIN_EMAIL
    recipients = [admin_email]
    
    if user_email and isinstance(user_email, str):
        cleaned_email = user_email.strip()
        if (cleaned_email and 
            "@" in cleaned_email and 
            not cleaned_email.lower().endswith("@example.com") and 
            not cleaned_email.lower().endswith("@iam.amazonaws.com") and 
            "unknown" not in cleaned_email.lower()):
            recipients.append(cleaned_email)
            logger.info(f"📧 Added user recipient: {cleaned_email}")
        else:
            logger.info(f"⚠️ Ignored dummy/invalid user email: {cleaned_email}")
        
    # Remove duplicates
    recipients = list(set(recipients))
    
    workflow_input = event.get("input") if isinstance(event.get("input"), dict) else {}
    partial_warnings = []
    for warning_key, label in (
        ("setup_guide_error", "Setup Guide"),
        ("audit_error", "Auditoría posterior"),
        ("decks_error", "Decks"),
    ):
        if event.get(warning_key) is not None or workflow_input.get(warning_key) is not None:
            partial_warnings.append(label)

    estado_correo = status
    if _compuerta_de_enlaces_muertos(event):
        estado_correo = "link_audit_failed"
        if not error_message or error_message == "Error desconocido":
            error_message = (
                "Enlaces públicos muertos (404, 410 o DNS). "
                "Revise labguide/enlaces.json."
            )

    logger.info(
        "QUALITY GATE notification status=%s project=%s detail=%s warnings=%s",
        estado_correo,
        project_folder,
        error_message,
        partial_warnings,
    )
    subject, body_text, body_html = construir_notificacion(
        estado_correo,
        project_folder,
        error_message,
        execution_arn,
        admin_email,
        advertencias_parciales=partial_warnings,
    )
    
    # Send emails individually to prevent one unverified email from blocking others
    results = []
    for recipient in recipients:
        try:
            response = ses_client.send_email(
                Source=sender_email,
                Destination={
                    'ToAddresses': [recipient]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': body_text,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': body_html,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            logger.info(f"Email sent successfully to {recipient}. MessageId: {response['MessageId']}")
            results.append(f"Success: {recipient}")
        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {str(e)}")
            results.append(f"Failed: {recipient} - {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps(f'Notification process completed. Results: {", ".join(results)}')
    }
