import os.path
import platform
from twisted.python import log
try:
    platform.linux_distribution()
    from select import epoll, EPOLLPRI, EPOLLOUT, EPOLLERR
except (AttributeError, ImportError):
    log.err('Unsupported platform! Linux is required to use sysfs-gpio')
    raise
from twisted.internet import abstract, fdesc
from txgpio.exceptions import InvalidArgument, UnsupportedSystem


class GPIO(abstract.FileDescriptor, object):
    """
    Gpio reader, writer based on SysFS gpio files.

    Reading mode:
    Reader descriptor is hooked into twisted's event loop by means of epoll
    with specific flags, documented here:
    https://www.kernel.org/doc/Documentation/gpio/sysfs.txt

    Writing mode:
    Sysfs descriptor events always return with ERROR flag enabled, from the
    event loop which prevents consuming the write buffer.
    Also, in order to write sysfs file(s), open-write-close operations should be
    followed, so there is no need to open the sysfs file and leave it open
    during the application's lifespan.
    Having said that, a pipe's writing endpoint is hooked into event loop,
    which is always ready for writing.
    When the data is available at write buffer, the relevant sysfs file is
    opened-written-closed.
    """

    connected = 1

    def __init__(self, protocol, gpio_no, direction='in', edge='both',
                 active_low=None, reactor=None, sysfs_gpio_dir=None):
        abstract.FileDescriptor.__init__(self, reactor)
        assert direction is not None

        self.protocol = protocol
        self.sysfs_gpio_dir = sysfs_gpio_dir or '/sys/class/gpio'
        if not os.path.exists(self.sysfs_gpio_dir):
            raise UnsupportedSystem(
                'Ensure that gpio sysfs is enabled in kernel.')

        self.gpio_no = gpio_no
        self.sysfs_gpio_node_dir = os.path.join(
            self.sysfs_gpio_dir, 'gpio{}'.format(gpio_no))
        self._gpio_node_exported = self._export_gpio(
            self.sysfs_gpio_dir, gpio_no, self.sysfs_gpio_node_dir)

        try:
            # Do the gpio configuration
            self.direction = self._configure_option(
                self.sysfs_gpio_node_dir, 'direction', direction, ['in', 'out'])
            if self.direction == 'in':
                self.edge = self._configure_option(
                    self.sysfs_gpio_node_dir, 'edge', edge,
                    ['none', 'rising', 'falling', 'both'])
                self.active_low = self._configure_option(
                    self.sysfs_gpio_node_dir, 'active_low', active_low, ['0', '1'])
        except (IOError, InvalidArgument):
            if self._gpio_node_exported:
                self._unexport_gpio(self.sysfs_gpio_dir, gpio_no)
            raise

        self._fds = self._open_files()
        self.protocol.makeConnection(self)
        if self.direction == 'in':
            self.startReading()
        else:
            self.startWriting()

    def _open_files(self):
        fds = {}
        if self.direction == 'in':
            ep = epoll()
            # About reading sysfs gpio nodes.
            # https://www.kernel.org/doc/Documentation/gpio/sysfs.txt
            gpio_node = self._open_gpio_node()
            flags = EPOLLPRI | EPOLLERR
            ep.register(gpio_node.fileno(), flags)

            fds['ep'] = ep
            fds['gpio_node'] = gpio_node
        else:
            # Create a pipe channel to use its writing endpoint.
            fds['pin'], fds['pout'] = os.pipe()
        return fds

    def _close_files(self):
        for fd in self._fds.values():
            try:
                fd.close()
            except AttributeError:
                os.close(fd)

    def _open_gpio_node(self):
        mode = 'r' if self.direction == 'in' else 'w'
        gpio_value_path = os.path.join(self.sysfs_gpio_node_dir, 'value')
        return open(gpio_value_path, mode)

    def _configure_option(self, gpio_dir, variable, value, options):
        if value is not None:
            value = value.lower()
            if value not in options:
                raise InvalidArgument(
                    'Invalid option {} (available options: {}).'
                    .format(value, ', '.join(options)))
            variable_path = os.path.join(gpio_dir, variable)
            with open(variable_path, 'w') as f:
                f.write(value)
            return value

    def _export_gpio(self, basedir, num, node_dir):
        if not os.path.exists(node_dir):
            path = os.path.join(basedir, 'export')
            with open(path, 'w') as f:
                f.write(num)
            return True

    def _unexport_gpio(self, basedir, num):
        if self._gpio_node_exported:
            path = os.path.join(basedir, 'unexport')
            with open(path, 'w') as f:
                f.write(num)

    def fileno(self):
        if self.direction == 'in':
            return self._fds['ep'].fileno()
        else:
            return self._fds['pout']

    def writeSomeData(self, data):
        if data and self.direction == 'out':
            if data not in ['1', '0']:
                raise InvalidArgument('Invalid value {}, it must be 1 or 0'
                                      .format(data))
            with self._open_gpio_node() as f:
                f.write(data)
            return len(data)

    def doRead(self):
        if self.direction == 'in':
            def _read_cb(data):
                return self.protocol.dataReceived(data.strip())

            f = self._fds['gpio_node']
            f.seek(0)
            return fdesc.readFromFD(f.fileno(), _read_cb)

    def connectionLost(self, reason):
        abstract.FileDescriptor.connectionLost(self, reason)
        self._close_files()
        if self._gpio_node_exported:
            self._unexport_gpio(self.sysfs_gpio_dir, self.gpio_no)
        self.protocol.connectionLost(reason)
