# Copyright 2021 Max Planck Institute for Software Systems, and
# National University of Singapore
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from simbricks.orchestration import system
from simbricks.orchestration import simulation
from simbricks.orchestration.helpers import instantiation as inst_helpers
from simbricks.utils import base as utils_base


"""
This list is used and expected
"""
instantiations = []


"""
PARAMETERS
"""
sys_nic = system.IntelI40eNIC
sys_host = system.I40ELinuxHost

sim_nic = simulation.I40eNicSim
sim_host = simulation.Gem5Sim

num_ns3_dummy_host_pairs = 1

synchronized = False

full_hosts = []
nics = []
ns3_hosts = []

"""
System Specification
"""
syst = system.System(name="Columbo-Sys")
distro_disk_image = system.DistroDiskImage(syst, "base")

# Client host
host0 = sys_host(syst)
host0.add_disk(distro_disk_image)
host0.add_disk(system.LinuxConfigDiskImage(syst, host0))
full_hosts.append(host0)

# Client NIC
nic0 = sys_nic(syst)
nic0.add_ipv4("10.0.0.1")
host0.connect_pcie_dev(nic0)
nics.append(nic0)

# Server Host
host1 = sys_host(syst)
host1.add_disk(distro_disk_image)
host1.add_disk(system.LinuxConfigDiskImage(syst, host1))
full_hosts.append(host1)

# Server NIC
nic1 = sys_nic(syst)
nic1.add_ipv4("10.0.0.2")
host1.connect_pcie_dev(nic1)
nics.append(nic1)

# Client app
client_app = system.NetperfClient(h=host0, server_ip=nic1._ip)
client_app.wait = True
host0.add_app(client_app)

# Server app
server_app = system.NetperfServer(h=host1)
host1.add_app(server_app)

# create switches and connect them to NICs
switch_1 = system.EthSwitch(syst)
switch_1.connect_eth_peer_if(nic0._eth_if)
switch_2 = system.EthSwitch(syst)
switch_2.connect_eth_peer_if(nic1._eth_if)
# connect switches
eth_1 = system.EthInterface(switch_1)
switch_1.add_if(eth_1)
eth_2 = system.EthInterface(switch_2)
switch_2.add_if(eth_2)
switch_to_switch_chan = system.EthChannel(eth_1, eth_2)


# create ns3 dummy hosts system spec
for i in range(num_ns3_dummy_host_pairs):
    # create bulk send host & connect to switch
    client = system.Host(syst)
    client.parameters["ip"] = f"192.168.64.{i}/24"
    client_inf = system.EthInterface(client)
    client.add_if(client_inf)
    switch_1.connect_eth_peer_if(client_inf)
    ns3_hosts.append(client)

    # create packet sink and connect to switch
    server = system.Host(syst)
    server.parameters["ip"] = f"192.168.64.{i + num_ns3_dummy_host_pairs}/24"
    server_inf = system.EthInterface(server)
    server.add_if(server_inf)
    switch_2.connect_eth_peer_if(server_inf)
    ns3_hosts.append(server)

    # add bulk send app to respective host
    client_app = system.Application(client)
    client_app.parameters["type_id"] = "ns3::BulkSendApplication"
    client_app.parameters["ns3_params"] = {
        'Remote(InetSocketAddress)': f"192.168.64.{i + num_ns3_dummy_host_pairs}:2000",
    }
    client.add_app(client_app)

    # add packet sink app to respective host
    server_app = system.Application(server)
    server_app.parameters["type_id"] = "ns3::PacketSink"
    server_app.parameters["ns3_params"] = {
        'Local(InetSocketAddress)': "0.0.0.0:0",
    }
    server.add_app(server_app)


"""
Simulator Choice
"""
sim = simulation.Simulation(name="Columbo-Sim", system=syst)

# create simulators for full hosts
for host in full_hosts:
    host_inst = sim_host(sim)
    if isinstance(host_inst, simulation.Gem5Sim):
        host_inst._variant = "opt"
    host_inst.add(host)

# create simulators for nics
for nic in nics:
    nic_inst = sim_nic(simulation=sim)
    nic_inst.add(nic)

# mac address + log file nic0 / nic1
nic0_s = sim.find_sim(nic0)
nic0_s.mac = "00:1A:2B:3C:4D:5E"
nic0_s.log_file = "nic0.log"

nic1_s = sim.find_sim(nic1)
nic1_s.mac = "00:1A:2B:3C:4D:5F"
nic1_s.log_file = "nic1.log"

# create network simulator
net_inst = simulation.NS3Net(sim)
net_inst.add(switch_1)
net_inst.add(switch_2)

# add ns3 dumbell hosts to ns3 sim
for ns3_h in ns3_hosts:
    net_inst.add(ns3_h)

net_inst.logging.add_logging("SimbricksNetDevice", simulation.ns3_comps.NS3LoggingLevel.ALL)
net_inst.logging.add_logging("BridgeNetDevice", simulation.ns3_comps.NS3LoggingLevel.ALL)
net_inst.logging.add_logging("E2ENetwork", simulation.ns3_comps.NS3LoggingLevel.ALL)
net_inst.logging.add_logging("E2ETopology", simulation.ns3_comps.NS3LoggingLevel.ALL)
# Set the ns3 log file!
net_inst.log_file = "ns3_net.log"
net_inst._executable = "sims/external/ns-3/simbricks-run-log.sh"

if synchronized:
    sim.enable_synchronization()


"""
Instantiation
"""
instance = inst_helpers.simple_instantiation(sim)
instantiations.append(instance)

