# coding: utf-8

"""
A pure python ping implementation using raw sockets.

Note that ICMP messages can only be sent from processes running as root
(in Windows, you must run this script as 'Administrator').

Bugs are naturally mine. I'd be glad to hear about them. There are certainly word - size dependencies here.

:homepage: https://github.com/toxinu/Pyping/
:copyleft: 1989-2011 by the python-ping team, see AUTHORS for more details.
:license: GNU GPL v2, see LICENSE for more details.
"""

import os
import select
import signal
import socket
import struct
import sys
from time import perf_counter, sleep


# ICMP parameters
ICMP_ECHOREPLY = 0  # Echo reply (per RFC792)
ICMP_ECHO = 8  # Echo request (per RFC792)
ICMP_MAX_RECV = 2048  # Max size of incoming buffer

MAX_SLEEP = 1000


def calculate_checksum(source_string):
    """
    A port of the functionality of in_cksum() from ping.c
    Ideally this would act on the string as a series of 16-bit ints (host
    packed), but this works.
    Network data is big-endian, hosts are typically little-endian
    """
    countTo = (int(len(source_string) / 2)) * 2
    checksum = 0
    count = 0

    # Handle bytes in pairs (decoding as short ints)
    while count < countTo:
        if sys.byteorder == "little":
            loByte = source_string[count]
            hiByte = source_string[count + 1]
        else:
            loByte = source_string[count + 1]
            hiByte = source_string[count]
        checksum = checksum + (hiByte * 256 + loByte)
        count += 2

    # Handle last byte if applicable (odd-number of bytes)
    # Endianness should be irrelevant in this case
    if countTo < len(source_string):  # Check for odd length
        loByte = source_string[len(source_string) - 1]
        checksum += loByte

    checksum &= 0xffffffff  # Truncate sum to 32 bits (a variance from ping.c, which
    # uses signed ints, but overflow is unlikely in ping)

    checksum = (checksum >> 16) + (checksum & 0xffff)  # Add high 16 bits to low 16 bits
    checksum += (checksum >> 16)  # Add carry from above (if any)
    answer = ~checksum & 0xffff  # Invert and truncate to 16 bits
    answer = socket.htons(answer)

    return answer


def is_valid_ip4_address(addr):
    parts = addr.split(".")
    if not len(parts) == 4:
        return False
    for part in parts:
        try:
            number = int(part)
        except ValueError:
            return False
        if number > 255 or number < 0:
            return False
    return True


def to_ip(addr):
    if is_valid_ip4_address(addr):
        return addr
    return socket.gethostbyname(addr)


class Response(object):
    def __init__(self):
        self.max_rtt = None
        self.min_rtt = None
        self.avg_rtt = None
        self.packet_lost = None
        self.ret_code = None
        self.output = []

        self.packet_size = None
        self.timeout = None
        self.destination = None
        self.destination_ip = None


class Ping(object):
    def __init__(self, destination, timeout=1000, packet_size=55, own_id=None, quiet_output=True, udp=False, bind=None):
        self.quiet_output = quiet_output
        if quiet_output:
            self.response = Response()
            self.response.destination = destination
            self.response.timeout = timeout
            self.response.packet_size = packet_size

        self.destination = destination
        self.timeout = timeout
        self.packet_size = packet_size
        self.udp = udp
        self.bind = bind

        if own_id is None:
            self.own_id = os.getpid() & 0xFFFF
        else:
            self.own_id = own_id

        try:
            # FIXME: Use destination only for display this line here? see: https://github.com/jedie/python-ping/issues/3
            self.dest_ip = to_ip(self.destination)
            if quiet_output:
                self.response.destination_ip = self.dest_ip
        except socket.gaierror as e:
            self.print_unknown_host(e)
        else:
            self.print_start()

        self.seq_number = 0
        self.send_count = 0
        self.receive_count = 0
        self.min_time = 999999999
        self.max_time = 0.0
        self.total_time = 0.0

    # --------------------------------------------------------------------------

    def print_start(self):
        msg = "\nPYTHON-PING %s (%s): %d data bytes" % (self.destination, self.dest_ip, self.packet_size)
        if self.quiet_output:
            self.response.output.append(msg)
        else:
            print(msg)

    def print_unknown_host(self, e):
        msg = "\nPYTHON-PING: Unknown host: %s (%s)\n" % (self.destination, e.args[1])
        if self.quiet_output:
            self.response.output.append(msg)
            self.response.ret_code = 1
        else:
            print(msg)

        raise Exception("unknown_host")

    # sys.exit(-1)

    def print_success(self, delay, ip, packet_size, ip_header, icmp_header):
        if ip == self.destination:
            from_info = ip
        else:
            from_info = "%s (%s)" % (self.destination, ip)

        msg = f"{packet_size} bytes from {from_info}: icmp_seq={icmp_header['seq_number']} ttl={ip_header['ttl']} time={delay:.1f} ms"

        if self.quiet_output:
            self.response.output.append(msg)
            self.response.ret_code = 0
        else:
            print(msg)

    # print("IP header: %r" % ip_header)
    # print("ICMP header: %r" % icmp_header)

    def print_failed(self):
        msg = "Request timed out."

        if self.quiet_output:
            self.response.output.append(msg)
            self.response.ret_code = 1
        else:
            print(msg)

    def print_exit(self):
        msg = f"\n----{self.destination} PYTHON PING Statistics----"

        if self.quiet_output:
            self.response.output.append(msg)
        else:
            print(msg)

        lost_count = self.send_count - self.receive_count
        # print("%i packets lost" % lost_count)
        lost_rate = float(lost_count) / self.send_count * 100.0

        msg = f"{self.send_count} packets transmitted, {self.receive_count} packets received, {lost_rate:.1f}% packet loss"

        if self.quiet_output:
            self.response.output.append(msg)
            self.response.packet_lost = lost_count
        else:
            print(msg)

        if self.receive_count > 0:
            msg = "round-trip (ms)  min/avg/max = %0.3f/%0.3f/%0.3f" % (self.min_time, self.total_time / self.receive_count, self.max_time)
            if self.quiet_output:
                self.response.min_rtt = f'{self.min_time:.3f}'
                self.response.avg_rtt = f'{(self.total_time / self.receive_count):.3f}'
                self.response.max_rtt = f'{self.max_time:.3f}'
                self.response.output.append(msg)
            else:
                print(msg)

        if self.quiet_output:
            self.response.output.append('\n')
        else:
            print('')

    # --------------------------------------------------------------------------

    def signal_handler(self, signum):
        """
        Handle print_exit via signals
        """
        self.print_exit()
        msg = f"\n(Terminated with signal {signum})\n"

        if self.quiet_output:
            self.response.output.append(msg)
            self.response.ret_code = 0
        else:
            print(msg)

        sys.exit(0)

    def setup_signal_handler(self):
        signal.signal(signal.SIGINT, self.signal_handler)  # Handle Ctrl-C
        if hasattr(signal, "SIGBREAK"):
            # Handle Ctrl-Break e.g. under Windows
            signal.signal(signal.SIGBREAK, self.signal_handler)

    # --------------------------------------------------------------------------

    @staticmethod
    def header2dict(names, struct_format, data):
        """ unpack the raw received IP and ICMP header information to a dict """
        unpacked_data = struct.unpack(struct_format, data)
        return dict(zip(names, unpacked_data))

    # --------------------------------------------------------------------------

    def run(self, count=None, deadline=None):
        """
        send and receive pings in a loop. Stop if count or until deadline.
        """
        if not self.quiet_output:
            self.setup_signal_handler()

        while True:
            delay = self.do()

            self.seq_number += 1
            if count and self.seq_number >= count:
                break
            if deadline and self.total_time >= deadline:
                break

            if delay is None:
                delay = 0

            # Pause for the remainder of the MAX_SLEEP period (if applicable)
            if MAX_SLEEP > delay:
                sleep((MAX_SLEEP - delay) / 1000.0)

        self.print_exit()
        if self.quiet_output:
            return self.response

    def do(self):
        """
        Send one ICMP ECHO_REQUEST and receive the response until self.timeout
        """
        try:  # One could use UDP here, but it's obscure
            if self.udp:
                current_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.getprotobyname("icmp"))
            else:
                current_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))

            # Bind the socket to a source address
            if self.bind:
                current_socket.bind((self.bind, 0))  # Port number is irrelevant for ICMP

        except socket.error as msg:
            if msg == 1:
                # Operation not permitted - Add more information to traceback
                etype, evalue, etb = sys.exc_info()
                evalue = etype(
                    "%s - Note that ICMP messages can only be send from processes running as root." % evalue
                )
                raise etype(evalue).with_traceback(etb)
            raise  # raise the original error

        send_time = self.send_one_ping(current_socket)
        if send_time is None:
            return
        self.send_count += 1

        receive_time, packet_size, ip, ip_header, icmp_header = self.receive_one_ping(current_socket)
        current_socket.close()

        if receive_time:
            self.receive_count += 1
            delay = (receive_time - send_time) * 1000.0
            self.total_time += delay
            if self.min_time > delay:
                self.min_time = delay
            if self.max_time < delay:
                self.max_time = delay

            self.print_success(delay, ip, packet_size, ip_header, icmp_header)
            return delay
        else:
            self.print_failed()

    def send_one_ping(self, current_socket):
        """
        Send one ICMP ECHO_REQUEST
        """
        # Header is type (8), code (8), checksum (16), id (16), sequence (16)
        checksum = 0

        # Make a dummy header with a 0 checksum.
        header = struct.pack(
            "!BBHHH", ICMP_ECHO, 0, checksum, self.own_id, self.seq_number
        )

        padBytes = []
        startVal = 0x42
        for i in range(startVal, startVal + self.packet_size):
            padBytes += [(i & 0xff)]  # Keep chars in the 0-255 range
        data = bytes(padBytes)

        # Calculate the checksum on the data and the dummy header.
        checksum = calculate_checksum(header + data)  # Checksum is in network order

        # Now that we have the right checksum, we put that in. It's just easier
        # to make up a new header than to stuff it into the dummy.
        header = struct.pack(
            "!BBHHH", ICMP_ECHO, 0, checksum, self.own_id, self.seq_number
        )

        packet = header + data

        send_time = perf_counter()

        try:
            current_socket.sendto(packet, (self.destination, 1))  # Port number is irrelevant for ICMP
        except socket.error as e:
            self.response.output.append(f"General failure ({e.args[1]})")
            current_socket.close()
            return

        return send_time

    def receive_one_ping(self, current_socket):
        """
        Receive the ping from the socket. timeout = in ms
        """
        timeout = self.timeout / 1000.0

        while True:  # Loop while waiting for packet or timeout
            select_start = perf_counter()
            inputready, outputready, exceptready = select.select([current_socket], [], [], timeout)
            select_duration = (perf_counter() - select_start)
            if not inputready:  # timeout
                return None, 0, 0, 0, 0

            packet_data, address = current_socket.recvfrom(ICMP_MAX_RECV)

            icmp_header = self.header2dict(
                names=[
                    "type", "code", "checksum",
                    "packet_id", "seq_number"
                ],
                struct_format="!BBHHH",
                data=packet_data[20:28]
            )

            receive_time = perf_counter()

            if icmp_header["packet_id"] == self.own_id:  # Our packet
                ip_header = self.header2dict(
                    names=[
                        "version", "type", "length",
                        "id", "flags", "ttl", "protocol",
                        "checksum", "src_ip", "dest_ip"
                    ],
                    struct_format="!BBHHHBBHII",
                    data=packet_data[:20]
                )
                packet_size = len(packet_data) - 28
                ip = socket.inet_ntoa(struct.pack("!I", ip_header["src_ip"]))
                # XXX: Why not ip = address[0] ???
                return receive_time, packet_size, ip, ip_header, icmp_header

            timeout = timeout - select_duration
            if timeout <= 0:
                return None, 0, 0, 0, 0


def ping(hostname, timeout=1000, count=3, packet_size=55, *args, **kwargs):
    p = Ping(hostname, timeout, packet_size, *args, **kwargs)
    return p.run(count)
