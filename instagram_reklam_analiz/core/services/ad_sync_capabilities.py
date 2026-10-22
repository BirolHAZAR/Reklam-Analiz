"""Shared campaign-panel and worker capabilities; organic OAuth is not Ads OAuth."""

SUPPORTED_AD_SYNC_PLATFORMS = {"facebook", "google_ads", "linkedin", "tiktok", "x"}


def supports_account_ad_sync(account):
    code = account.platform.code
    if code == "x":
        return bool(account.connection_id and (account.connection.extra_data or {}).get("source") == "x_ads_oauth")
    if code == "tiktok":
        return bool(account.connection_id and (account.connection.extra_data or {}).get("source") == "tiktok_ads_oauth")
    return code in SUPPORTED_AD_SYNC_PLATFORMS


def ad_sync_unavailable_message(platform_code):
    return {
        "instagram": "Facebook ve Instagram yerleşimleri kampanya düzeyinde ayrılamıyor. Meta kampanyalarını Facebook bölümünde inceleyin. Organik paylaşımlarınız Organik İçerik bölümündedir.",
        "youtube": "Bu bağlantı YouTube kanal verileri içindir. YouTube reklam kampanyalarını bağlı Google Ads hesabında inceleyin.",
        "tiktok": "Kampanyalar için ayrı TikTok Ads bağlantısını kullanın. Organik TikTok videoları Organik İçerik bölümünden yenilenir. Reklam erişimi için TikTok for Business uygulaması ve reklam hesabı izni gerekir.",
        "x": "Kampanyalar için ayrı X Ads bağlantısını kullanın. Organik X hesabı reklam erişimi sağlamaz; Standard Ads API onayı ve reklam hesabı okuma yetkisi gerekir.",
    }.get(platform_code, "Bu platformda reklam kampanyası senkronizasyonu henüz desteklenmiyor.")
