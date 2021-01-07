import subprocess
import pexpect
import psutil
import time
import random
import string

from os import fpathconf, linesep

class IOGenerator(object):
    """
    The IO generator.
    The generator can let user to generate IO with specific need.
    """

    def __init__(self, packet_size, flow_size, force=True):
        self.packet_size = packet_size
        self.buffer_size = fpathconf(0, 'PC_MAX_CANON') - len(linesep)
        self.flow_size   = flow_size
        self.force       = force

    def start(self, target, duration):
        start_time = time.time()
        total_load = 0
        packet_content = self.generate_random_string()
        packet_buffers = [packet_content[i:i+self.buffer_size] for i in range(0, len(packet_content), self.buffer_size)]
        while True:
            if time.time() - start_time > duration:
                break

            # hand over traffic
            target.receive(packet_buffers)
            total_load += self.packet_size

            # traffic control
            # flow_size   = total_load / (elapsed_time + delay_time)
            elapsed_time = time.time() - start_time
            delay_time   = (total_load - self.flow_size * elapsed_time) / self.flow_size
            if self.force and delay_time < 0:
                raise PacketSizeTooSmallError("The packet_size is too small, it should be larger than {}".format(int(self.flow_size * elapsed_time)))
            elif delay_time > 0:
                time.sleep(delay_time)
        actual_flow_size = total_load / (time.time() - start_time)
        target.actual_flow_size = actual_flow_size
        return actual_flow_size
    
    def generate_random_string(self):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(self.packet_size))

class LocalHostCosumer(object):
    def receive(self, packet_content):
        print(packet_content)
    
    def probe(self, duration):
        self.avg_cpu_percent = psutil.cpu_percent(interval=duration)

class SonicTsHost(object):
    PURE_SSH_CMD_PATTERN = "ssh {}@{}"
    SSH_CMD_PATTERN = "ssh {}@{} \"{}\""
    TTY_CMD_PATTERN = "sudo picocom -b {} {}{}"

    def __init__(self, hostname, user="admin", pwd="YourPaSsWoRd", tty_prefix="/dev/ttyUSB"):
        self.hostname   = hostname
        self.user       = user
        self.pwd        = pwd
        self.tty_prefix = tty_prefix
    
    def connect(self, line_num, baud):
        tty_cmd = SonicTsHost.TTY_CMD_PATTERN.format(baud, self.tty_prefix, line_num)
        ssh_cmd = SonicTsHost.SSH_CMD_PATTERN.format(self.user, self.hostname, tty_cmd)
        proc = pexpect.spawn(ssh_cmd)
        proc.expect("admin@{}'s password:".format(self.hostname))
        proc.sendline(self.pwd)
        proc.expect("Terminal ready")
        return SonicTsHostCosumer(proc)
    
    def join(self):
        ssh_cmd = SonicTsHost.PURE_SSH_CMD_PATTERN.format(self.user, self.hostname)
        proc = pexpect.spawn(ssh_cmd)
        proc.expect("admin@{}'s password:".format(self.hostname))
        proc.sendline(self.pwd)
        return SonicTsHostProber(proc)

class SonicTsHostCosumer(object):
    TERMINATE_TEXT = "Thanks for using picocom"
    def __init__(self, proc):
        self.proc             = proc
        self.actual_flow_size = 0

        # pexpect set this value to 50ms by default, which will cause we never got chance to send faster
        self.proc.delaybeforesend = None
        self.proc.delayafterread  = None

    def receive(self, packet_buffers):
        for packet_buffer in packet_buffers:
            self.proc.sendline(packet_buffer)
            self.proc.expect_exact(packet_buffer)
    
    def close(self):
        self.proc.close(force=True)

class SonicTsHostProber(object):
    CPU_PROBE_CMD_PATTERN = "top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\([0-9.]*\)%* id.*/\\1/\" | awk '{print 100 - $1\"%\"}'"
    PROBE_INTERVAL = 1

    def __init__(self, proc):
        self.proc = proc

    def probe(self, duration):
        start_time = time.time()
        probe_count = 0
        total_cpu_percent = 0
        while (time.time() - start_time) < duration:
            self.proc.sendline("echo \"probe start\"")
            self.proc.expect("probe start")
            self.proc.sendline(SonicTsHostProber.CPU_PROBE_CMD_PATTERN)
            self.proc.expect("%\r\n")
            out = self.proc.before
            outs = out.splitlines()
            total_cpu_percent += float(outs[-1])
            probe_count += 1
        self.avg_cpu_percent = total_cpu_percent / (probe_count if probe_count != 0 else 1)

class PacketSizeTooSmallError(Exception):
    def __init__(self, message):
        self.message = message
