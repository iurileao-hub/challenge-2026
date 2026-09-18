"""Contexto compartilhado dos templates.

`e_gestor` vive num context processor, e nao em cada view, porque template
Django trata variavel ausente como vazia -- sem erro, sem aviso. O menu
simplesmente aparecia errado. Um lugar so elimina a classe inteira do problema.
"""

from core.models import AppUser


def perfil(request):
    # `pagina` acende o item do menu. Sai da rota resolvida, e nao de cada
    # view: nenhuma view a passava, e o menu nunca acendia -- exatamente a
    # classe de defeito que este arquivo existe para eliminar.
    pagina = getattr(request.resolver_match, "url_name", "") or ""
    if not request.user.is_authenticated:
        return {"pagina": pagina}
    app_user = AppUser.objects.filter(auth_user=request.user).select_related("unit").first()
    return {
        "pagina": pagina,
        "app_user_atual": app_user,
        "e_gestor": bool(app_user and app_user.role == AppUser.Role.MANAGER),
    }
