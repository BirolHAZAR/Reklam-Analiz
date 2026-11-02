from django.urls import path
from core.views.sync_center import sync_center, sync_center_account, sync_center_job_status

urlpatterns = [
    path("sync-center/", sync_center, name="sync_center"),
    path("sync-center/accounts/<int:account_id>/sync/", sync_center_account, name="sync_center_account"),
    path("sync-center/jobs/<int:job_id>/", sync_center_job_status, name="sync_center_job_status"),
]
