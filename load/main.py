import threading
import time

from lib import IOGenerator, PacketSizeTooSmallError
from lib import SonicTsHost, SonicTsHostCosumer,SonicTsHostProber

MAX_WAITING = 10

def sonic_host_test(host, ports, packet_size, flow_size, duration):
    ''' This is for SONiC console port testing '''
    generator = IOGenerator(packet_size, flow_size, force=False)
    sonic_host = SonicTsHost(host)
    probe_host = sonic_host.join()
    remote_hosts = []
    for port in ports:
        if port >= 0:
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
            t.join(duration + MAX_WAITING)
        probe_thread.join(duration + MAX_WAITING)
        result = {}
        result["cpu"] = probe_host.avg_cpu_percent
        result["actual_flow_size"] = 0
        for remote_host in remote_hosts:
            remote_host.close()
            result["actual_flow_size"] += remote_host.actual_flow_size
        result["actual_flow_size"] /= len(remote_hosts) if len(remote_hosts) > 0 else 1
        return result
    except PacketSizeTooSmallError as e:
        print("Test failed, {}".format(e.message))

def batch_sonic_host_test(parameters):
    with open("result.csv", "w") as f:
        for p in parameters:
            start_port  = p['start_port']
            end_port    = p['end_port']
            packet_size = p['packet_size']
            flow_size   = p['flow_size']
            duration    = p['duration']
            step        = p['step']
            for i in range(start_port, end_port + 1, step):
                print("Test start: {}->{} {} {}".format(start_port, i, packet_size, flow_size))
                result = sonic_host_test("10.1.100.60", list(range(start_port, i + 1)), packet_size, flow_size, duration)
                f.write("{},{},{},{},{},{}\n".format(i + 1, packet_size, flow_size, duration, result["cpu"], result["actual_flow_size"]))
                print("{}, {}%, {} B/s".format(i, result["cpu"], result["actual_flow_size"]))
                time.sleep(5)

if __name__ == '__main__':
    parameters = []
    parameters.append({
        'start_port' : -1,
        'end_port'   : 48,
        'packet_size': 32,
        'flow_size'  : 100*1024,
        'duration'   : 60,
        'step'       : 4
    })
    parameters.append({
        'start_port' : -1,
        'end_port'   : 48,
        'packet_size': 128,
        'flow_size'  : 100*1024,
        'duration'   : 60,
        'step'       : 4
    })
    parameters.append({
        'start_port' : -1,
        'end_port'   : 48,
        'packet_size': 1024,
        'flow_size'  : 100*1024,
        'duration'   : 60,
        'step'       : 4
    })
    batch_sonic_host_test(parameters)