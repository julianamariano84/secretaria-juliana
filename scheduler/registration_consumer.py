"""Small consumer to process pending registrations and try to create patients in Terapee.

Run periodically or manually. In production, wire this to a scheduler or message queue.
"""
from webhook.registrations import list_pending, get_pending, mark_created
from scheduler.terapee_scraper import TerapeeScraper
import os


def process_all(dry_run: bool = False):
    items = list_pending()
    if not items:
        print('no pending registrations')
        return

    s = TerapeeScraper(headless=os.getenv('HEADLESS', 'True') == 'True')

    for rec in items:
        if rec.get('status') != 'pending':
            continue
        phone = rec.get('phone')
        print(f'processing {phone}')
        if dry_run:
            print('dry run: would create patient with:', rec.get('answers', {}))
            continue
        result = s.create_patient_from_registration(rec)
        if result.get('created'):
            mark_created(phone, created_info=result)
            print(f'created {phone}:', result)
        else:
            print(f'failed to create {phone}:', result)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--dry', action='store_true')
    args = p.parse_args()
    process_all(dry_run=args.dry)
