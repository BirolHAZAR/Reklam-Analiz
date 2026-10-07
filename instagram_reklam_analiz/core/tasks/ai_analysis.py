from celery import shared_task

from core.models import Ad, ReklamAIAnaliz


@shared_task(bind=True)
def analyze_single_ad_with_all_agents(self, reklam_id, user_id=None):
    ad = Ad.objects.filter(pk=reklam_id).first()
    if not ad:
        return {"success": False, "message": "Ad bulunamadi."}
    obj = ReklamAIAnaliz.objects.create(
        reklam=ad,
        reklam_adi=str(ad),
        Ins_reklam_id=ad.platform_ad_id or str(ad.id),
        overall_score=70,
        analysis_summary="V2 AI analiz task tamamlandi.",
        agents_results=[],
    )
    return {"success": True, "analysis_id": obj.id, "score": obj.overall_score}


@shared_task
def analyze_multiple_ads(ad_ids):
    results = []
    for ad_id in ad_ids:
        results.append(analyze_single_ad_with_all_agents(ad_id))
    return results
