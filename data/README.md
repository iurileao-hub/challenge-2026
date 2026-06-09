# data/

Datasets brutos baixados localmente (gitignored, exceto este README). Quem clonar o repositório regenera tudo executando `notebooks/frota_ev_brasil.ipynb` — as células de download recriam os arquivos abaixo e são puladas quando eles já existem.

| Arquivo | Conteúdo | Origem | Como obter |
|---|---|---|---|
| `ocm_br_poi.json` | 1.298 pontos de recarga no Brasil (ID, título, município, UF, lat/lon, nº de pontos/conexões) consolidados num único JSON | Open Charge Map, espelho oficial [`openchargemap/ocm-export`](https://github.com/openchargemap/ocm-export) (commit de 2026-04-22 na data do download, 2026-06-09) | Célula de download do notebook: clone esparso de `data/BR` + consolidação. Sem autenticação. A API oficial (`api.openchargemap.io/v3/poi`) exige chave gratuita — instruções no notebook |
| `ibge_municipios.json` | Lista oficial dos 5.571 municípios brasileiros com UF e região (visão nivelada) | [API de localidades do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado) | Célula de download do notebook (HTTP GET simples) |

Os dados da ABVE/Tupi Mobilidade (emplacamentos anuais, rede de recarga, frota plug-in) **não têm dataset estruturado público** — foram transcritos manualmente de releases e estão como dicionários comentados no próprio notebook, com URL e data de acesso por número.
