# backend/app/core/email.py
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


async def send_email(to: str, subject: str, html_body: str):
    """
    Асинхронная отправка email через SMTP.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject

    part = MIMEText(html_body, "html", "utf-8")
    msg.attach(part)

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
        use_tls=False,
    )


def build_verification_email(token: str, base_url: str) -> str:
    """
    HTML-шаблон письма для подтверждения email.
    """
    link = f"{base_url}/verify-email?token={token}"
    return f"""
    <html>
      <body>
        <h2>Подтверждение регистрации</h2>
        <p>Перейдите по ссылке, чтобы подтвердить email:</p>
        <a href="{link}">{link}</a>
        <p>Ссылка действительна 24 часа.</p>
      </body>
    </html>
    """


def build_password_reset_email(token: str, base_url: str) -> str:
    """
    HTML-шаблон письма для сброса пароля.
    """
    link = f"{base_url}/reset-password?token={token}"
    return f"""
    <html>
      <body>
        <h2>Восстановление пароля</h2>
        <p>Перейдите по ссылке, чтобы установить новый пароль:</p>
        <a href="{link}">{link}</a>
        <p>Ссылка действительна 1 час.</p>
      </body>
    </html>
    """
