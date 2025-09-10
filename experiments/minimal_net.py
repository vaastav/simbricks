from simbricks.orchestration import instantiation as inst
from simbricks.orchestration import simulation as sim
from simbricks.orchestration import system
from simbricks.orchestration.helpers import instantiation as inst_helpers
from simbricks.orchestration.helpers import simulation as sim_helpers
from simbricks.utils import base as utils_base
import json

synchronized = True

sys = system.System()

# create disk images
distro_disk_image = system.DistroDiskImage(sys, "base")

# create a host instance and a NIC instance then install the NIC on the host
# host0 = system.CorundumLinuxHost(sys)
host0 = system.I40ELinuxHost(sys)
host0.add_disk(distro_disk_image)
host0.add_disk(system.LinuxConfigDiskImage(sys, host0))

nic0 = system.IntelI40eNIC(sys)
nic0.add_ipv4("10.0.0.1")
host0.connect_pcie_dev(nic0)


# create a host instance and a NIC instance then install the NIC on the host
host1 = system.I40ELinuxHost(sys)
host1.add_disk(distro_disk_image)
host1.add_disk(system.LinuxConfigDiskImage(sys, host1))

nic1 = system.IntelI40eNIC(sys)
nic1.add_ipv4("10.0.0.2")
host1.connect_pcie_dev(nic1)


switch0 = system.EthSwitch(sys)
switch0.connect_eth_peer_if(nic0._eth_if)
switch0.connect_eth_peer_if(nic1._eth_if)

# configure the software to run on the host
ping_client_app = system.PingClient(host0, nic1._ip)
ping_client_app.wait = True
host0.add_app(ping_client_app)
host1.add_app(system.Sleep(host1, infinite=True))

simulation = sim_helpers.simple_simulation(
    sys,
    compmap={
        system.FullSystemHost: sim.Gem5Sim,
        system.IntelI40eNIC: sim.I40eNicSim,
        system.EthSwitch: sim.SwitchNet,
    },
)

if synchronized:
    simulation.enable_synchronization(amount=500, ratio=utils_base.Time.Nanoseconds)

nic_sim0 = simulation.find_sim(nic0)
nic_sim0.mac = "00:1A:2B:3C:4D:5E"
nic_sim0.log_file = "nic0.log"
nic_sim1 = simulation.find_sim(nic1)
nic_sim1.mac = "00:1A:2B:3C:4D:5F"
nic_sim1.log_file = "nic1.log"

switch0_sim = simulation.find_sim(switch0)
switch0_sim.log_file = "switch0.log"

host_sim0 = simulation.find_sim(host0)
host_sim1 = simulation.find_sim(host1)
host_sim0.log_file = "host0.log"
host_sim1.log_file = "host1.log"
if isinstance(host_sim0, sim.Gem5Sim):
    host_sim0._variant = "opt"
if isinstance(host_sim1, sim.Gem5Sim):
    host_sim1._variant = "opt"

instantiation = inst_helpers.simple_instantiation(simulation)
fragment = inst.Fragment()
fragment.add_simulators(*simulation.all_simulators())
instantiation.fragments = [fragment]

instantiations = [instantiation]

with open('sim_topology.json', 'w+') as outf:
    topo = {}
    topo['system'] = sys.toJSON()
    topo['simulation'] = simulation.toJSON()
    topo_str = json.dumps(topo, indent=4)
    outf.write(topo_str)