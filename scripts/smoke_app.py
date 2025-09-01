from app import create_app
app = create_app()
print('APP_CREATED', app.name)
print('ROUTES:', sorted([r.rule for r in app.url_map.iter_rules()]))
