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
Certifique-se de configurar a `OPENAI_API_KEY` do provedor **OpenCode Go** (endpoint OpenAI-Compatible em `OPENAI_BASE_URL`, default `https://opencode.ai/zen/go/v1`) e a `CELERY_BROKER_URL` (ex: `redis://localhost:6379/0`). O modelo global fallback é definido em `DEFAULT_MODEL_NAME` (ex: `deepseek-v4-flash`); cada `ProfileConfig` pode sobrescrever com um `model_name` próprio.

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

## 🐳 Rodando com Docker (Recomendado)

A aplicação é totalmente conteinerizada com um **único `docker-compose.yml`** que sobe os 5 serviços: `db` (PostgreSQL), `redis` (broker), `web` (Django + gunicorn), `worker` (Celery) e `beat` (Ceifador de Zumbis). Um arquivo opcional `docker-compose.override.yml` ativa o **modo de desenvolvimento** (bind-mount do código-fonte + `runserver` com auto-reload + porta `8000` exposta), carregado automaticamente apenas em execuções locais — produção não é afetada.

### Pré-requisitos
* [Docker](https://docs.docker.com/engine/install/) + [Docker Compose](https://docs.docker.com/compose/install/) (ou Docker Desktop)

### 1. Configurar o ambiente
```bash
cp .env.example .env
# Preencha OPENAI_API_KEY (chave do provedor OpenCode Go), APP_ENV, credenciais e limites
```

> O serviço `web` ingressa numa rede externa chamada `web` (reverse proxy) para exposição via domínio/TLS. Crie-a antes do primeiro `up` se for usá-la:
> ```bash
> docker network create web
> ```

### 2. Subir a stack
```bash
docker compose up --build
# Em segundo plano:
docker compose up -d --build
```

### 3. Acessar
* Interface: http://localhost:8000
* Admin: http://localhost:8000/admin (superusuário `admin` / `admin123`, criado pelo seeder)

### Controlando desenvolvimento vs produção
Um único compose atende os dois ambientes via `.env`:

| Variável | `development` | `production` |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `DEBUG` | `true` | `false` |
| `SECRET_KEY` | qualquer valor | valor forte secreto |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | domínio(s) real(is) |

> O modo `development` é **fiel a produção**: também usa PostgreSQL + Redis reais e worker/beat separados, para que o loop agêntico seja testado de verdade. A diferença para `production` é apenas o `DEBUG`.

### Comportamentos automáticos
* **Migrações:** `python manage.py migrate` roda no start do `web`.
* **Seeder:** `python manage.py seed_profiles` roda no start (idempotente — cria os 7 perfis e o admin, sem resetar senha de admin existente).
* **Estáticos:** `collectstatic` + **WhiteNoise** servem os assets do admin sem nginx extra.

#### Perfis out-of-the-box (seeder)
O `seed_profiles` popula 7 perfis de geração prontos para uso:
1. **E-mail Corporativo de Alto Impacto** — clareza, tom profissional e CTA.
2. **Carta de Amor** — carga emocional, criatividade poética e fluidez.
3. **Trabalho de Escola (Ensaio Acadêmico)** — rigor gramatical, coesão e densidade argumentativa.
4. **Engenheiro de Prompts Sênior (Meta-Prompting)** — meta-prompts arquiteturais com delimitadores XML, restrições negativas e Chain-of-Thought.
5. **Engenheiro de Prompts Pleno (Meta-Prompting)** — versão intermediária com concisão equilibrada.
6. **Engenheiro de Prompts Júnior (Meta-Prompting)** — versão mínima com frugalidade de tokens.
7. **Refatoração de README.md** — especializado em clareza de proposta de valor, escaneabilidade Markdown, tom anti-fluff e delimitação de escopo.

### Comandos úteis
```bash
docker compose logs -f web      # logs do servidor
docker compose logs -f worker   # logs do loop agêntico
docker compose ps               # status dos serviços
docker compose down             # derruba a stack
docker compose down -v          # derruba e apaga volumes (dados)
```

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