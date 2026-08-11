"""Módulo de ML (produção) do LexiCraft.

Contém as features, o detector humano-vs-IA e o carregamento/versionamento do
modelo. Este módulo é a única fonte de verdade em runtime; os notebooks em
`research/` IMPORTAM estas funções para evitar divergência treino/produção
(train/serve skew). A matemática de ponderação final permanece no
`apps/orchestrator/services/math_engine.py`.
"""
