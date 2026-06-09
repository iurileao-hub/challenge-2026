# docs/normas — textos oficiais preservados

Fontes primárias usadas na Frente 2 (Opção A). Toda citação de artigo/item no dossiê
(`docs/frente-2-regulatorio.md`) foi conferida contra os arquivos abaixo. Downloads em **2026-06-09**.

| Arquivo | Norma | Órgão | URL oficial de origem |
|---|---|---|---|
| `aneel-ren-1000-2021-dou.html` | Resolução Normativa ANEEL nº 1.000, de 7/12/2021 — texto original integral (DOU 20/12/2021, ed. 238, seção 1, p. 206) | ANEEL / Imprensa Nacional | https://www.in.gov.br/en/web/dou/-/resolucao-normativa-aneel-n-1.000-de-7-de-dezembro-de-2021-368359651 |
| `aneel-ren-1000-2021-consolidada-2025-09.pdf` | REN 1.000/2021 — texto consolidado oficial da ANEEL (captura da página oficial em 29/09/2025) | ANEEL | https://www2.aneel.gov.br/cedoc/ren20211000.html ¹ |
| `alesp-lei-18403-2026.html` | Lei estadual (SP) nº 18.403, de 18/02/2026 (texto retificado em 20/02/2026) | ALESP | https://www.al.sp.gov.br/repositorio/legislacao/lei/2026/lei-18403-18.02.2026.html |
| `prefeitura-sp-lei-17336-2020.html` | Lei municipal (São Paulo) nº 17.336, de 30/03/2020 | Prefeitura de São Paulo — Catálogo de Legislação Municipal | https://legislacao.prefeitura.sp.gov.br/leis/lei-17336-de-30-de-marco-de-2020 |
| `cbpmesp-portaria-ccb-008-800-2025.pdf` | Portaria nº CCB-008/800/2025, de 12/11/2025 — consulta pública da proposta de alteração da IT nº 41 (DOE-SP 13/11/2025) | CBPMESP | https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232326891879.pdf |
| `cbpmesp-portaria-ccb-009-800-2025.pdf` | Portaria nº CCB-009/800/2025, de 12/11/2025 — publica o Parecer Técnico nº CCB-001/800/25 (orientações sobre SAVE) | CBPMESP | https://cbaplang.corpodebombeiros.sp.gov.br/Midias/638986232512702533.pdf |
| `cbpmesp-portaria-ccb-003-970-2026.html` (+ `.txt` ²) | Portaria nº CCB-003/970/2026, de 17/03/2026 — atualiza a IT nº 41 incluindo os itens 5.2 a 5.12 (SAVE); código de verificação DOE 2026.03.16.1.1.38.16.7.1.214.1709068 | CBPMESP / DOE-SP | https://doe.sp.gov.br/executivo/secretaria-da-seguranca-publica/portaria-n-003-970-2026-de-17-de-marco-de-2026-20260316113816712141709068 |

¹ A página oficial `www2.aneel.gov.br/cedoc` bloqueia acessos a partir de IPs de datacenter (Cloudflare 403),
o que impediu o download direto desta VM. O PDF preservado é uma impressão fiel da própria página oficial
(URL e data de captura — 29/09/2025, 09:39 — constam no cabeçalho/rodapé de todas as páginas), obtida via
mirror público (`cervam.com.br`). Cross-check feito contra uma segunda captura independente da mesma página,
hospedada por órgão público (SEMA-RS, captura de 24/01/2025:
https://sema.rs.gov.br/upload/arquivos/202501/24140257-resolucao-aneel-1000.pdf) — os arts. 550–560 são
idênticos nas duas capturas e idênticos ao texto original do DOU, **sem nenhuma anotação de alteração**
("Redação dada pela…"/"Incluído pela…") no Capítulo V do Título II, embora as capturas registrem 600+
anotações de alteração em outros pontos da norma.

² O `.txt` é extração de texto do HTML oficial do DOE (página carregada via JavaScript), gerada para
facilitar leitura e conferência offline; o HTML é a captura primária.

## Normas identificadas, texto não obtido

| Norma | Por quê | Como foi referenciada |
|---|---|---|
| ABNT NBR 5410 — Instalações elétricas de baixa tensão | Norma ABNT é paga (não há texto oficial gratuito) | Título oficial citado verbatim nos itens 5.2.1 da IT-41 (Portarias CCB-008/2025 e CCB-003/2026, preservadas acima) |
| ABNT NBR 17019 — Instalações elétricas de baixa tensão – Requisitos para instalações em locais especiais – Alimentação de veículos elétricos | idem | Itens 5.2.2 e 5.6.1 da IT-41 |
| ABNT NBR IEC 61851-1 — Sistema de recarga condutiva para veículos elétricos – Parte 1: Requisitos gerais | idem | Itens 5.2.3 e 5.3 da IT-41 |

O dossiê não afirma nada sobre o **conteúdo interno** dessas NBRs; só sobre o que a IT-41 exige delas.
