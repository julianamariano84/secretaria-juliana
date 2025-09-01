from app import app
print('APP NAME:', app.name)
print('ROUTES:', [r.rule for r in app.url_map.iter_rules()])
