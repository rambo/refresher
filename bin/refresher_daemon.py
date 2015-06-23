#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Takes a config file with which points to a list of URLs and keeps hitting those urls within the configured intervals"""
from __future__ import with_statement
from __future__ import print_function
import functools
import logging
import yaml
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPError

LOGLEVEL = logging.INFO

class controller(object):
    config = {}
    pcbs = [] # List of active PeriodicCallback instances

    def __init__(self, config_file, mainloop):
        self.config_file = config_file
        self.mainloop = mainloop
        self.reload()

    def hook_signals(self):
        """Hooks POSIX signals to correct callbacks, call only from the main thread!"""
        import signal as posixsignal
        posixsignal.signal(posixsignal.SIGTERM, self.quit)
        posixsignal.signal(posixsignal.SIGQUIT, self.quit)
        posixsignal.signal(posixsignal.SIGHUP, self.reload)

    def reload(self, *args):
        """Reloads the configuration, will stop any and all periodic callbacks in flight"""
        # Stop the old ones
        for pcb in self.pcbs:
            pcb.stop()
        # And clean the list
        self.pcbs = []
        
        with open(self.config_file) as f:
            self.config = yaml.load(f)
        logging.getLogger().setLevel(self.config['log_level'])
        # Allow 1.5 times batch_size clients in the AsyncHTTPClient backend
        AsyncHTTPClient.configure(None, max_clients=int(self.config['batch_size']*1.5))

        for listinfo in self.config['urllists']:
            interval = self.config['default_interval']
            if listinfo.has_key('interval'):
                interval = listinfo['interval']

            urls = []
            if listinfo.has_key('file'):
                with open(listinfo['file']) as f:
                    # Make sure the whitespace is stripped
                    urls = [ line.strip() for line in f ]
            else:
                urls = listinfo['urls']
            
            batch_no = 0
            i = 0
            for url in urls:
                # Skip empty ones
                if not url:
                    continue
                # Also skip "commented out" lines
                if url.startswith('#'):
                    continue
                delay = batch_no * self.config['stagger_time']
                self.mainloop.call_later(delay, functools.partial(self.create_pcb, interval, url))
                i += 1
                if ((i % self.config['batch_size']) == 0):
                    batch_no += 1

    def quit(self, *args):
        self.mainloop.stop()

    def run(self):
        self.mainloop.start()

    def create_pcb(self, interval, url):
        """Calls the callback immediately and then schedules a PeriodicCallback for it with given interval"""
        logging.debug("create_pcb for %s called (interval %s), current time %s" % (url, interval, self.mainloop.time()))
        callback = functools.partial(self.fetcher, url)
        self.mainloop.spawn_callback(callback)
        pcb = PeriodicCallback(callback, int(interval*1000))
        pcb.start()
        self.pcbs.append(pcb)

    @gen.coroutine
    def fetcher(self, url):
        """Asynchronously fetches the URL"""
        logging.debug("Fetcher for %s called, current time %s" % (url, self.mainloop.time()))
        try:
            response = yield AsyncHTTPClient().fetch(url, request_timeout=self.config['http_timeout'])
            if response.error:
                logging.warning("Got error %s when fetching %s" % (response.error, url))
            else:
                logging.info("Fetched %s in %s seconds" % (url, response.request_time))
        except HTTPError, e:
            logging.warning("Got error %s when fetching %s" % (e.status_code, url))
        except Exception, e:
            #logging.error("Got exception when fetching %s" % (url))
            logging.exception("Got exception when fetching %s" % (url), e)
        pass



if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: refresher_daemon.py config.yml")
        sys.exit(1)
    # TODO: add a bsic formatter that gives timestamps etc
    logging.basicConfig(level=LOGLEVEL, stream=sys.stdout, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    loop = IOLoop.instance()
    instance = controller(sys.argv[1], loop)
    instance.hook_signals()
    try:
        instance.run()
    except KeyboardInterrupt:
        instance.quit()
