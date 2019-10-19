# Test Script 1 for LSP Information

# BWP : 3/23/18 : Initial Creation
# BWP : 11/15/18 : Updating for f-string support
# BWP : 06/14/19 : Updated to take command line arguments.
#                  Single IP address argument will display all LSP's information for that router.
#                  Two IP Address arguments will display all LSP's information for both routers.
#                  Two IP Address arguments followed by '--compare' will pull all LSP information from both routers, but
#                      will only display LSP information for each router that is destined to the other.
#                      Also checks for asymmetrical path between the two on the Active Path.
# BWP : 10/19/19 : *Updated some comments.  Note there are items for investigation on next code review (See comments)

# System Imports
import time
startup = time.time()
import sys
import itertools
import re
from lxml import etree
import yaml

from colorama import init as colo_init
from colorama import Fore, Style
colo_init()

# PyEZ Imports
from jnpr.junos import Device


# Information that can be regex'd from each LSP
_all_lsp_Re = re.compile(r'<mpls-lsp>(.*?)</mpls-lsp>', re.I | re.S)
_destination_address_Re = re.compile(r'<destination-address>(.*?)</destination-address>', re.I | re.S)
_source_address_Re = re.compile(r'<source-address>(.*?)</source-address>', re.I | re.S)
_name_Re = re.compile(r'<name>(.*?)</name>', re.I | re.S)
_state_Re = re.compile(r'<lsp-state>(.*?)</lsp-state>', re.I | re.S)
_active_path_Re = re.compile(r'<active-path>(.*?)</active-path>', re.I | re.S)


# Information that can be regex'd from each individual Path within an LSP
_lsp_path_Re = re.compile(r'<mpls-lsp-path>(.*?)</mpls-lsp-path>', re.I | re.S)
_lsp_path_name_Re = re.compile(r'<name>(.*?)</name>', re.I | re.S)
_lsp_path_title_Re = re.compile(r'<title>(.*?)</title>', re.I | re.S)
_lsp_path_state_Re = re.compile(r'<path-state>(.*?)</path-state>', re.I | re.S)
_lsp_path_route_Re = re.compile(r'<explicit-route heading="          ">(.*?)</explicit-route>', re.I | re.S)
_lsp_path_addresses_Re = re.compile(r'<address>(.*?)</address>', re.I | re.S)


router_list = []
lsp_list = []


class lspPath(object):
    def __init__(self, title, active, name, state, explicit_route):
        self.title = title
        self.active = active
        self.name = name
        self.state = state
        self.explicit_route = explicit_route
        if self.active:
            self.color_BG = f"{Style.BRIGHT}{Fore.GREEN}"
        else:
            self.color_BG = ""
            
        if self.state == "Down":
            self.color_BR = f"{Style.BRIGHT}{Fore.RED}"
        else:
            self.color_BR = ""

    def __repr__(self):
        return f"\tName: {self.color_BG}{self.name}{Style.RESET_ALL}\n\tTitle: {self.title}\n\tState: {self.color_BR}{self.state}{Style.RESET_ALL}\n\tExplicit Route: {self.explicit_route}\n"


class labelSwitchedPath(object):
    def __init__(self, lsp_destination_address, lsp_source_address, lsp_state, lsp_name, lsp_active_path, lsp_paths):
        self.lsp_destination_address = lsp_destination_address
        self.lsp_source_address = lsp_source_address
        self.lsp_state = lsp_state
        self.lsp_name = lsp_name
        self.lsp_active_path = lsp_active_path
        self.lsp_paths = lsp_paths
        self.color_BG = f"{Style.BRIGHT}{Fore.GREEN}"
        if self.lsp_state == "Down":
            self.color_BR = f"{Style.BRIGHT}{Fore.RED}"
        else:
            self.color_BR = ""
        

    def __repr__(self):
        return f"Name: {self.lsp_name}\nSource: {self.lsp_source_address}\nDestination: {self.lsp_destination_address}\n" \
               f"State: {self.color_BR}{self.lsp_state}{Style.RESET_ALL}\nActive Path: {self.color_BG}{self.lsp_active_path}\n{Style.RESET_ALL}"        

class oneRouter(object):
    def __init__(self, hostname, loopback):
        self.hostname = hostname
        self.loopback = loopback
        self.lsps = []


def get_router_lsps(router, address_list):
    detailed_info = router.rpc.get_mpls_lsp_information(ingress=True, detail=True)
    detailed_info = etree.tostring(detailed_info).decode()
    
    all_lsps = _all_lsp_Re.findall(detailed_info)
    if len(all_lsps) > 0:
        for each_lsp in all_lsps:
            # Parse out all of the LSP SPECIFIC information
            lsp_destination_address = _destination_address_Re.search(each_lsp).group(1)
            lsp_source_address = _source_address_Re.search(each_lsp).group(1)
            lsp_state = _state_Re.search(each_lsp).group(1)
            lsp_name = _name_Re.search(each_lsp).group(1)
            lsp_active_path = _active_path_Re.search(each_lsp).group(1).split()[0]

            # Parse out all of the individual Path Information for this LSP
            paths_to_add = []
            all_paths = _lsp_path_Re.findall(each_lsp)
            if len(all_paths) > 0:
                for eachmatch in all_paths:
                    path_name = _lsp_path_name_Re.search(eachmatch).group(1)
                    path_title = _lsp_path_title_Re.search(eachmatch).group(1)
                    path_state = _lsp_path_state_Re.search(eachmatch).group(1)
                    path_explicit_route = _lsp_path_route_Re.search(eachmatch).group(1)
                    path_explicit_route_list = _lsp_path_addresses_Re.findall(path_explicit_route)
                    path_route_list = []
                    if len(path_explicit_route_list) > 0:
                        for eachaddress in path_explicit_route_list:
                            for eachdevice in address_list.keys():
                                if eachaddress in address_list[eachdevice]['ipaddresses']:
                                    path_route_list.append(eachdevice)
                    if path_name == lsp_active_path:
                        path_active = True
                    else:
                        path_active = False
                        
                    paths_to_add.append(lspPath(path_title, path_active, path_name, path_state, path_route_list))

            lsp_list.append(labelSwitchedPath(lsp_destination_address, lsp_source_address, lsp_state, lsp_name, lsp_active_path, paths_to_add))

            #print(f"LSP {lsp_name} at {lsp_source_address} added to list with {len(paths_to_add)} paths\n")
    else:
        print("Error matching all lsps")

def display_all_lsp_information():
    for eachlsp in lsp_list:
        print(eachlsp)
        for eachpath in eachlsp.lsp_paths:
            print(f"{eachpath}")
        print("\n ***** \n")


def display_rev_lsp_information(addresses):
    found_rev_lsp = 0
    active_paths = []

    for eachlsp in lsp_list:
        if eachlsp.lsp_destination_address in addresses:
            found_rev_lsp += 1
            # Print the Label-Switched-Path header information
            print(eachlsp)
            for eachpath in eachlsp.lsp_paths:
                print(f"{eachpath}")
                if eachpath.active:
                    active_paths.append(eachpath.explicit_route[:-1])
            print("\n ***** \n")

    # Identify and print any asymmetrical paths on Active Paths
    if len(active_paths) == 2:
        if active_paths[0] != active_paths[1][::-1]:
            print(f"{Style.BRIGHT}{Fore.RED}!!! FOUND ASYMMETRICAL PATH !!! {Style.RESET_ALL}")
        
    print(f"Found {found_rev_lsp} reverse LSP's.")

if __name__ == "__main__":
    try:
        with open("routers_lsp.yml", "r") as configfile:
            config = yaml.load(configfile, Loader=yaml.SafeLoader)
        credentials = config['credentials']
        device_username = credentials['username']
        device_password = credentials['password']
        device_port = credentials['port']

        address_list = config['routerlist']

        device_loopbacks = config['devices_to_query']
        
        devices_address_list = []

        compare_rev_lsp = False

        # Determine if we have CLI arguments
        # *This may be sexier as a dict. Evaluate on next review.
        if len(sys.argv) == 1:
            devices_address_list = [dev for dev in device_loopbacks.values()]
        elif len(sys.argv) == 2:
            devices_address_list.append(str(sys.argv[1]))
        elif len(sys.argv) == 3:
            devices_address_list = [str(dev) for dev in sys.argv[1:3]]
        elif len(sys.argv) == 4 and sys.argv[3] == "--compare":
            devices_address_list = [str(dev) for dev in sys.argv[1:3]]
            compare_rev_lsp = True
        else:
            # Update this to be informative. Or, look at argparse module and do it correctly.
            print("Not valid input")
            sys.exit()

    except Exception as err:
        print(f"Error opening or processing routers.yml : {err}")
        sys.exit()
        
    for each_router in devices_address_list:
        try:
            with Device(host=each_router, user=device_username, passwd=device_password, port=device_port) as dev:
                #print(f"\nConnected to {dev.facts['hostname']}.\n")
                this_hostname = dev.facts['hostname']
                
                get_router_lsps(dev, address_list)
                #print(f"Disconnected from {this_hostname}.\n\n")

                this_router = oneRouter(this_hostname, each_router)
                router_list.append(this_router)

        except Exception as err:
            print(f"Error opening device {each_router}.  Error: {err}")

    count = 0
    for eachlsp in lsp_list:
       count += len(eachlsp.lsp_paths)

    if not compare_rev_lsp:
        display_all_lsp_information()
    else:
        display_rev_lsp_information(addresses=sys.argv[1:3])

    print(f"Found {len(router_list)} Routers : Found {len(lsp_list)} total LSPs : Found {count} total Paths")
            
    print(f"Complete in {(time.time() - startup):,.3f} seconds.")
    
    sys.exit()
