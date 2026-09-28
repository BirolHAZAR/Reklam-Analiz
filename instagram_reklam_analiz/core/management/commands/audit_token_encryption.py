"""Audit raw database storage without revealing credentials."""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.fields import EncryptedTextField


class Command(BaseCommand):
    help = "Gizli alanlari ham veritabaninda kontrol eder; degerleri yazdirmaz."

    def add_arguments(self, parser):
        parser.add_argument("--encrypt-legacy", action="store_true", help="EncryptedTextField kolonlarindaki eski duz metni mevcut anahtarla sifrele.")

    def handle(self, *args, **options):
        apply = options["encrypt_legacy"]
        total = encrypted_total = plaintext_total = unreadable_total = converted_total = 0
        # Any unreadable/unsupported storage rolls back the whole conversion.
        with transaction.atomic():
            for model in apps.get_models():
                if not model._meta.managed or model._meta.proxy:
                    continue
                for field in model._meta.local_fields:
                    encrypted_field = isinstance(field, EncryptedTextField)
                    token_field = "token" in field.name and field.get_internal_type() in ("TextField", "CharField")
                    if not encrypted_field and not token_field:
                        continue
                    quote = connection.ops.quote_name
                    table, column, pk = quote(model._meta.db_table), quote(field.column), quote(model._meta.pk.column)
                    encrypted = plaintext = unreadable = converted = 0
                    lock = " FOR UPDATE" if apply and connection.features.has_select_for_update else ""
                    with connection.cursor() as cursor:
                        cursor.execute(f"SELECT {pk}, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} <> %s{lock}", [""])
                        rows = cursor.fetchall()
                    for object_id, value in rows:
                        total += 1
                        if str(value).startswith(EncryptedTextField.prefix):
                            try:
                                (field if encrypted_field else EncryptedTextField())._decrypt(value)
                                encrypted += 1
                            except Exception:
                                unreadable += 1
                        elif apply and encrypted_field:
                            try:
                                ciphertext = field._encrypt(value)
                                if field._decrypt(ciphertext) != value:
                                    raise ValueError("round-trip")
                            except Exception:
                                raise CommandError(f"Sifreleme dogrulanamadi: {model._meta.label}.{field.name}. Degisiklikler geri alindi.") from None
                            with connection.cursor() as cursor:
                                cursor.execute(f"UPDATE {table} SET {column} = %s WHERE {pk} = %s", [ciphertext, object_id])
                            converted += 1
                        else:
                            plaintext += 1
                    encrypted_total += encrypted
                    plaintext_total += plaintext
                    unreadable_total += unreadable
                    converted_total += converted
                    self.stdout.write(f"{model._meta.label}.{field.name}: encrypted={encrypted}, plaintext={plaintext}, unreadable={unreadable}, converted={converted}")
            if plaintext_total or unreadable_total:
                raise CommandError(f"Dogrulama basarisiz: plaintext={plaintext_total}, unreadable={unreadable_total}. "
                                   "EncryptedTextField eski kayitlari icin --encrypt-legacy kullanilabilir. Sifrelenmemis model alanlari ayri incelenmelidir.")
        self.stdout.write(self.style.SUCCESS(f"OK: nonempty={total}, encrypted={encrypted_total}, converted={converted_total}, plaintext=0, unreadable=0"))
