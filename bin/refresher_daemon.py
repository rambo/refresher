#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Takes a config file with which points to a list of URLs and keeps hitting those urls within the configured intervals"""
from __future__ import with_statement
from __future__ import print_function
import functools
import yaml
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen


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

        print("Config: %s" % repr(self.config))

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
            
            for url in urls:
                pcb = PeriodicCallback(functools.partial(self.fetcher, url) ,int(interval*1000))
                pcb.start()
                self.pcbs.append(pcb)

    def quit(self, *args):
        self.mainloop.stop()

    def run(self):
        self.mainloop.start()


    def fetcher(self, url):
        print("Fetcher for %s called" % url)
        pass

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: refresher_daemon.py config.yml")
        sys.exit(1)
    loop = IOLoop.instance()
    instance = controller(sys.argv[1], loop)
    instance.hook_signals()
    try:
        instance.run()
    except KeyboardInterrupt:
        instance.quit()
