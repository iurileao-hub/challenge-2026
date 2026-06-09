# data/

Datasets brutos baixados localmente (gitignored, exceto este README).

## Arquivos do notebook (Frente 1-C)

Quem clonar o repositório regenera estes executando `notebooks/frota_ev_brasil.ipynb` — as células de download recriam os arquivos abaixo e são puladas quando eles já existem.

| Arquivo | Conteúdo | Origem | Como obter |
|---|---|---|---|
| `ocm_br_poi.json` | 1.298 pontos de recarga no Brasil (ID, título, município, UF, lat/lon, nº de pontos/conexões) consolidados num único JSON | Open Charge Map, espelho oficial [`openchargemap/ocm-export`](https://github.com/openchargemap/ocm-export) (último commit do espelho: 2026-04-22; dados baixados em 2026-06-09) | Célula de download do notebook: clone esparso de `data/BR` + consolidação. Sem autenticação. A API oficial (`api.openchargemap.io/v3/poi`) exige chave gratuita — instruções no notebook |
| `ibge_municipios.json` | Lista oficial dos 5.571 municípios brasileiros com UF e região (visão nivelada) | [API de localidades do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado) | Célula de download do notebook (HTTP GET simples) |

## Respostas brutas das chamadas de API (Frente 2-C)

Evidência das chamadas reais documentadas na seção "Opção C — APIs complementares" de [`docs/frente-2-regulatorio.md`](../docs/frente-2-regulatorio.md) (todas em 2026-06-09; os comandos curl exatos das duas chamadas principais estão na própria seção).

| Arquivo | Conteúdo | Como obter |
|---|---|---|
| `ocm_api_nokey_response.txt` | Resposta real da API OCM sem chave (HTTP 403 + mensagem de exigência de chave), headers incluídos | curl da seção (com `-i`) |
| `ocm_poi_474661_full.json` | POI completo de exemplo (Eco Luz — Vila Monumento, São Paulo) no formato compacto do espelho | `curl https://raw.githubusercontent.com/openchargemap/ocm-export/main/data/BR/OCM-474661.json` |
| `ocm_referencedata.json` | Tabelas de referência da OCM (ConnectionTypes, StatusTypes, UsageTypes, Operators…) para resolver os IDs | `curl https://raw.githubusercontent.com/openchargemap/ocm-export/main/data/referencedata.json` |
| `ocm_openapi_spec.yaml` | Especificação OpenAPI oficial da API OCM v3 (parâmetros do `/poi`, esquema de autenticação) | `curl https://raw.githubusercontent.com/openchargemap/ocm-docs/master/Model/schema/ocm-openapi-spec.yaml` |
| `aneel_package_search_tarifa.json` | Resposta do `package_search?q=tarifa` (12 datasets) | curl da seção |
| `aneel_package_show_tarifas.json` | Metadados do dataset `tarifas-distribuidoras-energia-eletrica` (resources, datastore ativo, dicionário PDF) | `curl "https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=tarifas-distribuidoras-energia-eletrica"` |
| `aneel_datastore_sample.json` | `datastore_search` sem filtro, `limit=2` — lista dos 18 campos + total de 318.339 registros | `curl "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search?resource_id=fcf2906c-7c32-4b9b-a637-054e7a5234f4&limit=2"` |
| `aneel_datastore_enelsp_b3.json` | `datastore_search` filtrado (ELETROPAULO / B3 / Tarifa de Aplicação / Convencional), com a tarifa vigente da Enel SP | curl da seção |

Os dados da ABVE/Tupi Mobilidade (emplacamentos anuais, rede de recarga, frota plug-in) **não têm dataset estruturado público** — foram transcritos manualmente de releases e estão como dicionários comentados no próprio notebook, com URL e data de acesso por número.
