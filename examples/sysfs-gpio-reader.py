import sys
import os.path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from zope.interface import implements, Interface
from twisted.internet.protocol import Factory, Protocol, connectionDone
from twisted.internet import reactor
from twisted.python import log, usage
from txgpio.sysfs import GPIO


class SysfsGPIODevice(Protocol):
    def connectionMade(self):
        log.msg('Connection is made')

    def dataReceived(self, data):
        self.factory.on_receive(data)

    def connectionLost(self, reason=connectionDone):
        log.msg('Connection is lost')


class ISysfsGPIOFactory(Interface):
    def on_receive(self, data):
        """
        Called when message from device (connected by serial) or test server
        is ready.
        """


class SysfsGPIOFactory(Factory):
    implements(ISysfsGPIOFactory)

    protocol = SysfsGPIODevice

    def on_receive(self, data):
        log.msg('Read value: {}'.format(data))


class AppOptions(usage.Options):
    optParameters = [
        ['gpio_no', 'n', None, 'GPIO number'],
        ['edge', 'e', 'both', 'Edge mode (Options: [none, rising, falling, both])'],
        ['active_low', 'a', None, 'Active low value (Options: [0, 1]']
    ]


def main(argv):
    log.startLogging(sys.stdout)
    opts = AppOptions()
    opts.parseOptions(argv)
    factory = SysfsGPIOFactory()
    protocol = factory.buildProtocol(None)
    GPIO(protocol, reactor=reactor, **opts)
    try:
        reactor.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
