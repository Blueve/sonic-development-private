import threading

from lib import IOGenerator, PacketSizeTooSmallError
from lib import LocalHostCosumer
from lib import SonicTsHost, SonicTsHostCosumer,SonicTsHostProber

MAX_WAITING = 10

def LocalHostTest(packet_size, flow_size, duration):
    ''' This is for local testing '''
    generator = IOGenerator(packet_size, flow_size)
    cosumer = LocalHostCosumer()
    print("Local cosumer ready\n")

    try:
        probe_thread = threading.Thread(target=cosumer.probe, args=(duration,))
        probe_thread.start()
        avg_flow_size = generator.start(cosumer, duration)
        probe_thread.join()
        print("Test ended:")
        print("Avg Flow: {} KiB/s".format(avg_flow_size / 1024))
        print("Avg CPU%: {}".format(cosumer.avg_cpu_percent))
    except PacketSizeTooSmallError as e:
        print("Test failed, {}".format(e.message))

def SonicHostTest(host, ports, packet_size, flow_size, duration):
    ''' This is for SONiC console port testing '''
    generator = IOGenerator(packet_size, flow_size)
    sonic_host = SonicTsHost(host)
    probe_host = sonic_host.join()
    remote_hosts = []
    for port in ports:
        remote_hosts.append(sonic_host.connect(port, 9600))
    
    try:
        probe_thread = threading.Thread(target=probe_host.probe, args=(duration,))
        probe_thread.start()

        testing_threads = []
        for remote_host in remote_hosts:
            testing_threads.append(threading.Thread(target=generator.start, args=(remote_host, duration,)))
        
        for t in testing_threads:
            t.start()

        for t in testing_threads:
            t.join()
        probe_thread.join()
        print("Test ended:")
        print("Avg CPU%: {}".format(probe_host.avg_cpu_percent))
        return probe_host.avg_cpu_percent
    except PacketSizeTooSmallError as e:
        print("Test failed, {}".format(e.message))

if __name__ == '__main__':
    # LocalHostTest(packet_size=8*1024, flow_size=1024*1024, duration=10)
    start_port  = 1
    end_port    = 10
    packet_size = 1024
    flow_size   = 1024
    duration    = 60
    with open("result.csv", "w") as f:
        for i in range(start_port, end_port + 1):
            cpu = SonicHostTest("10.1.100.60", list(range(start_port, i)), packet_size, flow_size, duration)
            f.write("{},{},{},{}\n".format(i, packet_size, flow_size, cpu))
