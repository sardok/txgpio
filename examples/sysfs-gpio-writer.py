import sys
import ast
import os.path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from twisted.protocols import basic
from twisted.internet import protocol, stdio, reactor
from twisted.python import usage
from txgpio.sysfs import GPIO


class SysfsGPIOProtocol(protocol.Protocol):
    def connectionMade(self):
        self.factory.gpio_connected(self)


class SysfsGPIOFactory(protocol.Factory):
    protocol = SysfsGPIOProtocol

    def __init__(self, console_protocol):
        self.console_protocol = console_protocol

    def gpio_connected(self, gpio_conn):
        self.console_protocol.gpio_connected(gpio_conn)


class SysfsGPIOConsoleProtocol(basic.LineReceiver):
    delimiter = '\n'
    gpio_conn = None

    def gpio_connected(self, gpio_conn):
        self.gpio_conn = gpio_conn

    def lineReceived(self, line):
        stripped = line.strip()
        if stripped:
            try:
                value = ast.literal_eval(stripped)
            except ValueError:
                value = stripped
            data = '1' if value else '0'
            self.gpio_conn.transport.write(data)
        self.prompt()

    def connectionMade(self):
        text = '''
    Welcome to GPIO console.

    You may use 1, True, any kind of value that will result True in if check, to turn on the gpio.

    You may use 0, False or None to turn off the gpio.

    Ctrl + C to exit.
        '''
        self.sendLine(text)
        self.prompt()

    def prompt(self):
        gpio_num = self.gpio_conn.transport.gpio_no \
            if self.gpio_conn else 'Unknown'
        prompt = ' {}> '.format(gpio_num)
        self.transport.write(prompt)


class AppOptions(usage.Options):
    optParameters = [
        ['gpio_no', 'n', None, 'GPIO number'],
    ]


def main(argv):
    opts = AppOptions()
    opts.parseOptions(argv)
    console_protocol = SysfsGPIOConsoleProtocol()

    # Setup Sysfs GPIO
    factory = SysfsGPIOFactory(console_protocol)
    protocol = factory.buildProtocol(None)
    GPIO(protocol, reactor=reactor, direction='out', **opts)

    stdio.StandardIO(console_protocol)
    try:
        reactor.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
