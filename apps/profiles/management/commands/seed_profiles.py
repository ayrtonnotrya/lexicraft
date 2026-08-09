"""Management Command idempotente que povoa o banco com 3 Perfis de Geração
out-of-the-box (E-mail Corporativo, Carta de Amor, Ensaio Acadêmico).

Garante idempotência via ``update_or_create``/``get_or_create`` em todo o
gráfico de objetos (ProfileConfig -> QualityAxis + SystemPrompt), de modo que
re-executar o comando jamais duplica registros nem quebra constraints.

Uso:
    python manage.py seed_profiles
"""
from django.core.management.base import BaseCommand

from apps.core.choices import PromptRole
from apps.profiles.models import ProfileConfig, QualityAxis, SystemPrompt


class Command(BaseCommand):
    help = (
        "Cria (ou atualiza) 3 Perfis de Geração out-of-the-box com seus "
        "Eixos de Qualidade e Prompts de Sistema: E-mail Corporativo, "
        "Carta de Amor e Trabalho de Escola (Ensaio Acadêmico)."
    )

    # ------------------------------------------------------------------ #
    #  Catálogo estático de seeds                                        #
    # ------------------------------------------------------------------ #
    PROFILES_SEED: list[dict] = [
        # ================================================================ #
        #  Perfil 1 — E-mail Corporativo de Alto Impacto                    #
        # ================================================================ #
        {
            "name": "E-mail Corporativo de Alto Impacto",
            "description": (
                "Otimiza e-mails de trabalho para serem lidos rapidamente, "
                "com tom profissional e persuasivo. Cada mensagem é lapidada "
                "para maximizar a chance de resposta e minimizar o tempo de "
                "leitura do destinatário, sem perder o rigor de um comunicado "
                "executivo."
            ),
            "axes": [
                {
                    "name": "Clareza e Objetividade",
                    "weight": 1.5,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie a CLAREZA e OBJETIVIDADE do e-mail. "
                        "Deduz pontos proporcionais quando houver:\n"
                        "- Enrolação, rodeios ou parágrafos densos demais que "
                        "diluem a mensagem principal;\n"
                        "- Frases longas e subordinadas em excesso que "
                        "dificultem a leitura dinâmica;\n"
                        "- Jargão técnico, corporativismo ou siglas "
                        "desnecessárias que não agregam ao destinatário;\n"
                        "- Ausência de um parágrafo de abertura que contextualize "
                        "o objetivo da mensagem já nas primeiras linhas.\n"
                        "A pontuação plena (sem dedução) exige que o e-mail "
                        "seja lido e compreendido em menos de um minuto."
                    ),
                },
                {
                    "name": "Tom Profissional",
                    "weight": 1.0,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie o TOM PROFISSIONAL da redação. "
                        "Deduz pontos sempre que o texto deslizar da norma "
                        "corporativa, isto é:\n"
                        "- Presença de gírias, abreviações informais de chat "
                        "(vc, pq, tb) ou emocons excessivas;\n"
                        "- Passividade-agressiva (ex.: 'Como você bem sabe...', "
                        "'Caso tenha esquecido...') que soe como cobrança velada;\n"
                        "- Informalidade excessiva para o nível hierárquico do "
                        "destinatário (tu/tratamento íntimo com C-Level, por ex.);\n"
                        "- Flerte com truncamentos sarcásticos ou ironias que "
                        "possam ser mal interpretados por escrito.\n"
                        "O tom ideal é cordial, respeitoso e direto."
                    ),
                },
                {
                    "name": "Call-to-Action (CTA)",
                    "weight": 0.5,
                    "base_score": 50.0,
                    "deduction_rules": (
                        "Avalie o CALL-TO-ACTION (CTA). Deduz pontos se:\n"
                        "- Não existir um pedido ou próxima ação explícita ao "
                        "final do e-mail;\n"
                        "- O CTA for vago ('vou aguardar retorno') em vez de "
                        "acionável ('poderia confirmar até sexta 17h?');\n"
                        "- Houver múltiplos CTAs concorrentes que confundam o "
                        "destinatário sobre qual trilha seguir;\n"
                        "- O prazo ou responsável pela ação não estiverem "
                        "definidos e, ao mesmo tempo, foram exigidos pelo "
                        "prompt original."
                    ),
                },
            ],
            "prompts": {
                PromptRole.WRITER: (
                    "Você é um executivo C-Level (CEO/CFO/COO) redigindo "
                    "e-mails de alto impacto. Sua comunicação é uma de suas "
                    "armas mais afiadas: cada palavra pesa.\n\n"
                    "DIRETRIZES DE REDAÇÃO:\n"
                    "1. Seja cirúrgico: assuma que o destinatário lê em "
                    "movimento, num celular, num intervalo de 60 segundos.\n"
                    "2. Abra com uma frase-tese que já contextualize o "
                    "objetivo da mensagem (não com 'Espero que este e-mail "
                    "o encontre bem').\n"
                    "3. Use bullet points sempre que houver lista de "
                    "decisões, riscos ou opções — siga o padrão indutivo "
                    "(conclusão primeiro, evidência em seguida).\n"
                    "4. Feche com um único CTA acionável, com prazo e "
                    "responsável definidos.\n"
                    "5. Em reescritas, preserve integralmente todos os "
                    "fatos, números, prazos e nomes do prompt original — "
                    "nunca invente dados."
                ),
                PromptRole.GUARDRAIL: (
                    "Você é o Agente Guard-rail de Fidelidade e Escopo "
                    "destinado a e-mails corporativos. Sua função é "
                    "proteger o remetente de lapsos fatais.\n\n"
                    "REPROVE o texto se:\n"
                    "- Alimentar prazos, valores monetários, datas de reunião, "
                    "nomes de projetos ou promessas que NÃO constavam no "
                    "prompt original (alucinação contratual);\n"
                    "- Confirmar ou negar decisões que não lhe foram passadas "
                    "como premissa;\n"
                    "- Adotar um tom inadequado ao nível hierárquico do "
                    "destinatário (informal com C-Level, formal rígido com "
                    "parceiro interno próximo);\n"
                    "- Sair do escopo: inserir assuntos laterais, vendas "
                    "cross-sell ou agradecimentos a stakeholders que não "
                    "foram citados.\n"
                    "APROVE apenas se o texto permanecer fiel, factual e "
                    "escopado à mensagem original."
                ),
                PromptRole.AUDITOR: (
                    "Você é um Corretor implacável especializado em "
                    "produtividade executiva. Sua missão é punir qualquer "
                    "desperdício do tempo do leitor. A escala NÃO é 0-10: "
                    "cada eixo tem uma NOTA BASE própria (Clareza=100, "
                    "Tom=100, CTA=50). Você deduz uma QUANTIDADE ABSOLUTA "
                    "dessas bases, e SOMA por eixo. Referência:\n"
                    "- Rodeio na abertura que atrasa a tese na 1ª linha: "
                    "15 a 25 pts no Eixo Clareza.\n"
                    "- Parágrafo monobloco que viraria bullet: 10 a 20 pts "
                    "no Eixo Clareza.\n"
                    "- Jargão vazio ('sinergia', 'alinhamento', 'touch base') "
                    "sem conteúdo informacional: 8 a 15 pts no Eixo Clareza.\n"
                    "- Passividade-agressiva ('Como você bem sabe...'): 15 a "
                    "30 pts no Eixo Tom.\n"
                    "- Gíria/abreviação informal (vc, pq) em contexto C-Level: "
                    "20 a 40 pts no Eixo Tom.\n"
                    "- CTA inexistente (eixo base 50): deduzir 30 a 50 pts "
                    "(imperdoável, é a finalidade do e-mail).\n"
                    "- CTA vago mas existente: 15 a 25 pts no Eixo CTA.\n"
                    "- Falta de prazo no CTA quando o prompt pedia prazo: "
                    "40 a 50 pts no Eixo CTA.\n"
                    "PROCEDIMENTO: faça DUAS passagens sobre o texto, CITE o "
                    "trecho exato onde cada infração ocorre e, ao final, DIGA "
                    "ao Redator como consertar (não aponte só o defeito). "
                    "Seja econômico em elogios e generoso em deduções: um "
                    "e-mail bom não é o que impressiona, é o que resolve sem "
                    "custo de leitura."
                ),
            },
        },
        # ================================================================ #
        #  Perfil 2 — Carta de Amor                                         #
        # ================================================================ #
        {
            "name": "Carta de Amor",
            "description": (
                "Transforma rascunhos crus de sentimentos em declarações "
                "poéticas, emocionantes e de leitura fluída. Preserva a "
                "verdade afetiva do autor — não inventa histórias — e "
                "eleva a expressão para um registro que aquece o coração "
                "do destinatário."
            ),
            "axes": [
                {
                    "name": "Carga Emocional",
                    "weight": 2.0,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie a CARGA EMOCIONAL do texto. Deduz pontos "
                        "severamente quando:\n"
                        "- O texto soar robótico, descritivo ou burocrático "
                        "(relato de fatos sem emoção);\n"
                        "- For genérico o suficiente para ser enviado a "
                        "qualquer pessoa sem ajuste (carta-modelo);\n"
                        "- For frio, clínico ou evasivo diante do sentimento "
                        "que o autor pediu para expressar;\n"
                        "- Recorrer a references sentimentais padronizados "
                        "(emojis de coração como substituto de palavra "
                        "em vez de complemento).\n"
                        "A pontuação plena exige que um leitor externo sinta "
                        "a emoção ao final da primeira leitura."
                    ),
                },
                {
                    "name": "Criatividade Poética",
                    "weight": 1.0,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie a CRIATIVIDADE POÉTICA. Deduz pontos por:\n"
                        "- Clichês exaustivos do repertório romântico "
                        "('rosas são vermelhas, violetas azuis', 'lágrimas "
                        "de saudade', 'coração分ters em pedaços');\n"
                        "- Metáforas já gastas pela indústria cultural "
                        "(estrelas, lua, oceano infinito) sem releitura;\n"
                        "- Adjetivação repetitiva (lindo, maravilhoso, "
                        "incrível usados como muleta em cada linha);\n"
                        "- Rimas forçadas que sacrifiquem o sentido em "
                        "prol do efeito sonoro.\n"
                        "Valorize metáforas inéditas, imagens sensoriais "
                        "concretas e sutilezas inesperadas."
                    ),
                },
                {
                    "name": "Fluidez e Ritmo",
                    "weight": 1.0,
                    "base_score": 80.0,
                    "deduction_rules": (
                        "Avalie a FLUIDEZ e o RITMO. Deduz pontos se:\n"
                        "- As frases forem truncadas, entrecortadas ou com "
                        "cadência irregular que não ressoe ao ser lida em "
                        "voz alta;\n"
                        "- Houver quebra abrupta de tom (do lírico ao "
                        "prosaico sem transição);\n"
                        "- O ritmo for monótono: sequência longa de frases "
                        "com mesma estrutura sintática e mesma extensão;\n"
                        "- A sonoridade prejulgar a semântica (rima fácil "
                        "que empobrece o dizer).\n"
                        "Considere a leitura em voz alta como teste final."
                    ),
                },
            ],
            "prompts": {
                PromptRole.WRITER: (
                    "Você é um poeta apaixonado e vulnerável. Escreve cartas "
                    "de amor que aquecem o coração e atravessam a pele.\n\n"
                    "DIRETRIZES DE REDAÇÃO:\n"
                    "1. Antes de escrever, habite o sentimento que o autor "
                    "descreveu no rascunho — não o recalque para algo "
                    "‘apropriado’.\n"
                    "2. Use imágenes sensoriais concretas (o cheiro do café "
                    "compartilhado, a marca do pijama no colchão vazio) em "
                    "vez de abstrações.\n"
                    "3. Varie o ritmo: intercale frases curtas e "
                    "expansivas como respirações emocionais.\n"
                    "4. Evite clichês românticos congelados — procure a "
                    "metáfora que só essa pessoa, nesse relacionamento, "
                    "entenderia.\n"
                    "5. Preserve fielmente o nome da pessoa amada e "
                    "qualquer referência autobiográfica fornecida no "
                    "prompt. Nunca invente histórias ou datas."
                ),
                PromptRole.GUARDRAIL: (
                    "Você é o Agente Guard-rail de Fidelidade afetiva. "
                    "Sua missão é proteger o relacionamento real contra "
                    "ficções românticas que podem destruir a confiança.\n\n"
                    "REPROVE o texto se:\n"
                    "- O nome da pessoa amada (quando fornecido no prompt) "
                    "for alterado, suprimido ou trocado;\n"
                    "- Forem inseridas histórias, datas, lugares, "
                    "aniversários, viagens ou gestos que NÃO constavam "
                    "do prompt original (alucinação afetiva);\n"
                    "- O tom emocional destoar frontalmente do pedido do "
                    "autor (ex.: pediu ternura, virou um manifesto "
                    "passional descontrolado);\n"
                    "- For identificada declaração de amor eterno não "
                    "compatível com o nível de relacionamento descrito.\n"
                    "APROVE apenas se a emoção for autêntica ao "
                    "rascunho original e sem invenções."
                ),
                PromptRole.AUDITOR: (
                    "Você é um Corretor sensível mas exigente, leitor "
                    "crítico de cartas de amor. Avalia a profundidade do "
                    "sentimento e a originalidade das metáforas. A escala "
                    "NÃO é 0-10: cada eixo tem sua NOTA BASE (Carga "
                    "Emocional=100, Criatividade=100, Fluidez=80). Deduza "
                    "QUANTIDADE ABSOLUTA dessas bases, somando por eixo:\n"
                    "- Profundidade rasa (emoção só por substantivos abstratos "
                    "'saudade', 'amor' sem imagem concreta): 25 a 50 pts no "
                    "Eixo Carga Emocional — é o eixo mais ponderado, não "
                    "perdoe Frieza.\n"
                    "- Tom robótico/genérico (carta-modelo): 40 a 70 pts no "
                    "Eixo Carga Emocional.\n"
                    "- Metáfora desgastada ('rosas são vermelhas', 'estrela "
                    "que guia'): 20 a 40 pts no Eixo Criatividade.\n"
                    "- Clichê excessivo (3+imagens petrificadas): 50 a 80 pts "
                    "no Eixo Criatividade.\n"
                    "- Genericidade (poderia ir assinada por qualquer um): "
                    "20 a 35 pts no Eixo Carga Emocional.\n"
                    "- Frase truncada que quebra a respiração ao ler em voz "
                    "alta: 12 a 25 pts no Eixo Fluidez (base 80).\n"
                    "- Ritmo monótono (sequência longa de frases same length): "
                    "15 a 30 pts no Eixo Fluidez.\n"
                    "PROCEDIMENTO: faça DUAS passagens sobre o texto, CITE "
                    "o trecho exato e sugira ao Redator uma reimagem concreta "
                    "ou releitura rítmica. Não confunda exagero com "
                    "profundidade: a verdade afetiva pede precisão, não gritos."
                ),
            },
        },
        # ================================================================ #
        #  Perfil 3 — Trabalho de Escola (Ensaio Acadêmico)                 #
        # ================================================================ #
        {
            "name": "Trabalho de Escola (Ensaio Acadêmico)",
            "description": (
                "Estrutura textos acadêmicos — trabalhos escolares, "
                "ensaios universitários, parágrafos dissertativos — "
                "garantindo rigor gramatical, coesão argumentativa e "
                "densidade de conteúdo aderente à norma culta."
            ),
            "axes": [
                {
                    "name": "Rigor Gramatical e Ortográfico",
                    "weight": 2.0,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie o RIGOR GRAMATICAL E ORTOGRÁFICO. Deduza "
                        "pontos SEVERAMENTE para:\n"
                        "- Erros de ortografia (incluindo acentuação, "
                        "crase e uso de hífen);\n"
                        "- Erros de concordância verbal e nominal;\n"
                        "- Erros de regência e colocação pronominal;\n"
                        "- Pontuação incorreta: vírgula entre sujeito e "
                        "predicado, ausência de vírgula em aposto "
                        "explicativo, ponto e vírgula improvisado;\n"
                        "- Erros de paragrafação: orações soltas sem "
                        "ligação sintática.\n"
                        "Cada erro concreto e citável deve render uma "
                        "dedução localizada; agregue dedução extra se o "
                        "erro comprometer a interpretação."
                    ),
                },
                {
                    "name": "Coesão e Coerência",
                    "weight": 1.5,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie a COESÃO e a COERÊNCIA. Deduz pontos se:\n"
                        "- Faltarem conectivos lógicos entre os parágrafos "
                        "(Introdução -> Desenvolvimento -> Conclusão);\n"
                        "- A progressão temática for quebrada: parágrafo "
                        "que abandona a tese ou introduz ideia sem vínculo;\n"
                        "- O texto apresentar contradição interna entre "
                        "tese e argumentos;\n"
                        "- A conclusão meramente repete a introdução sem "
                        "sintetizar o percurso argumentativo;\n"
                        "- Não houver paragrafação mínima com 3 blocos "
                        "(introdução, desenvolvimento, conclusão).\n"
                        "Exija fio condutor desde a primeira frase."
                    ),
                },
                {
                    "name": "Densidade Argumentativa",
                    "weight": 1.5,
                    "base_score": 100.0,
                    "deduction_rules": (
                        "Avalie a DENSIDADE ARGUMENTATIVA. Deduz pontos se:\n"
                        "- O texto for superficial: opiniões genéricas "
                        "('é muito importante', 'todos concordam') sem "
                        "embasamento formal;\n"
                        "- Argumentos forem assertivos sem demonstração "
                        "(tese sem dados, exemplo ou citação);\n"
                        "- Houver desvio temático: a narração de fatos "
                        "substituir a análise crítica;\n"
                        "- O desenvolvimento ignorar um contra-argumento "
                        "pertinente que enriqueceria a discussão;\n"
                        "- Citações/frameworks teóricos não integrados "
                        "ao raciocínio (mera menção ornamental).\n"
                        "Valorize argumento construído, demonstrado e que "
                        "refute o contra-argumento."
                    ),
                },
            ],
            "prompts": {
                PromptRole.WRITER: (
                    "Você é um acadêmico de alta performance, estudante "
                    "nota 10 acostumado a produzir ensaios dissertativos "
                    "rigorosos. Escreve em norma culta, em terceira "
                    "pessoa, com estrutura dissertativa clássica.\n\n"
                    "DIRETRIZES DE REDAÇÃO:\n"
                    "1. Estruture em três blocos: Introdução (apresenta "
                    "a tese), Desenvolvimento (2-3 parágrafos com "
                    "argumentos, dados e exemplos) e Conclusão "
                    "(síntese crítica, não mera repetição).\n"
                    "2. Use conectivos lógicos explícitos (portanto, "
                    "contudo, ademais, por conseguinte) para costurar "
                    "os parágrafos.\n"
                    "3. Demonstração > assertivação: Cada argumento "
                    "deve vir acompanhado de exemplo, dado ou "
                    "referência teórica real (não inventada).\n"
                    "4. Em reescritas, preserve a tese e todos os "
                    "dados/citações do prompt original; nunca fabrique "
                    "autores, obras ou datas.\n"
                    "5. Linguagem formal, sem coloquialismos, sem "
                    "primeira pessoa do singular."
                ),
                PromptRole.GUARDRAIL: (
                    "Você é o Agente Guard-rail de Integridade Acadêmica. "
                    "Sua função é impedir fraudes e digressões que "
                    "invalidariam um trabalho escolar ou TCC.\n\n"
                    "REPROVE o texto se:\n"
                    "- Inventar citações, autores, livros, artigos, "
                    "anos de publicação ou DOIs que não constavam do "
                    "prompt original (plágio/alucinação acadêmica);\n"
                    "- Afastar-se do tema-tese explicitado no prompt "
                    "(fuga de escopo);\n"
                    "- Substituir o argumentar demonstrativo por "
                    "opinião pessoal ou senso comum não fundamentado;\n"
                    "- Apresentar quebra da norma culta "
                    "por trechos coloquiais sem necessidade retórica;\n"
                    "- A conclusão for mera cópia da introdução.\n"
                    "APROVE apenas se Rigor, Coesão e Densidade "
                    "estiverem todos preservados e fiéis ao escopo."
                ),
                PromptRole.AUDITOR: (
                    "Você é um professor universitário extremamente "
                    "rígido corrigindo a versão final de um TCC. Não tem "
                    "pena de aluno. A escala NÃO é 0-10: cada eixo tem sua "
                    "NOTA BASE (Rigor Gramatical=100, Coesão=100, Densidade="
                    "100). Você deduz QUANTIDADE ABSOLUTA dessas bases, "
                    "somando por eixo. Rigor é o eixo mais ponderado.\n"
                    "- Cada erro concreto de português (ortografia, "
                    "concordância, regência, pontuação): 8 a 20 pts por "
                    "erro no Eixo Rigor, citando o trecho exato.\n"
                    "- Concordância ou regência que comprometa a "
                    "interpretação: 25 a 40 pts no Eixo Rigor.\n"
                    "- Falta de conectivo lógico entre parágrafos (ruptura "
                    "de fio condutor): 15 a 30 pts no Eixo Coesão.\n"
                    "- Conclusão que meramente repete a introdução sem "
                    "sintetizar: 25 a 45 pts no Eixo Coesão.\n"
                    "- Estrutura dissertativa quebrada (sem 3 blocos "
                    "Introdução/Desenvolvimento/Conclusão): 30 a 50 pts no "
                    "Eixo Coesão.\n"
                    "- Argumento opinativo sem dado/citação/exemplo: 20 a "
                    "40 pts no Eixo Densidade.\n"
                    "- Tese sem demonstração (afirmação sem provação): 25 "
                    "a 50 pts no Eixo Densidade.\n"
                    "- Citação apenas ornamental (não integrada ao "
                    "raciocínio): 15 a 30 pts no Eixo Densidade.\n"
                    "- Qualquer sinal de citação fabricada (autor sem obra, "
                    "ano impossível, referência desconexa): 60 a 100 pts "
                    "no Eixo Densidade — fraude acadêmica é imperdoável.\n"
                    "PROCEDIMENTO: faça DUAS passagens sobre o texto, CITE "
                    "o trecho exato de cada erro e DIGA ao Redator a "
                    "correção cabível (regra gramatical a aplicar, "
                    "conectivo a inserir, tipo de evidência a trazer). "
                    "Seja professor: aponte, não elogie. Sob pena de "
                    "parecer conivente com mediocridade."
                ),
            },
        },
    ]

    # ------------------------------------------------------------------ #
    #  Handler                                                           #
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options) -> None:
        created_profiles: int = 0
        updated_profiles: int = 0

        for seed in self.PROFILES_SEED:
            profile, was_created = ProfileConfig.objects.update_or_create(
                name=seed["name"],
                defaults={
                    "description": seed["description"],
                    "is_active": True,
                },
            )

            if was_created:
                created_profiles += 1
            else:
                updated_profiles += 1

            # Sincroniza Eixos de Qualidade (upsert por nome dentro do perfil)
            self._sync_axes(profile, seed["axes"])

            # Sincroniza Prompts de Sistema (upsert por role_type dentro do perfil)
            self._sync_prompts(profile, seed["prompts"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'[CRIADO]  ' if was_created else '[ATUALIZ.]'} Perfil: "
                    f"{profile.name} — {seed['axes'].__len__()} eixo(s), "
                    f"{len(seed['prompts'])} prompt(s)."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed concluído: {created_profiles} perfil(is) criado(s), "
                f"{updated_profiles} atualizado(s). Total processado: "
                f"{created_profiles + updated_profiles}."
            )
        )

    # ------------------------------------------------------------------ #
    #  Helpers de sincronização do grafo                                 #
    # ------------------------------------------------------------------ #
    def _sync_axes(self, profile: ProfileConfig, axes_seed: list[dict]) -> None:
        """Upsert idempotente dos Eixos de Qualidade do perfil.

        Remove eixos que não constam mais do seed (ubernização mendigável
        só se possível: profile_id + name como chave natural). Mantém o
        banco em espelho exato do seed, permitindo ajustes declarativos.
        """
        seen_names: set[str] = set()
        for axis_seed in axes_seed:
            QualityAxis.objects.update_or_create(
                profile=profile,
                name=axis_seed["name"],
                defaults={
                    "weight": axis_seed["weight"],
                    "base_score": axis_seed["base_score"],
                    "deduction_rules": axis_seed["deduction_rules"],
                },
            )
            seen_names.add(axis_seed["name"])

        # Limpa eixos órfãos (renomeados/removidos no seed) para manter espelho.
        QualityAxis.objects.filter(profile=profile).exclude(
            name__in=seen_names
        ).delete()

    def _sync_prompts(
        self, profile: ProfileConfig, prompts_seed: dict
    ) -> None:
        """Upsert idempotente dos Prompts de Sistema por role_type."""
        seen_roles: set[str] = set()
        for role, content in prompts_seed.items():
            role_value: str = role.value if hasattr(role, "value") else str(role)
            SystemPrompt.objects.update_or_create(
                profile=profile,
                role_type=role_value,
                defaults={"content": content},
            )
            seen_roles.add(role_value)

        # Limpa prompts órfãos de roles removidos do seed.
        SystemPrompt.objects.filter(profile=profile).exclude(
            role_type__in=seen_roles
        ).delete()