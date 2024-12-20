#!/usr/bin/python3
'''
Query the TrueNAS server for new alerts and send notifications
by email and to Ntfy. Then dismiss the alerts.
'''


from datetime import datetime as dt
from typing import List
from logging.handlers import RotatingFileHandler

import logging
import os
import time

from dotenv import load_dotenv

import requests
from requests import Response


load_dotenv()

# TrueNAS properties
TRUENAS_SERVER: str       = 'https://truenas.jleonr.duckdns.org'
TRUENAS_TOKEN: str        = os.getenv('TRUENAS_TOKEN')
TRUENAS_ALERTS_PATH: str  = 'api/v2.0/alert/list'
TRUENAS_DISMISS_PATH: str = 'api/v2.0/alert/dismiss'

# Ntfy properties
NTFY_SERVER: str = 'https://ntfy.jleonr.duckdns.org'
NTFY_TOKEN: str  = os.getenv('NTFY_TOKEN')
NTFY_TOPIC: str  = 'truenas_alerts'

true_nas_headers: dict = {
    'Authorization': f'Bearer {TRUENAS_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}


def get_truenas_alerts() -> None:
    '''
    Query the TrueNAS server for alerts and send push notifications.
    '''

    truenas_response: Response = requests.get(
        url=f'{TRUENAS_SERVER}/{TRUENAS_ALERTS_PATH}',
        headers=true_nas_headers,
        timeout=5
    )

    if truenas_response.status_code == 200:
        content: List[dict] = truenas_response.json()

        if not content:
            logging.info('No new alerts since the last fetch')
            return

        logging.info('Fetched %d alerts', len(content))

        # Sort alerts by date
        for alert in sorted(content, key=lambda x: x['datetime']['$date']):
            if not alert['dismissed']:
                title: str = 'TrueNAS Alerts'

                if alert['level'] != 'INFO':
                    tags: str = 'rotating_light,bangbang'
                else:
                    tags: str = 'floppy_disk,bell'

                alert_date: int = alert['datetime']['$date']
                at: str = dt.fromtimestamp(
                    alert_date/1000).strftime('%Y-%m-%d %H:%M:%S')

                message: str = f"Alert class: {alert['klass']}\n" \
                               f"Alert level: {alert['level']}\n" \
                               f"At: {at}\n" \
                               f"Message: {alert['formatted']}"

                ntfy_headers: dict = {
                    'Authorization': f'Bearer {NTFY_TOKEN}',
                    'Title': title,
                    'Tags': tags
                }

                ntfy_response: Response = requests.post(
                    url=f'{NTFY_SERVER}/{NTFY_TOPIC}',
                    data=message,
                    headers=ntfy_headers,
                    timeout=5
                )

                if ntfy_response.status_code != 200:
                    logging.error('Error sending TrueNAS alert to Ntfy. Status code: %d. Reason: %s',
                                  ntfy_response.status_code,
                                  ntfy_response.reason)

                # Wait 2 seconds before sending another notification
                # to not spam the email/Ntfy servers.
                time.sleep(2)

                # Don't dismiss error alerts so I can take a look
                # on the server
                if alert['level'] == 'INFO':
                    dismiss_response: Response = requests.post(
                        url=f"{TRUENAS_SERVER}/{TRUENAS_DISMISS_PATH}",
                        json=str(alert['uuid']),
                        headers=true_nas_headers,
                        timeout=5
                    )

                    if dismiss_response.status_code != 200:
                        logging.error('Error dismissing TrueNAS alert. Status code: %d. Reason: %s',
                                      dismiss_response.status_code,
                                      dismiss_response.reason)

        logging.info('All fetched alerts have been processed.')

    else:
        logging.error('Error querying TrueNAS alerts. Status code: %d. Reason: %s',
                      truenas_response.status_code,
                      truenas_response.reason)

        ntfy_headers: dict = {
            'Authorization': f'Bearer {NTFY_TOKEN}',
            'Title': 'TrueNAS Alerts ERROR!',
            'Tags': 'rotating_light,bangbang'
        }

        error_msg: str = f"Error querying TrueNAS alerts.\n" \
                         f"Status code: {truenas_response.status_code}.\n" \
                         f"Reason: {truenas_response.reason}."

        requests.post(
            url=f'{NTFY_SERVER}/{NTFY_TOPIC}',
            headers=ntfy_headers,
            data=error_msg,
            timeout=5
        )


if __name__ == "__main__":
    LOGS_PATH: str = os.getenv('LOGS_PATH')
    logging.basicConfig(
        handlers=[RotatingFileHandler(
            LOGS_PATH, maxBytes=2000, backupCount=3, mode='w')],
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s'
    )

    get_truenas_alerts()
