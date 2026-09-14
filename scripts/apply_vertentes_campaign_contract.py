from pathlib import Path

path = Path('services/api/src/routes/campaigns.py')
text = path.read_text()

old = '''    if request.offer_profile_key:\n        from services.prospecting.default_profiles import get_default_registry\n\n        if get_default_registry().get(request.offer_profile_key) is None:\n            raise HTTPException(status_code=422, detail="Perfil de oferta não encontrado")\n\n    campaign = Campaign('''
new = '''    analysis_profile = request.analysis_profile\n    if request.offer_profile_key:\n        from services.prospecting.effective_offer_registry import get_effective_profile\n\n        profile = get_effective_profile(db, _org.id, request.offer_profile_key)\n        if profile is None:\n            raise HTTPException(status_code=422, detail="Vertente não encontrada nesta organização")\n        analysis_profile = (\n            "web_presence"\n            if profile.archetype in {"web_presence", "digital_systems"}\n            else "business_opportunity"\n        )\n\n    campaign = Campaign('''
assert text.count(old) == 1, 'create campaign contract not found'
text = text.replace(old, new, 1)

old = '        analysis_profile=request.analysis_profile,\n'
new = '        analysis_profile=analysis_profile,\n'
assert text.count(old) == 1, 'create analysis profile line not found'
text = text.replace(old, new, 1)

old = '''        from services.prospecting.default_profiles import get_default_registry\n        from services.prospecting.offer_profile import OfferProfileResolver\n        resolved_offer = OfferProfileResolver(get_default_registry()).resolve_campaign(\n            target_service=suggestion.get("target_service") or "",\n            target_segment=suggestion.get("target_segment") or "",\n        )'''
new = '''        from services.prospecting.effective_offer_registry import build_effective_registry\n        from services.prospecting.offer_profile import OfferProfileResolver\n        resolved_offer = OfferProfileResolver(build_effective_registry(db, _org.id)).resolve_campaign(\n            target_service=suggestion.get("target_service") or "",\n            target_segment=suggestion.get("target_segment") or "",\n        )'''
assert text.count(old) == 1, 'from-brief resolver contract not found'
text = text.replace(old, new, 1)

old = '''    if "offer_profile_key" in updates:\n        if updates["offer_profile_key"]:\n            from services.prospecting.default_profiles import get_default_registry\n\n            if get_default_registry().get(updates["offer_profile_key"]) is None:\n                raise HTTPException(status_code=422, detail="Perfil de oferta não encontrado")\n        campaign.offer_profile_key = updates["offer_profile_key"]\n\n    if "analysis_profile" in updates:\n        campaign.analysis_profile = updates["analysis_profile"]'''
new = '''    if "offer_profile_key" in updates:\n        if updates["offer_profile_key"]:\n            from services.prospecting.effective_offer_registry import get_effective_profile\n\n            profile = get_effective_profile(db, _org.id, updates["offer_profile_key"])\n            if profile is None:\n                raise HTTPException(status_code=422, detail="Vertente não encontrada nesta organização")\n            campaign.analysis_profile = (\n                "web_presence"\n                if profile.archetype in {"web_presence", "digital_systems"}\n                else "business_opportunity"\n            )\n        campaign.offer_profile_key = updates["offer_profile_key"]\n    elif "analysis_profile" in updates:\n        # Campanhas legadas sem Vertente explícita ainda aceitam o campo.\n        campaign.analysis_profile = updates["analysis_profile"]'''
assert text.count(old) == 1, 'patch campaign contract not found'
text = text.replace(old, new, 1)

path.write_text(text)
