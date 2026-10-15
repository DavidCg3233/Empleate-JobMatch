"""Envío de correos.

Si SMTP_HOST está vacío en el .env (modo desarrollo), el correo NO se envía:
se imprime en la consola donde corre uvicorn para que puedas copiar el enlace.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("empleate.email")


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    if not settings.SMTP_HOST:
        print("\n" + "=" * 70)
        print(f"[CORREO - modo desarrollo] Para: {to}")
        print(f"Asunto: {subject}\n")
        print(text)
        print("=" * 70 + "\n", flush=True)
        return

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError):
        # Se registra el error sin romper la petición del usuario
        logger.exception("No se pudo enviar el correo a %s", to)


def send_password_reset(to: str, reset_link: str, minutes: int) -> None:
    subject = "Recupera tu contraseña - Empléate Jobmatch"
    text = (
        "Hola,\n\n"
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta en Empléate Jobmatch.\n"
        f"Abre este enlace para crear una nueva (vence en {minutes} minutos):\n\n"
        f"{reset_link}\n\n"
        "Si no fuiste tú, ignora este mensaje: tu contraseña seguirá igual.\n"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#2a2f33">
      <h2 style="color:#3f7f78">Empléate Jobmatch</h2>
      <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>
      <p style="text-align:center;margin:28px 0">
        <a href="{reset_link}" style="background:#3f7f78;color:#fff;padding:12px 22px;
           border-radius:10px;text-decoration:none;font-weight:bold">Crear nueva contraseña</a>
      </p>
      <p style="font-size:13px;color:#667078">El enlace vence en {minutes} minutos y solo se puede usar una vez.
      Si no fuiste tú, ignora este correo.</p>
    </div>"""
    send_email(to, subject, text, html)
