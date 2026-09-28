from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from core.models import Platform, PlatformAccount


class TokenEncryptionTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="token-audit")
        platform, _ = Platform.objects.get_or_create(code="google_ads", defaults={"name": "Google Ads"})
        self.account = PlatformAccount.objects.create(user=user, platform=platform, account_id="123", access_token="fixture-secret", refresh_token="fixture-refresh")

    def raw_token(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT access_token FROM core_platformaccount WHERE id = %s', [self.account.pk])
            return cursor.fetchone()[0]

    def write_raw(self, value):
        with connection.cursor() as cursor:
            cursor.execute('UPDATE core_platformaccount SET access_token = %s WHERE id = %s', [value, self.account.pk])

    def test_new_tokens_and_queryset_updates_are_encrypted(self):
        self.assertTrue(self.raw_token().startswith("enc:v1:"))
        PlatformAccount.objects.filter(pk=self.account.pk).update(access_token="updated-secret")
        self.assertNotIn("updated-secret", self.raw_token())
        self.account.refresh_from_db()
        self.assertEqual(self.account.access_token, "updated-secret")

    def test_audit_and_legacy_conversion_are_secret_free_and_idempotent(self):
        self.write_raw("legacy-secret")
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_token_encryption", stdout=output)
        self.assertNotIn("legacy-secret", output.getvalue())
        self.assertEqual(self.raw_token(), "legacy-secret")
        call_command("audit_token_encryption", encrypt_legacy=True, stdout=output)
        ciphertext = self.raw_token()
        self.assertTrue(ciphertext.startswith("enc:v1:"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.access_token, "legacy-secret")
        call_command("audit_token_encryption", encrypt_legacy=True, stdout=output)
        self.assertEqual(self.raw_token(), ciphertext)
        self.assertNotIn("legacy-secret", output.getvalue())

    def test_unreadable_ciphertext_causes_failure_without_exposing_value(self):
        self.write_raw("enc:v1:invalid-fixture")
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_token_encryption", encrypt_legacy=True, stdout=output)
        self.assertNotIn("invalid-fixture", output.getvalue())
        self.assertEqual(self.raw_token(), "enc:v1:invalid-fixture")
