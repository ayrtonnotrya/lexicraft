# ⚙️ LexiCraft

> **Motor Agêntico Autônomo e Determinístico para Otimização Textual**

O **LexiCraft** é uma plataforma Full-Stack e orquestrador de IA operando em loop fechado (*closed-loop*). Seu objetivo é atuar como uma "linha de montagem" textual: ele redige, audita, pontua matematicamente e reescreve textos de forma autônoma até que atinjam o nível ótimo de qualidade, baseado em perfis e critérios estritamente customizáveis.

Em vez de confiar no empirismo ou em notas alucinadas por Large Language Models (LLMs), o LexiCraft isola a semântica da matemática. Os LLMs apenas apontam falhas; o código Python calcula o resultado utilizando a **Barganha de Nash Assimétrica**.

---

## ✨ Diferenciais Arquiteturais

O projeto foi desenhado sob a filosofia do **Monólito Majestoso (Majestic Monolith)**, unindo reatividade moderna no frontend a um backend assíncrono blindado contra falhas sistêmicas.

* 🧠 **Isolamento Matemático (Nash Bargaining):** O sistema não usa médias aritméticas, que mascaram falhas. A Barganha de Nash pune assimetrias severamente, forçando a IA a otimizar seus piores gargalos para ganhar eficiência marginal.
* 🛡️ **Resiliência Extrema (Regra dos 3 Strikes):** Falhas de rede (Timeouts, Erro 500), rate limits ou fugas de escopo consomem "strikes". O orquestrador tenta se recuperar silenciosamente sem quebrar o Worker. Três strikes seguidos abortam a iteração graciosamente.
* 🛑 **Degola Sumária e Rollback Automático:** O sistema monitora o ganho marginal de qualidade ($\Delta W$). Estagnação ou piora do texto (degradação) disparam um *Rollback* instantâneo, ejetando sempre o melhor *Snapshot* histórico.
* 🧬 **Anti-Alucinação (Pydantic Dinâmico):** Os contratos de saída dos LLMs são gerados em tempo de execução (*runtime*), impedindo que a IA invente IDs que não existem no banco de dados ou omita a avaliação de critérios por preguiça.
* ⏱️ **Ceifador de Zumbis (Garbage Collector):** Monitoramento contínuo via *heartbeats*. Se um container ou processo do Celery morrer abruptamente, o sistema detecta a falha e libera a interface do usuário, recuperando o progresso salvo.

---

## 🛠️ Tech Stack

* **Linguagem:** Python 3.12+
* **Backend Web:** Django 5.x
* **Orquestração Assíncrona:** Celery + Redis
* **Banco de Dados:** PostgreSQL
* **Integração LLM:** `httpx` (Assíncrono) + Pydantic (Structured Outputs)
* **Frontend:** Django Templates + HTMX + Tailwind CSS (Zero-SPA)
* **Testes:** Pytest, Pytest-Django (BDD & Mocks Determinísticos)

---

## 📚 Documentação Oficial

A arquitetura do LexiCraft é estritamente documentada. Para entender as engrenagens internas, consulte os documentos mestre na pasta `docs/`:

1. [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): Diagramas de infraestrutura, máquina de estados e pipeline.
2. [`DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md): Modelagem relacional, constraints e otimizações de índices.
3. [`MATH_SPEC.md`](docs/MATH_SPEC.md): Fórmulas da Barganha de Nash, cálculo de Epsilon e Isocusto.
4. [`LLM_SCHEMAS.md`](docs/LLM_SCHEMAS.md): Fábricas dinâmicas do Pydantic e mitigação de Prompt Injection.
5. [`AGENTS.md`](docs/AGENTS.md): Regras de negócio, fluxo do Worker e diretrizes para desenvolvimento.
6. [`TEST_SCENARIOS.md`](docs/TEST_SCENARIOS.md): A Bíblia BDD/TDD. Cenários de degradação, timeouts e limites.

---

## 🚀 Como Rodar o Projeto (Ambiente Local)

### Pré-requisitos
* Python 3.12+
* Redis (Rodando localmente ou via Docker)
* PostgreSQL (Recomendado, mas SQLite suportado para testes rápidos)

### 1. Clonar e Configurar Ambiente
```bash
git clone https://github.com/seu-usuario/lexicraft.git
cd lexicraft

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 2. Variáveis de Ambiente
Copie o arquivo de exemplo e preencha com suas credenciais:
```bash
cp .env.example .env
```
Certifique-se de configurar a `OPENAI_API_KEY` (ou chave compatível) e a `CELERY_BROKER_URL` (ex: `redis://localhost:6379/0`).

### 3. Banco de Dados e Migrações
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Iniciando os Serviços
Para o LexiCraft funcionar, você precisa de 3 processos rodando simultaneamente (recomenda-se usar abas separadas no terminal ou um gerenciador como o `honcho`/`tmux`):

**Terminal 1: Servidor Web (Django)**
```bash
python manage.py runserver
```

**Terminal 2: Worker do Celery (Orquestrador LLM)**
```bash
celery -A config worker --loglevel=info
```

**Terminal 3: Celery Beat (Ceifador de Zumbis)**
```bash
celery -A config beat --loglevel=info
```

Acesse `http://localhost:8000` para a interface principal e `http://localhost:8000/admin` para gerenciar os Perfis, Eixos e Prompts de Sistema.

---

## 🧪 Suíte de Testes

O projeto adota a política de **Zero Network** na esteira de testes. Nenhuma requisição real é feita a provedores de LLM durante os testes automatizados, garantindo 100% de determinismo.

Para rodar a suíte completa:
```bash
pytest
```
Para checar a cobertura de código:
```bash
pytest --cov=apps
```

---

## 📄 Licença

Este projeto está licenciado sob os termos da licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.