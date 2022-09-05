from apscheduler.schedulers.background import BackgroundScheduler
# from .update_games import update_games 
from .update_picks import update_picks 

def start():
    scheduler = BackgroundScheduler()
    # scheduler.add_job(update_games, 'interval', seconds=500)
    scheduler.add_job(update_picks, 'interval', seconds=500)
    scheduler.start()