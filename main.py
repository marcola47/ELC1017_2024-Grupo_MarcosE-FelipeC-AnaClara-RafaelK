# main.py
import argparse
from mininet.log import setLogLevel
from mininet.cli import CLI
from topologies import LineTopo, RingTopo, StarTopo, MeshTopo, HybridTopo, create_network
from algorithms import DistanceVector, LinkState

dv_instances = {}
ls_instances = {}

def parse_arguments():
    parser = argparse.ArgumentParser(description="Run a network topology with a routing algorithm")
    parser.add_argument('-t', '--topology', required=True, choices=['line', 'ring', 'star', 'mesh', 'hybrid'], help="Choose a topology")
    parser.add_argument('-a', '--algorithm', required=True, choices=['distance-vector', 'link-state'], help="Choose a routing algorithm")
    return parser.parse_args()

def get_topology(name):
    topologies = {
        'line': LineTopo,
        'ring': RingTopo,
        'star': StarTopo,
        'mesh': MeshTopo,
        'hybrid': HybridTopo
    }
    try:
        return topologies[name]()
    except KeyError:
        print("Invalid topology")
        exit(1)


if __name__ == '__main__':
    setLogLevel('info')
    args = parse_arguments()
    topology = get_topology(args.topology)
    algorithm = args.algorithm
    net, link_delays = create_network(topology)

    if algorithm == 'distance-vector':
        DistanceVector.setup_distance_vector(dv_instances, net, link_delays)

    else:
        LinkState.setup_link_state(ls_instances, net, link_delays)

    try:
        CLI(net)
    finally:
        if algorithm == 'distance-vector':
            DistanceVector.print_all_routing_tables(dv_instances)
            DistanceVector.cleanup_distance_vector(dv_instances)
        elif algorithm == 'link-state':
            LinkState.print_all_routing_tables(ls_instances)
            LinkState.cleanup_link_state(ls_instances)
        
        print("\nStopping Mininet network...")
        net.stop()
        print("Mininet network stopped.")