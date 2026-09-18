from django.urls import path

from ingestion import views

urlpatterns = [
    path("api/v1/ingest/<slug:source>/", views.push_events, name="ingest_push"),
]
