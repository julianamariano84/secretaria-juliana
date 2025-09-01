import os
import traceback
from scheduler.terapee_scraper import TerapeeScraper

s = TerapeeScraper(headless=True)
print('configured=', s.configured)
try:
    prof = os.getenv('PROFESSOR', 'prof1')
    start = os.getenv('START_TIME', '2025-09-01T10:00:00')
    end = os.getenv('END_TIME', '2025-09-01T11:00:00')
    res = s.check_availability(professional_id=prof, start_iso=start, end_iso=end)
    print('availability ->', res)
except Exception as e:
    traceback.print_exc()
    print('exception:', e)
