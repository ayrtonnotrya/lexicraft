"""Config do Jupyter Lab para o estudo de ML (dev-only).

Sem token/senha (acesso local), raiz em research/notebooks.
Criado para evitar problemas de quoting de flags via sh -c no docker compose.
"""
c = get_config()  # noqa: F821

c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.allow_root = True
c.ServerApp.token = ""
c.ServerApp.password = ""
c.ServerApp.root_dir = "/app/research/notebooks"
