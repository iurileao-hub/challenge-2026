"""Adaptadores de fonte. Acrescentar uma fonte e acrescentar uma linha aqui."""

from ingestion.adapters.dataset import AsensioDatasetAdapter  # noqa: F401
from ingestion.adapters.events import EventStreamAdapter  # noqa: F401
from ingestion.adapters.sems import SemsStubAdapter  # noqa: F401
from ingestion.adapters.semsplus_log import SemsPlusLogAdapter  # noqa: F401

#: Fontes consultaveis por nome (`manage.py ingest <fonte>`). O fluxo de eventos
#: nao entra: ele nao e consultado, e ENTREGUE -- pelo endpoint de push.
PULLABLE = {
    SemsPlusLogAdapter.name: SemsPlusLogAdapter,
    SemsStubAdapter.name: SemsStubAdapter,
    AsensioDatasetAdapter.name: AsensioDatasetAdapter,
}


def adapter_for_replay(source: str):
    """O adaptador capaz de RE-traduzir um registro bruto daquela fonte.

    Fonte desconhecida do registro e, por construcao, uma fonte de push: o nome
    veio da URL do endpoint.
    """
    if source in PULLABLE:
        return PULLABLE[source]()
    return EventStreamAdapter([], source=source)
