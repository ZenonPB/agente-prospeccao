from pathlib import Path

# Evita fuzzy match de uma única palavra genérica em campanhas legadas.
path = Path('services/workers/src/services/prospecting/offer_profile.py')
text = path.read_text()
old = '''            if best is not None:\n                return _ResolvedOffer(best, "vertical")\n'''
new = '''            # Um único token compartilhado (ex.: "manutenção") é ambíguo\n            # demais para escolher uma Vertente automaticamente. Nomes/taglines\n            # exatos já foram tratados acima; o fuzzy exige duas evidências.\n            if best is not None and best_score >= 2:\n                return _ResolvedOffer(best, "vertical")\n'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
path.write_text(text)

# Projeto mecânico: evidência central = operação + expansão/equipamento.
# Outros sinais técnicos e de contato complementam, sem diluir o Golden Path.
path = Path('services/workers/src/services/alphamec_vertente_equalization.py')
text = path.read_text()
old = '''    _set_signal_roles(\n        registry,\n        "mechanical_project",\n        positive=["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION", "EXPANDING_FACTORY", "NEW_EQUIPMENT", "HIRING_MECHANICAL_ENGINEER"],\n        optional_positive=["HAS_CNPJ", "HAS_BUSINESS_EMAIL", "HAS_PHONE"],\n        negative=["RETAIL_FOCUSED", "SERVICE_ONLY"],\n    )'''
new = '''    _set_signal_roles(\n        registry,\n        "mechanical_project",\n        positive=["HAS_PRODUCTION_LINE", "EXPANDING_FACTORY", "NEW_EQUIPMENT"],\n        optional_positive=[\n            "CUSTOM_MACHINERY", "AUTOMATION", "HIRING_MECHANICAL_ENGINEER",\n            "HAS_CNPJ", "HAS_BUSINESS_EMAIL", "HAS_PHONE",\n        ],\n        negative=["RETAIL_FOCUSED", "SERVICE_ONLY"],\n    )'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
path.write_text(text)
