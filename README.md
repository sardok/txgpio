## txgpio
Twisted-based asynchronous library for using GPIO (over Sysfs) implemented in pure python.

### Reading

#### Define protocol

```python
class SysfsGPIOProtocol(Protocol):

    def dataReceived(self, data):
        self.factory.on_receive(data)

```

#### Define factory

```python
class SysfsGPIOFactory(Factory):
    protocol = SysfsGPIOProtocol

    def on_receive(self, data):
        log.msg('Read value: {}'.format(data))
```

#### Create instances

```python
    factory = SysfsGPIOFactory()
    protocol = factory.buildProtocol(None)
    GPIO(protocol, reactor=reactor, gpio_no=21, edge='both')
```

#### Let the reactor run

```
reactor.run()
```

See ```examples/``` directory for reader & writer applications.
