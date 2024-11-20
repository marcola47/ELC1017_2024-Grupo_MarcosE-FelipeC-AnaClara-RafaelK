# algorithms.py
import threading
import time
from collections import defaultdict, deque
from heapq import heappush, heappop
import copy
from scapy.all import *

class DistanceVector:
    def __init__(self, host, net, link_delays):
        self.host = host
        self.net = net
        self.link_delays = link_delays
        self.distance_vector = defaultdict(lambda: float('inf'))
        self.next_hop = {}
        self.neighbors = {}
        self.running = False
        self.lock = threading.Lock()

        self.distance_vector[self.host.name] = 0

        self._build_topology()

    def _get_connected_nodes(self, node_name):
        """Get all nodes connected to the given node"""
        connected = []

        for link in self.link_delays:
            node1, node2 = link.intf1.node.name, link.intf2.node.name
            if node_name == node1:
                connected.append((node2, float(self.link_delays[link].replace('ms', ''))))
            elif node_name == node2:
                connected.append((node1, float(self.link_delays[link].replace('ms', ''))))
        return connected

    def _build_topology(self):
        """Build understanding of network topology and initial distances using BFS"""
        visited = set()
        queue = deque([(self.host.name, 0)]) 

        while queue:
            current_node, current_delay = queue.popleft()
            if current_node in visited:
                continue

            visited.add(current_node)
            connected = self._get_connected_nodes(current_node)

            for next_node, link_delay in connected:
                total_delay = current_delay + link_delay

                if next_node.startswith('h'):
                    if next_node not in self.neighbors or total_delay < self.neighbors[next_node]:
                        self.neighbors[next_node] = total_delay
                        self.distance_vector[next_node] = total_delay
                        self.next_hop[next_node] = next_node

                if next_node.startswith('s') and next_node not in visited:
                    queue.append((next_node, total_delay))

    def _create_update_packet(self):
        """Create a distance vector update packet"""
        return {
            'source': self.host.name,
            'distances': dict(self.distance_vector)
        }

    def _process_update(self, update_packet):
        """Process received distance vector update"""
        source = update_packet['source']
        received_distances = update_packet['distances']

        with self.lock:
            updated = False
            direct_cost_to_source = self.neighbors.get(source, float('inf'))

            for dest, cost in received_distances.items():
                if dest != self.host.name and dest.startswith('h'):
                    new_cost = direct_cost_to_source + float(cost)
                    current_cost = self.distance_vector[dest]

                    if new_cost < current_cost:
                        self.distance_vector[dest] = new_cost
                        self.next_hop[dest] = source
                        updated = True

            return updated

    def _send_updates(self):
        """Send distance vector updates to neighbors"""
        update_packet = self._create_update_packet()

        for neighbor_name in self.neighbors:
            neighbor_host = self.net.getNodeByName(neighbor_name)
            if hasattr(neighbor_host, 'dv_instance'):
                neighbor_dv = neighbor_host.dv_instance
                neighbor_dv._process_update(update_packet)

    def start(self):
        """Start the distance vector algorithm"""
        self.running = True
        self.host.dv_instance = self
        thread = threading.Thread(target=self._run)
        thread.daemon = True
        thread.start()

    def stop(self):
        """Stop the distance vector algorithm"""
        self.running = False

    def _run(self):
        """Main loop for the distance vector algorithm"""
        update_interval = 1

        while self.running:
            self._send_updates()
            time.sleep(update_interval)

    def get_route(self, destination):
        """Get the route and total delay to a destination"""
        if destination not in self.distance_vector:
            return None, float('inf')

        return [self.host.name, destination], self.distance_vector[destination]

    def print_routing_table(self):
        """Print the current routing table"""
        print("\nRouting table for {}:".format(self.host.name))
        print("Destination\tTotal Delay")
        for dest in sorted(self.distance_vector.keys()):
            if dest != self.host.name and dest.startswith('h'):
                path, delay = self.get_route(dest)
                print("{}\t\t{:.1f}ms".format(dest, delay))

    @staticmethod
    def setup_distance_vector(dv_instances, net, link_delays):
        """Setup distance vector routing and store instances"""
        for host in net.hosts:
            dv = DistanceVector(host, net, link_delays)
            dv_instances[host.name] = dv
            dv.start()
            host.dv_instance = dv

    @staticmethod
    def cleanup_distance_vector(dv_instances):
        """Stop all distance vector instances"""
        for dv in dv_instances.values():
            dv.stop()

    @staticmethod
    def print_all_routing_tables(dv_instances):
        """Print routing tables from all hosts"""
        print("\n" + "=" * 40)
        print("FINAL ROUTING TABLES FOR ALL HOSTS")
        print("=" * 40)

        for host_name, dv in sorted(dv_instances.items()):
            dv.print_routing_table()
            print("-" * 40)

class LinkState:
    def __init__(self, host, net, link_delays):
        self.host = host
        self.net = net
        self.link_delays = link_delays
        self.topology = defaultdict(dict)
        self.shortest_paths = {}
        self.running = False
        self.lock = threading.Lock()
        self.sequence_number = 0
        
        self._build_initial_topology()
        self._dijkstra()

    def _get_connected_nodes(self, node_name):
        """Get all nodes connected to the given node"""
        connected = []
        for link in self.link_delays:
            node1, node2 = link.intf1.node.name, link.intf2.node.name
            if node_name == node1:
                delay = float(self.link_delays[link].replace('ms', ''))
                connected.append((node2, delay))
            elif node_name == node2:
                delay = float(self.link_delays[link].replace('ms', ''))
                connected.append((node1, delay))
        return connected

    def _build_initial_topology(self):
        """Build initial topology understanding using BFS"""
        visited = set()
        queue = deque([(self.host.name, 0)])
        
        while queue:
            current_node, current_delay = queue.popleft()
            if current_node in visited:
                continue
                
            visited.add(current_node)
            
            connected = self._get_connected_nodes(current_node)
            
            for next_node, link_delay in connected:
                self.topology[current_node][next_node] = link_delay
                self.topology[next_node][current_node] = link_delay
                
                if next_node.startswith('s') and next_node not in visited:
                    queue.append((next_node, current_delay + link_delay))

    def _dijkstra(self):
        """Compute shortest paths to all destinations"""
        with self.lock:
            distances = defaultdict(lambda: float('inf'))
            distances[self.host.name] = 0
            previous = {}
            pq = [(0, self.host.name)]
            visited = set()

            while pq:
                current_distance, current_node = heappop(pq)
                
                if current_node in visited:
                    continue
                    
                visited.add(current_node)
                
                for neighbor, weight in self.topology[current_node].items():
                    if neighbor in visited:
                        continue
                        
                    distance = current_distance + weight
                    
                    if distance < distances[neighbor]:
                        distances[neighbor] = distance
                        previous[neighbor] = current_node
                        heappush(pq, (distance, neighbor))

            self.shortest_paths.clear()
            for dest in distances:
                if dest != self.host.name and dest.startswith('h'):
                    path = []
                    current = dest
                    while current in previous:
                        path.append(current)
                        current = previous[current]
                    path.append(self.host.name)
                    path.reverse()
                    self.shortest_paths[dest] = {
                        'path': path,
                        'cost': distances[dest]
                    }

    def _create_lsa(self):
        """Create a Link State Advertisement"""
        with self.lock:
            return {
                'source': self.host.name,
                'seq_num': self.sequence_number,
                'links': dict(self.topology[self.host.name])
            }

    def _flood_lsa(self, lsa):
        """Flood LSA to neighbors"""
        visited = {self.host.name}
        queue = list(self.topology[self.host.name].keys())
        
        while queue:
            next_node = queue.pop(0)
            if next_node in visited:
                continue
                
            visited.add(next_node)
            node = self.net.getNodeByName(next_node)
            
            if hasattr(node, 'ls_instance'):
                node.ls_instance._process_lsa(copy.deepcopy(lsa))
                
                if next_node in self.topology:
                    queue.extend([n for n in self.topology[next_node] if n not in visited])

    def _process_lsa(self, lsa):
        """Process received LSA and update topology"""
        with self.lock:
            source = lsa['source']
            links = lsa['links']
            
            changed = False
            for dest, cost in links.items():
                if (dest not in self.topology[source] or 
                    self.topology[source][dest] != cost):
                    self.topology[source][dest] = cost
                    self.topology[dest][source] = cost
                    changed = True
            
            if changed:
                self._dijkstra()

    def start(self):
        """Start the link state algorithm"""
        self.running = True
        self.host.ls_instance = self
        threading.Thread(target=self._run).start()

    def stop(self):
        """Stop the link state algorithm"""
        self.running = False

    def _run(self):
        """Main loop for the link state algorithm"""
        update_interval = 1 
        
        while self.running:
            lsa = self._create_lsa()
            self.sequence_number += 1
            self._flood_lsa(lsa)
            time.sleep(update_interval)

    def get_route(self, destination):
        """Get the route and total delay to a destination"""
        if destination not in self.shortest_paths:
            return None, float('inf')
        
        path_info = self.shortest_paths[destination]
        return path_info['path'], path_info['cost']

    def print_routing_table(self):
        """Print the current routing table"""
        print("\nRouting table for {}:".format(self.host.name))
        print("Destination\tPath\t\tTotal Delay")
        
        if not self.shortest_paths:
            print("No paths found. Current topology:")
            for node, neighbors in self.topology.items():
                print("{}: {}".format(node, neighbors))
            return
        
        for dest in sorted(self.shortest_paths.keys()):
            path, delay = self.get_route(dest)
            path_str = ' -> '.join(str(node) for node in path)
            print("{}\t\t{}\t\t{:.1f}ms".format(dest, path_str, delay))


    @staticmethod
    def setup_link_state(ls_instances, net, link_delays):
        """Setup link state routing and store instances"""
        time.sleep(1)
        
        for host in net.hosts:
            ls = LinkState(host, net, link_delays)
            ls_instances[host.name] = ls
            ls.start()
            host.ls_instance = ls
        
        time.sleep(2)

    @staticmethod
    def cleanup_link_state(ls_instances):
        """Stop all link state instances"""
        for ls in ls_instances.values():
            ls.stop()

    @staticmethod
    def print_all_routing_tables(ls_instances):
        """Print routing tables from all hosts"""
        print("\n" + "="*40)
        print("FINAL ROUTING TABLES FOR ALL HOSTS")
        print("="*40)
        
        for host_name, ls in sorted(ls_instances.items()):
            ls.print_routing_table()
            print("-"*40)
