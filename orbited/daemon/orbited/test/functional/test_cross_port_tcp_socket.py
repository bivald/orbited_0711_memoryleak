from selenium import selenium
import time, re

from orbited.test.functional import TCPSocketTestCase

class TestCrossPortTCPSocket(TCPSocketTestCase):
    domain = "xp.orbited"
    label = "Cross-Port"
