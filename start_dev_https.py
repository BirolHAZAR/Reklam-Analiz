"""Loopback-only HTTPS development server. Never use in production."""
import ipaddress
import os
from pathlib import Path
import ssl
import sys
from datetime import datetime, timedelta, timezone
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "instagram_reklam_analiz"
CERT_DIR = ROOT / "runtime" / "local-https"


def certificate():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = CERT_DIR / "localhost.crt", CERT_DIR / "localhost.key"
    if cert_path.exists() and key_path.exists():
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if cert.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=1):
            return cert_path, key_path
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ReklamAnaliz local development")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Handler(WSGIRequestHandler):
    def get_environ(self):
        environ = super().get_environ()
        environ["HTTPS"] = "on"
        environ["wsgi.url_scheme"] = "https"
        return environ

    def log_request(self, code="-", size="-"):
        # OAuth query strings contain one-use credentials; never log them.
        self.log_message("%s %s %s", self.command, self.path.split("?", 1)[0], code)


def main():
    os.chdir(PROJECT)
    sys.path.insert(0, str(PROJECT))
    os.environ["DEBUG"] = "True"
    os.environ["SENTRY_DSN"] = ""
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    import django
    django.setup()
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    if settings.DATABASES["default"].get("HOST") not in ("", "localhost", "127.0.0.1"):
        raise RuntimeError("Local HTTPS server requires a local database.")
    cert_path, key_path = certificate()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    with make_server("127.0.0.1", 8443, StaticFilesHandler(get_wsgi_application()),
                     server_class=Server, handler_class=Handler) as server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print("Local HTTPS ready: https://127.0.0.1:8443/hesap-ekle/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
