from django.urls import path

from portal import views

urlpatterns = [
    path("", views.home, name="home"),
    path("painel/", views.painel, name="painel"),
    path("painel/anomalia/<int:flag_id>/revisar/", views.revisar_anomalia, name="revisar_anomalia"),
    path("painel/anomalia/<int:flag_id>/resolver/", views.resolver_anomalia, name="resolver_anomalia"),
    path("painel/relatorio/", views.relatorio, name="relatorio"),
    path("painel/entrada/", views.entrada, name="entrada"),
    path("painel/entrada/recarga/<int:session_id>/atribuir/", views.atribuir_recarga, name="atribuir_recarga"),
    path("extrato/", views.extrato, name="extrato"),
    path("extrato/linha/<int:linha_id>/contestar/", views.contestar, name="contestar"),
]
