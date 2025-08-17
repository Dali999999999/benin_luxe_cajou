from flask_mail import Message
from .extensions import mail
from flask import current_app
import logging

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

def send_status_update_email(order):
    """
    Envoie un email au client pour le notifier d'un changement de statut de sa commande.
    """
    try:
        client = order.client
        
        # On personnalise le message en fonction du nouveau statut
        if order.statut == 'en_preparation':
            subject = f"Votre commande #{order.numero_commande} est en cours de préparation"
            body = f"<p>Bonne nouvelle {client.prenom},</p><p>Nous avons commencé à préparer votre commande <b>{order.numero_commande}</b>. Elle sera bientôt prête pour l'expédition.</p>"
        elif order.statut == 'expedie':
            subject = f"Votre commande #{order.numero_commande} a été expédiée"
            body = f"<p>Votre commande <b>{order.numero_commande}</b> est en route !</p><p>Notre livreur vous contactera bientôt pour coordonner la livraison.</p>"
        elif order.statut == 'livree':
            subject = f"Votre commande #{order.numero_commande} a été livrée"
            body = f"<p>Nous espérons que vous appréciez vos produits !</p><p>Votre commande <b>{order.numero_commande}</b> a été marquée comme livrée. Merci de votre confiance et à bientôt !</p>"
        else:
            # Pour d'autres statuts comme 'annulee', on ne fait rien pour l'instant
            return

        msg = Message(subject=subject,
                      recipients=[client.email],
                      html=body + "<p>L'équipe Benin Luxe Cajou.</p>")
        mail.send(msg)
        logging.getLogger().info(f"Email de statut '{order.statut}' envoyé pour la commande {order.id}")
        return True
    except Exception as e:
        logging.getLogger().error(f"Erreur lors de l'envoi de l'email de statut pour la commande {order.id}: {e}")
        return False
