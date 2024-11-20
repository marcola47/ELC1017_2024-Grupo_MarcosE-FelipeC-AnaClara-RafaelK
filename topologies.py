# topologies.py
import random
from collections import defaultdict
from mininet.node import OVSKernelSwitch
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel

class LineTopo(Topo):
    def build(self):
        print("Creating line topology")
        hosts_count = 10
        hosts = [self.addHost('h{}'.format(i)) for i in range(1, hosts_count + 1)] 
        switches = [self.addSwitch('s{}'.format(i)) for i in range(1, hosts_count)] 

        for i in range(hosts_count - 1):
            self.addLink(hosts[i], switches[i], delay='{}ms'.format(random.randint(1, 10)))

            if i < hosts_count - 2:
                self.addLink(switches[i], switches[i + 1], delay='{}ms'.format(random.randint(1, 100)))

        self.addLink(switches[len(switches) - 1], hosts[len(hosts) - 1], delay='{}ms'.format(random.randint(1, 10)))
        print("Done creating line topology")


class RingTopo(Topo):
    def build(self):
        print("Creating ring topology")
        hosts_count = 10
        hosts = [self.addHost('h{}'.format(i)) for i in range(1, hosts_count + 1)] 
        switches = [self.addSwitch('s{}'.format(i), cls=OVSKernelSwitch) for i in range(1, hosts_count + 1)]
        
        for i in range(hosts_count):
            self.addLink(hosts[i], switches[i], delay='{}ms'.format(random.randint(1, 10)))
            self.addLink(switches[i], switches[(i + 1) % hosts_count], delay='{}ms'.format(random.randint(1, 100)))

        print("Done creating ring topology")

class StarTopo(Topo):
    def build(self):
        print("Creating star topology")
        hosts_count = 10
        hosts = [self.addHost('h{}'.format(i)) for i in range(1, hosts_count + 1)] 
        switch = self.addSwitch('s1')

        for i in range(hosts_count):
            self.addLink(hosts[i], switch, delay='{}ms'.format(random.randint(1, 100)))

        print("Done creating star topology")

class MeshTopo(Topo):
    def build(self):
        print("Creating mesh topology")
        hosts_count = 10
        hosts = [self.addHost('h{}'.format(i)) for i in range(1, hosts_count + 1)] 

        for i in range(hosts_count):
            for j in range(i + 1, hosts_count):
                if j > i:
                    self.addLink(hosts[i], hosts[j], delay='{}ms'.format(random.randint(1, 100)))

        print("Done creating full mesh topology")

class HybridTopo(Topo):
    def build(self):
        print("Creating hybrid topology")
        switch_count = 3
        hosts_count = switch_count * 5
        hosts_per_switch = 5
        hosts = [self.addHost('h{}'.format(i)) for i in range(1, hosts_count + 1)] 
        switches = [self.addSwitch('s{}'.format(i)) for i in range(1, switch_count + 1)] 

        for i in range(switch_count - 1):
            self.addLink(switches[i], switches[i + 1], delay='{}ms'.format(random.randint(1, 100)))

        for i in range(hosts_count):
            switch = i // hosts_per_switch
            self.addLink(hosts[i], switches[switch], delay='{}ms'.format(random.randint(1, 10)))

        print("Done creating hybrid topology")

def create_network(topology):
    net = Mininet(topo=topology)
    net.start()

    if not net.hosts or (not isinstance(topology, MeshTopo) and not net.switches):
        net.stop()
        raise RuntimeError("Failed to initialize network or topology is empty.")

    print("Network initialized successfully with topology:", topology)
    print("Number of hosts:", len(net.hosts))
    print("Number of switches:", len(net.switches))

    link_delays = defaultdict(str)

    for link in net.links:
        delay = link.intf1.params.get('delay', None)
        if not delay:
            delay = link.intf2.params.get('delay', None)
        if delay:
            link_delays[link] = delay
        else:
            link_delays[link] = 'No delay'

    for link, delay in link_delays.items():
        print("Link {} - Delay: {}".format(link, delay))

    for host in net.hosts:
        print("Installing traceroute on {}".format(host.name))
        host.cmd('apt-get install -y traceroute')

    return net, link_delays


if __name__ == '__main__':
    setLogLevel('info')
