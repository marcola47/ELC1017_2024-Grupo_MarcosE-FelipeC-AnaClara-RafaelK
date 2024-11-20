import unittest
import time
from mininet.log import setLogLevel
from topologies import LineTopo, RingTopo, StarTopo, MeshTopo, HybridTopo, create_network
from algorithms import DistanceVector
from collections import defaultdict
import threading
from scapy.all import sniff, IP

class TestRoutingAlgorithm(unittest.TestCase):
    def setUp(self):
        """Configuração inicial para cada teste"""
        setLogLevel('error')
        self.dv_instances = {}
        self.convergence_times = {}
        self.control_overhead = defaultdict(int)
        self.packet_drops = defaultdict(int)
        self.processing_delays = defaultdict(list)

    def tearDown(self):
        """Limpeza após cada teste"""
        if hasattr(self, 'net'):
            DistanceVector.cleanup_distance_vector(self.dv_instances)
            self.net.stop()

    def measure_convergence_time(self, topology_name):
        """Mede o tempo de convergência do algoritmo"""
        start_time = time.time()
        stable = False
        old_tables = {}

        while not stable and (time.time() - start_time) < 30:
            stable = True
            current_tables = {}

            for host_name, dv in self.dv_instances.items():
                current_tables[host_name] = dict(dv.distance_vector)

                if host_name in old_tables:
                    if old_tables[host_name] != current_tables[host_name]:
                        stable = False
                        break

            old_tables = current_tables.copy()
            time.sleep(0.5)

        convergence_time = time.time() - start_time
        self.convergence_times[topology_name] = convergence_time
        return convergence_time

    def measure_control_overhead(self, topology_name, duration=10):
        """Mede a sobrecarga de controle na rede"""
        def packet_callback(packet):
            if packet.haslayer(IP):
                self.control_overhead[topology_name] += len(packet)

        # Inicia captura de pacotes
        sniff(prn=packet_callback, timeout=duration)

        return self.control_overhead[topology_name]

    def measure_packet_drops(self, topology_name):
        """Mede a quantidade de pacotes dropados"""
        drops = 0

        hosts = self.net.hosts
        for src in hosts:
            for dst in hosts:
                if src != dst:
                    result = src.cmd('ping -c 1 -W 1 {}'.format(dst.IP()))
                    if '100% packet loss' in result:
                        drops += 1

        self.packet_drops[topology_name] = drops
        return drops

    def measure_processing_delay(self, topology_name):
        """Mede o atraso de processamento no encaminhamento dos pacotes"""
        delays = []

        hosts = self.net.hosts
        for src in hosts:
            for dst in hosts:
                if src != dst:
                    start_time = time.time()
                    route, delay = self.dv_instances[src.name].get_route(dst.name)
                    end_time = time.time()

                    processing_time = (end_time - start_time) * 1000
                    delays.append(processing_time)

        avg_delay = sum(delays) / len(delays) if delays else 0
        self.processing_delays[topology_name] = avg_delay
        return avg_delay

    def run_topology_test(self, topology_class, topology_name):
        """Executa todos os testes para uma topologia específica"""
        print("\nTestando topologia: {}".format(topology_name))

        topology = topology_class()
        self.net, link_delays = create_network(topology)
        DistanceVector.setup_distance_vector(self.dv_instances, self.net, link_delays)

        convergence_time = self.measure_convergence_time(topology_name)
        control_overhead = self.measure_control_overhead(topology_name)
        packet_drops = self.measure_packet_drops(topology_name)
        processing_delay = self.measure_processing_delay(topology_name)

        print("Resultados para {}:".format(topology_name))
        print("- Tempo de convergência: {:.2f} segundos".format(convergence_time))
        print("- Sobrecarga de controle: {} bytes".format(control_overhead))
        print("- Pacotes dropados: {}".format(packet_drops))
        print("- Atraso médio de processamento: {:.2f} ms".format(processing_delay))

        return convergence_time, control_overhead, packet_drops, processing_delay

    def test_line_topology(self):
        self.run_topology_test(LineTopo, "line")

    def test_ring_topology(self):
        self.run_topology_test(RingTopo, "ring")

    def test_star_topology(self):
        self.run_topology_test(StarTopo, "star")

    def test_mesh_topology(self):
        self.run_topology_test(MeshTopo, "mesh")

    def test_hybrid_topology(self):
        self.run_topology_test(HybridTopo, "hybrid")

    def write_report(self):
        """Gera relatório com os resultados dos testes"""
        report = """
        Relatório de Desempenho do Algoritmo de Roteamento
        ================================================

        Resumo por Topologia:
        """
        if hasattr(self, 'convergence_times') and self.convergence_times:
            for topology in self.convergence_times.keys():
                report += "\n{} TOPOLOGY:\n".format(topology.upper())
                report += "- Tempo de convergência: {:.2f} segundos\n".format(self.convergence_times[topology])
                report += "- Sobrecarga de controle: {} bytes\n".format(self.control_overhead[topology])
                report += "- Pacotes dropados: {}\n".format(self.packet_drops[topology])
                report += "- Atraso médio de processamento: {:.2f} ms\n".format(self.processing_delays[topology])

        with open('routing_performance_report.txt', 'w') as f:
            f.write(report)

if __name__ == '__main__':
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestRoutingAlgorithm)
    test_results = unittest.TextTestRunner(verbosity=2).run(test_suite)

    test_instance = TestRoutingAlgorithm()
    test_instance.write_report()
