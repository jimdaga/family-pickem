from apscheduler.schedulers.background import BackgroundScheduler
# from .update_games import update_games 
# from .update_picks import update_picks 
import os

import logging
logger = logging.getLogger(__name__)

def start():
    if os.environ.get('RUN_MAIN'):
        scheduler = BackgroundScheduler()
        # scheduler.add_job(update_games, 'interval', seconds=60)
        # scheduler.add_job(update_picks, 'interval', seconds=60)
        # scheduler.start()