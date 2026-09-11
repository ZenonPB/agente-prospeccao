"""Genericity Test Harness (Task 2 do roadmap).

Contrato executável que impede que capabilities genéricas do core carreguem
lógica de uma vertical específica. Uma capability sob contrato deve funcionar
para Troféus/Eventos e Sistemas Web/ERP **sem branches por vertical no core** e
deve ser configurável, teoricamente, para Engenharia Mecânica.

Módulos:
- ``profiles``: as três fixtures de OfferProfile do contrato;
- ``contract``: execução paramétrica das capabilities e formato de saída;
- ``core_purity``: varredura estática (AST) + ratchet de violações conhecidas.
"""
