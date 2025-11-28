import json
import boto3
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client('ses')

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
    project_folder = event.get('project_folder', 'Proyecto Desconocido')
    status = event.get('status', 'success')
    error_message = event.get('error', 'Error desconocido')
    
    # Try to find user email in various places
    user_email = event.get('user_email')
    if not user_email and 'input' in event:
        user_email = event['input'].get('user_email')
        
    # Configuration
    sender_email = "juandavidossa@hotmail.com"  # Verified sender
    admin_email = "juan.ossa@netec.com"
    recipients = [admin_email]
    
    if user_email:
        recipients.append(user_email)
        
    # Remove duplicates
    recipients = list(set(recipients))
    
    # Content generation based on status
    if status == 'failed':
        subject = f"❌ Error en Generación de Curso: {project_folder}"
        body_text = f"""
        Hola,
        
        La generación del curso para el proyecto '{project_folder}' ha fallado.
        
        Detalle del error:
        {error_message}
        
        Por favor contacta al administrador para soporte: {admin_email}
        
        Saludos,
        Aurora Course Generator
        """
        body_html = f"""
        <html>
        <head></head>
        <body>
          <h1 style="color: #d32f2f;">Error en Generación de Curso</h1>
          <p>Hola,</p>
          <p>La generación del curso para el proyecto <b>{project_folder}</b> ha fallado.</p>
          <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <strong>Detalle del error:</strong><br>
            {error_message}
          </div>
          <p>Por favor contacta al administrador para soporte: <a href="mailto:{admin_email}">{admin_email}</a></p>
          <br>
          <p>Saludos,</p>
          <p>Aurora Course Generator</p>
        </body>
        </html>
        """
    else:
        subject = f"✅ Generación de Curso Completada: {project_folder}"
        body_text = f"""
        Hola,
        
        La generación del curso para el proyecto '{project_folder}' ha finalizado exitosamente.
        
        Ya puedes ver y editar el contenido del curso en el panel de Aurora.
        
        Saludos,
        Aurora Course Generator
        """
        body_html = f"""
        <html>
        <head></head>
        <body>
          <h1 style="color: #2e7d32;">Generación de Curso Completada</h1>
          <p>Hola,</p>
          <p>La generación del curso para el proyecto <b>{project_folder}</b> ha finalizado exitosamente.</p>
          <p>Ya puedes ver y editar el contenido del curso en el panel de Aurora.</p>
          <br>
          <p>Saludos,</p>
          <p>Aurora Course Generator</p>
        </body>
        </html>
        """
    
    try:
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': recipients
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
        logger.info(f"Email sent successfully. MessageId: {response['MessageId']}")
        return {
            'statusCode': 200,
            'body': json.dumps('Notification sent successfully')
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        # We don't want to fail the workflow just because notification failed
        return {
            'statusCode': 200, 
            'body': json.dumps(f'Notification failed but ignored: {str(e)}')
        }
