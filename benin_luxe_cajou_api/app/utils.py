from flask_mail import Message
from .extensions import mail
from flask import current_app

def send_email(to, subject, body):
    """
    Fonction utilitaire pour envoyer des emails.
    """
    try:
        msg = Message(
            subject,
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[to],
            body=body
        )
        mail.send(msg)
    except Exception as e:
        # En production, vous devriez logguer cette erreur
        print(f"Erreur lors de l'envoi de l'email: {e}")
        # Vous pourriez lever une exception personnalisée ici si nécessaire
