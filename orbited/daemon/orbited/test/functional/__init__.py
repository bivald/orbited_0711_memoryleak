import os
import re
import signal
import sys
import time

from orbited.test.resources.selenium import selenium

class TestingResource(object):
    
    def __init__(self, name_pattern):
        self.name_pattern = name_pattern
        self._path = None
    
    def _get_resources_dir(self):
        functional_test_dir = os.path.abspath(os.path.dirname(__file__))
        orbited_test_dir = os.path.normpath(os.path.join(functional_test_dir,
                                                          '..'))
        resources_dir = os.path.join(orbited_test_dir, 'resources')
        return resources_dir
    
    def _select_resource(self):
        resources_dir = self._get_resources_dir()
        resources = os.listdir(resources_dir)
        candidates = [name for name in resources 
                      if re.match(self.name_pattern, name)]
        assert candidates, \
            "could not find resource matching %s in %s; found:\n%s" % \
            (self.name_pattern, resources_dir, '\n'.join(candidates))
        return os.path.join(resources_dir, max(candidates))
    
    @property
    def path(self):
        if self._path is None:
            self._path = self._select_resource()
        return self._path

class InProcessServer(object):
    
    def start(self):
        command, args = self.command.split(' ', 1)
        print "running command [%s] with args [%r]" % (command, args)
        self.pid = os.spawnvp(os.P_NOWAIT, command, args)
        time.sleep(2)
    
    def stop(self):
        os.kill(self.pid, signal.SIGINT)

class OrbitedServer(InProcessServer):
    config_file = TestingResource(r'orbited-debug.cfg')
    command = "orbited -c %s" % config_file.path

class SeleniumRCServer(InProcessServer):
    server_jar = TestingResource(r'selenium-server-standalone-\S+.jar')
    command = "java -jar %s" % server_jar.path

orbited = OrbitedServer()
selenium_rc = SeleniumRCServer()

# def setup():
#     orbited.start()
#     selenium_rc.start()
    
# def teardown():
#     selenium_rc.stop()
#     orbited.stop()

class TCPSocketTestCase(object):
    
    def test_tcp_socket(self):
        BROWSERS = ["*firefox",
                    ]
        
        for browser in BROWSERS:
            yield self._tcp_socket_test, browser
    
    def _tcp_socket_test(self, browser):
        sel = selenium('localhost', 4444, browser, "http://%s:8000/" % self.domain)
        sel.start()
        
        sel.open("/static/tests/")
        sel.click("link=%s" % self.label)
        sel.wait_for_page_to_load("30000")
        time.sleep(0.5)
        assert sel.is_text_present("TEST SUMMARY")
        time.sleep(0.5)
        assert sel.is_text_present("5 tests in 1 groups")
        assert sel.is_text_present("0 errors")
        assert sel.is_text_present("0 failures")
        
        sel.stop()
