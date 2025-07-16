from scripts.app_log import app_log 


def run():
    log = app_log('test_ping_telegram')
    log.alert('Ping')