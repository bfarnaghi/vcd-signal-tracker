# I extracted the waveforms of the instance with a defined gap first and write in different VCD file
# then I used these VCD files to extracte the VCD of each clock cycle and write in different VCD file
# then I use the vc2saif to convert the VCD to SAIF file
import sys
sys.path.append('/home/b.farnaghinejad/.local/lib/python3.9/site-packages')
import  argparse
from    collections.abc import MutableMapping
import  bisect
import  math
import  re
from    decimal import Decimal
from    pprint import PrettyPrinter
import  os
from    os.path import basename
import  time as time_module
import  random
import  string
import  json
from    tqdm import tqdm

##### Parse Command Line Arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Parse and analyze VCD files.")
    parser.add_argument("-f", "--folder", help="Path to the folder containing VCD files.")
    parser.add_argument("vcd_file", nargs='?', help="Path to the VCD file. This argument is optional if --folder is provided.")
    parser.add_argument("-i","--instances", type=str, nargs='+', help="List of instance names to track")
    parser.add_argument("-t", "--time", nargs=2, type=int, help="Start time and end time of monitoring.")
    parser.add_argument("-c", "--clock", type=int, help="Clock period for each cycle.")
    parser.add_argument("-e", "--enable", nargs='*', help="Enable signal to monitor selected signals.")
    parser.add_argument("-saif", "--generate_saif_files", action="store_true", help="Generate SAIF files for each cycle.")
    parser.add_argument("-rmvcd", "--remove_vcd_files", action="store_true", help="Remove VCD files after generating SAIF files.")
    parser.add_argument("-o", "--output_folder", help="Output folder for generated VCD and SAIF files.")
    parser.add_argument("-hd", "--hamming_distance", action="store_true", help="Calculate Hamming distance for each signal.")
    return parser.parse_args()

##### Enhance VCD Parsing Logic
pp = PrettyPrinter()
_RE_TYPE = type(re.compile(''))

class Signal(object):
    # Initialize the Signal object
    def __init__(self, size, var_type, identifier):
        self.size = size
        self.var_type = var_type
        self.identifier = identifier
        self.tv = []
        self.endtime = None
        self.hamming_distance = []
    # Get the value of the signal at a specific time
    def __getitem__(self, time):
        if isinstance(time, slice):
            if not self.endtime:
                self.endtime = self.tv[-1][0]
            return [self[ii] for ii in range(*time.indices(self.endtime))]
        elif isinstance(time, int):
            if time < 0:
                time = 0
            left = bisect.bisect_left(self.tv, (time, ''))
            if left == len(self.tv):
                i = left - 1
            else:
                if self.tv[left][0] == time:
                    i = left
                else:
                    i = left - 1
            if i == -1:
                return None
            return self.tv[i][1]
        else:
            raise TypeError("Invalid argument type.")
    # Set the value of the signal at a specific time
    def __repr__(self):
        return pp.pformat(self.__dict__)
    
class VCDPARSE(object):

    # Character sets for value changes
    _VALUE = set(('0', '1', 'x', 'X', 'z', 'Z'))
    _VECTOR_VALUE_CHANGE = set(('b', 'B', 'r', 'R'))

    # Initialize the VCDPARSE object
    def __init__(self, vcd_path=None, signals=None, store_tvs=True, initial_value='0'):
        # Persistent attributes
        self.vcd_path = vcd_path
        self.hierarchy = {}
        self.scopes = {}
        self.data = {}
        self.endtime = 0
        self.begintime = 0
        self.total_line = 0
        self.references_to_ids = {}
        self.signals = signals if signals else []
        self.timescale = {}
        self._store_tvs = store_tvs
        self.initial_value = initial_value
        self.cur_sig_vals = {}
        self.factor = {
            "s": '1e0',
            "ms": '1e-3',
            "us": '1e-6',
            "ns": '1e-9',
            "ps": '1e-12',
            "fs": '1e-15',
        }

    # Read Scopes and Signals
    def read_definitions(self):
        """Parses the header part to get scopes and signal definitions."""

        hier = []

        with open(self.vcd_path, 'r') as vcd_file:
            
            # Parsing logic for definitions
            for line in vcd_file:
                if '$enddefinitions' in line:
                    break
                # Handle scopes
                elif '$scope' in line:
                    scope_name = line.split()[2]
                    hier.append(scope_name)
                elif '$upscope' in line:
                    hier.pop()
                elif '$var' in line:
                    ls = line.split()
                    type = ls[1]
                    size = ls[2]
                    identifier_code = ls[3]
                    name = ''.join(ls[4:-1])
                    path = '.'.join(hier)

                    if path:
                        reference = path + '.' + name
                    else:
                        reference = name

                    self.signals.append(reference)
                    self.data[identifier_code] = Signal(size, type, identifier_code)
                    self.references_to_ids[reference] = identifier_code
                    self.cur_sig_vals[identifier_code] = self.initial_value

                elif '$timescale' in line:
                    if '$end' not in line:
                        while True:
                            line += " " + vcd_file.readline().strip().rstrip()
                            if '$end' in line:
                                break
                    magnitude = Decimal(re.findall(r"\d+|$", line)[0])
                    unit = re.findall(r"s|ms|us|ns|ps|fs", line)[0]
                    factor = self.factor[unit]
                    self.timescale["timescale"] = magnitude * Decimal(factor)
                    self.timescale["magnitude"] = magnitude
                    self.timescale["unit"] = unit
                    self.timescale["factor"] = Decimal(factor)
            
            self.total_line = sum(1 for _ in vcd_file)

    # Read Value Changes
    def read_value_changes(self,start_time=None, end_time=None):
        """Parses value changes based on selected signals after definitions are parsed."""

        def handle_value_change(line):
            value = line[0]
            identifier_code = line[1:]
            if identifier_code in self.data:
                self._add_value_identifier_code(time, value, identifier_code)
                

        def handle_vector_value_change(line):
            value, identifier_code = line[1:].split()
            if identifier_code in self.data:
                self._add_value_identifier_code(time, value, identifier_code)

        time = 0
        first_time = True

        with open(self.vcd_path, 'r') as vcd_file, tqdm(total=self.total_line, desc="Reading VCD", unit=" lines") as pbar:

            for line in vcd_file:
                pbar.update(1)
                line0 = line[0]
                if line == '':
                    break
                line = line.strip()
                if line == '':
                    continue
                # Handle time step
                elif line0 == '#':
                    time = int(line.split()[0][1:])
                    if end_time is not None and time > end_time:
                        break
                    elif start_time is not None and time < start_time:
                        continue
                    elif first_time:
                        self.begintime = time
                        first_time = False
                    self.endtime = time

                # Handle value change for a more than one bit signal
                elif line0 in self._VECTOR_VALUE_CHANGE:
                    handle_vector_value_change(line)
                # Handle value change for a single bit signal
                elif line0 in self._VALUE:
                    handle_value_change(line)

    # Calculate Hamming Distance
    def hamming_distance(self, val1, val2):
        return bin(int(val1, 2) ^ int(val2, 2)).count('1')

    # Add Value Identifier Code
    def _add_value_identifier_code(self, time, value, identifier_code):
        entry = self.data[identifier_code]
        entry.tv.append((time, value))
        if args.hamming_distance and identifier_code in self.cur_sig_vals and self.cur_sig_vals[identifier_code] != 'x':
            hd = self.hamming_distance(self.cur_sig_vals[identifier_code], value)
            entry.hamming_distance.append((time, hd))
        self.cur_sig_vals[identifier_code] = value

    # Get Item
    def __getitem__(self, refname):
        if isinstance(refname, _RE_TYPE):
            l = []
            for aSignal in self.signals:
                if refname.search(aSignal):
                    l.append(aSignal)
            for aScope in self.scopes:
                if refname.search(aScope):
                    l.append(aScope)
            if len(l) == 1:
                return self[l[0]]
            return l
        else:
            if refname in self.references_to_ids:
                return self.data[self.references_to_ids[refname]]
            if refname in self.scopes:
                return self.scopes[refname]
            raise KeyError(refname)

    # Get data pf the VCD object
    def get_data(self):
        return self.data

    # Get start time of the VCD object
    def get_begintime(self):
        return self.begintime
    
    # Get end time of the VCD object
    def get_endtime(self):
        return self.endtime

    # Get signals of the VCD object
    def get_signals(self):
        return self.signals

    # Get timescale of the VCD object
    def get_timescale(self):
        return self.timescale

##### Monitor Signals
def monitor_signals(vcd, filtered_signals,enable):

    enable_data_dict = {}

    # Populate enable data only if enable signals are provided
    if enable:
        for en_signal in enable:
            enable_data = vcd[en_signal].tv
            enable_data_dict.update({time: value for time, value in enable_data})

    def get_enable_value(enable_data, time):
        return enable_data.get(time, 'x')  # Default to x if time is not found

    if enable:
        start_vcd_time = vcd.get_begintime()
        end_vcd_time = vcd.get_endtime()
        prv_enable_status = '0'
        enable_signal_ranges = []
        start_time = None

        for time in range(start_vcd_time, end_vcd_time + 1):
            enable_value = get_enable_value(enable_data_dict, time)
            if any(enable_value == "1".zfill(int(vcd[en].size)) for en in enable):  # Check each enable signal
                if prv_enable_status == '0':  # Enable just became active
                    start_time = time
                    prv_enable_status = '1'
            elif any(enable_value == "0".zfill(int(vcd[en].size)) for en in enable):  # Check each enable signal
                if prv_enable_status == '1' and start_time is not None:  # Enable just became inactive
                    enable_signal_ranges.append((start_time, time - 1))
                    start_time = None
                prv_enable_status = '0'
            else:  # Default to the previous enable status
                prv_enable_status = prv_enable_status
        # If enable remained active till the end
        if prv_enable_status == '1' and start_time is not None:
            enable_signal_ranges.append((start_time, end_vcd_time))
    else:
        enable_signal_ranges = [(vcd.get_begintime(), vcd.get_endtime())]

    # Group signals based on time windows
    grouped_time_windows = {group_id: {"start": start, "end": end} for group_id, (start, end) in enumerate(enable_signal_ranges, start=1)}

    # Initialize monitored data groups
    monitored_data_groups = {group_id: {signal: [] for signal in filtered_signals} for group_id in grouped_time_windows}
    
    # To track the last value of each signal for each group
    last_values = {signal: None for signal in filtered_signals}

    # Monitor signals based on time windows
    for signal in tqdm(filtered_signals, total=len(filtered_signals), desc="Monitoring Defined Signals", unit=" signals"):
        sig_data = vcd[signal].tv  # Time-value pairs for the signal
        # Assign values to their respective groups based on time
        for time, value in sig_data:
            for group_id, window in grouped_time_windows.items():
                if window["start"] <= time <= window["end"]:  # Check if time is in the group window
                    monitored_data_groups[group_id][signal].append((time, value))
                    last_values[signal] = value
                    break  # Stop checking once the group is found
    
    # Fill in missing values with the last known value
    for group_id, group_data in monitored_data_groups.items():
        for signal, data in group_data.items():
            filled_data = []
            last_value = None
            for time, value in data:
                if value is None and last_value is not None:
                    filled_data.append((time, last_value))  # Use the last known value
                else:
                    filled_data.append((time, value))
                    last_value = value

            # Add initial value before the group
            start_time = grouped_time_windows[group_id]["start"]
            if signal in enable:  # Special case for trigger (enable) signal
                for en in enable:
                    filled_data.insert(0, (start_time - 1, "0".zfill(int(vcd[en].size))))
            else:
                previous_value = None
                for time, value in vcd[signal].tv:
                    if time < start_time:
                        previous_value = value
                    else:
                        break
                if previous_value is not None:
                    filled_data.insert(0, (start_time - 1, previous_value))

            # Extend last value after the group
            end_time = grouped_time_windows[group_id]["end"]
            if last_value is not None:
                filled_data.append((end_time + 1, last_value))

            # Update the group data
            group_data[signal] = filled_data

    return monitored_data_groups

##### Write Output Files
# Build Scope Hierarchy
def build_scope_hierarchy(vcd):
    all_scopes = {}
    for signal in vcd.get_signals():
        parts = signal.split('.')
        current_scope = all_scopes
        for part in parts[:-1]:  # Exclude the signal name itself
            if part not in current_scope:
                current_scope[part] = {}
            current_scope = current_scope[part]
        current_scope[parts[-1]] = signal  # Final part is the signal itself
    return all_scopes
# Generate Identifier
def generate_identifier():
    # Ensure the first character is a letter (to avoid starting with a number)
    first_char = random.choice(string.ascii_uppercase)
    # Generate the remaining 5 characters from uppercase letters and digits
    remaining_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return first_char + remaining_chars
# Write Scopes
identifiers = {}
sizes = {}
def write_scopes(scopes_output, scopes, indent=""):
    for name, content in scopes.items():
        if isinstance(content, dict):
            scopes_output.append(f"{indent}$scope module {name} $end\n")
            write_scopes(scopes_output, content, indent + "  ")
            scopes_output.append(f"{indent}$upscope $end\n")
        else:
            match = re.search(r'\[(\d+):(\d+)\]', name)
            if match:
                if int(match.group(1)) < int(match.group(2)):
                    size = int(match.group(2)) - int(match.group(1)) + 1
                else:
                    size = int(match.group(1)) - int(match.group(2)) + 1
            else:
                size = 1

            signal_name  = scopes[name]
            sizes[signal_name] = size
            if signal_name not in identifiers:
                identifiers[signal_name] = generate_identifier()
            corrected_name = re.sub(r'\[(\d+):(\d+)\]', r' [\1:\2]', name)
            identifier = identifiers[signal_name]
            if size < 10:
                scopes_output.append(f"{indent}$var wire   {size} {identifier} {corrected_name} $end\n")
            elif size < 100:
                scopes_output.append(f"{indent}$var wire  {size} {identifier} {corrected_name} $end\n")    
            else:
                scopes_output.append(f"{indent}$var wire {size} {identifier} {corrected_name} $end\n")
# Generate VCD Header
def generate_vcd_header(vcd):
    header = []
    
    # Add version and timescale
    header.append("$version Generated by VCDSignalTracker $end\n")
    header.append(f"$timescale 1{vcd.timescale.get('unit')} $end\n")  # Adjust timescale unit as needed

    # Build the scope hierarchy from monitored data
    all_scopes = build_scope_hierarchy(vcd)
    
    # Capture scopes in the header
    scopes_output = []
    write_scopes(scopes_output, all_scopes)  # Modified write_scopes to take a list
    
    # Add scope outputs to the header
    header.extend(scopes_output)
    
    # End of definitions section
    header.append("$enddefinitions $end\n")

    # Convert list to a string for easy printing
    return ''.join(header)
# Generate VCD Files for each clock cycle
def generate_vcd_files_with_groups(start_time, num_cycles, monitored_data_groups, output_folder):
    """
    Generate VCD files for each group, creating a folder for each group and files for each clock cycle.

    Args:
        start_time (int): Starting time for the cycles.
        num_cycles (int): Number of cycles to generate VCD files for.
        monitored_data_groups (dict): Dictionary of monitored data, structured by groups.
        output_folder (str): Root folder to save the output files.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Step 1: Generate identical VCD header 
    vcd_header = generate_vcd_header(vcd)  

    start_cycle_time = time_module.time()
    clock_period = args.clock if args.clock else 2

    # Step 2: Process each group and create a folder for it
    for group_id, group_data in monitored_data_groups.items():

        # Create a folder for each group
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # Initialize last known value for each signal in the group
        last_value = {signal: '0' * sizes[signal] for signal in group_data}

        # Step 3: Generate VCD files for each cycle within the group
        for cycle in range(num_cycles):
            cycle_time = start_time + cycle * clock_period
            vcd_file_path = os.path.join(output_folder, f"cycle_{cycle_time}.vcd")
            with open(vcd_file_path, 'w') as f:
                f.write(vcd_header)

                f.write(f"#{cycle_time}\n")  # Start of the cycle

                for signal, data in group_data.items():
                    identifier = identifiers[signal]
                    current_value = last_value[signal]
                    for t, value in data:
                        if t == cycle_time:
                            current_value = value if 'x' not in value else last_value[signal]
                            break

                    last_value[signal] = current_value 
                    size = sizes[signal]
                    if size == 1:
                        f.write(f"{current_value}{identifier}\n")
                    else:
                        f.write(f"b{current_value} {identifier}\n")

                f.write(f"#{cycle_time+1}\n")  

                for signal, data in group_data.items():
                    identifier = identifiers[signal]
                    current_value = last_value[signal]
                    for t, value in data:
                        if t == (cycle_time+1):
                            current_value = value if 'x' not in value else last_value[signal]
                            break
                    last_value[signal] = current_value 
                    size = sizes[signal]
                    if size == 1:
                        f.write(f"{current_value}{identifier}\n")
                    else:
                        f.write(f"b{current_value} {identifier}\n")

                f.write(f"#{cycle_time+2}\n") 

                for signal, data in group_data.items():
                    identifier = identifiers[signal]
                    current_value = last_value[signal]
                    size = sizes[signal]
                    if size == 1:
                        f.write(f"{current_value}{identifier}\n")
                    else:
                        f.write(f"b{current_value} {identifier}\n")

                f.write("$end\n")

            # Step 4: Optionally generate SAIF files
            saif_file_path = os.path.join(output_folder, f"cycle_{cycle_time}.saif")
            os.system(f"vcd2saif -input {vcd_file_path} -output {saif_file_path} >> log_vcd2saif_converter.log")

            # Remove VCD file if specified
            if args.remove_vcd_files:
                while not os.path.exists(saif_file_path):
                    time_module.sleep(1)  # Wait for the conversion to complete
                os.remove(vcd_file_path)

    print(f"VCD files generated for all groups in {time_module.time() - start_cycle_time:.2f} seconds.")
# Generate VCD Files for each monitored data group
def generate_one_vcd_file_monitored_data(monitored_data_groups, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Step 1: Create identical header for all VCD files
    vcd_header = generate_vcd_header(vcd)

    start_generate_time = time_module.time()

    # Process each group in monitored_data_groups
    for group_id, group_data in tqdm(monitored_data_groups.items(), total=len(monitored_data_groups), desc="Writing VCD files", unit=" groups"):

        vcd_file_path = os.path.join(output_folder, f"monitored_data_group_{group_id}.vcd")

        with open(vcd_file_path, 'w') as f:
            f.write(vcd_header)

             # Collect all (time, signal_name, value) tuples
            all_changes = []
            for signal_name, time_value_pairs in group_data.items():
                identifier = identifiers.get(signal_name)
                if not identifier:
                    print(f"Warning: No identifier found for signal {signal_name}. Skipping.")
                    continue

                for time, value in time_value_pairs:
                    all_changes.append((time, signal_name, value, identifier))

            # Sort all changes by time
            all_changes.sort(key=lambda x: x[0])

            # Write changes in sorted order
            for time, signal_name, value, identifier in all_changes:
                f.write(f"#{time}\n")
                if len(value) == 1:
                    f.write(f"{value}{identifier}\n")
                else:
                    f.write(f"b{value} {identifier}\n")

            f.write("$end\n")

        # Optional SAIF generation
        if args.generate_saif_files:
            saif_file_path = os.path.join(output_folder, f"monitored_data_group_{group_id}.saif")
            os.system(f"vcd2saif -input {vcd_file_path} -output {saif_file_path} >> saif.log")

            # Optional removal of VCD file
            if args.remove_vcd_files:
                while not os.path.exists(saif_file_path):
                    time_module.sleep(1)  # Wait for SAIF generation to complete
                os.remove(vcd_file_path)

    print(f"All monitored data groups written to VCD files in {time_module.time() - start_generate_time:.2f} seconds.")

##### Helper Functions
def validate_instances(input_instances, signals):

    available_instances = list(set('.'.join(signal.split('.')[:-1]) for signal in signals))

    valid_instances = []
    for instance in input_instances:
        # Exact match check
        if instance in available_instances:
            valid_instances.append(instance)
        else:
            # Check if the instance name is a part of any available instance
            close_matches = [avail_instance for avail_instance in available_instances if instance in avail_instance and avail_instance.endswith(instance)]
            if len(close_matches) == 1:
                valid_instances.append(close_matches[0])
            elif close_matches:
                print(f"Instance '{instance}' not found. Did you mean one of the following?")
                for i, match in enumerate(close_matches):
                    print(f"{i + 1}: {match}")
                print("Enter the index of the instances you want to select:")
                
                choice = input("Your choice (comma-separated for multiple, 'all' for all): ").strip()
                if choice == 'all':
                    valid_instances.extend(close_matches)
                else:
                    try:
                        selected_indices = [int(idx) - 1 for idx in choice.split(',')]
                        for selected_index in selected_indices:
                            valid_instances.append(close_matches[selected_index])
                    except (ValueError, IndexError):
                        print(f"Invalid input. Skipping instance '{instance}'.")
            else:
                print(f"No close matches found for '{instance}'. Please enter a valid instance name.")
                return validate_instances(input("Enter valid instance(s): ").split(), signals)

    if not valid_instances:
        print("No valid instances were provided. Please try again.")
        return validate_instances(input("Enter valid instance(s): ").split(), signals)

    return valid_instances

def find_signals_with_string(signals, target_string):
    matching_signals = []
    for signal in signals:
        if target_string in signal:
            matching_signals.append(signal)
    return matching_signals

def find_enable_signals():
    # Find enable signals (if any)
    selected_enable = []
    print("Searching for enable signals...")
    for select_args in args.enable:
        matching_signals = find_signals_with_string(vcd.get_signals(), select_args)

        if matching_signals:
            if len(matching_signals) == 1:
                selected_enable.append(matching_signals[0])
                print(f"Selected enable signal: {matching_signals[0]}")
            else:
                print("Multiple matching enable signals found. Please select one:")
                for idx, signal in enumerate(matching_signals, start=1):
                    print(f"{idx}: {signal}")
                try:
                    choice = int(input("Enter the number of the enable signal you want to select: "))
                except ValueError:
                    print("Invalid input! Please enter a number.")
                    exit()
                if choice not in range(1, len(matching_signals) + 1):
                    print("Invalid choice. Exiting...")
                    exit()
                selected_enable.append(matching_signals[choice - 1])
                print(f"Selected enable signal: {matching_signals[choice - 1]}")
        else:
            print(f"No enable signals found containing '{select_args}'. Exiting...")
            exit()
    return selected_enable

##### Main Function
if __name__ == "__main__":

    args = parse_args()

    # Extract VCD files
    vcd_files = []
    if args.folder:
        for file in os.listdir(args.folder):
            if file.endswith(".vcd"):
                vcd_files.append(os.path.join(args.folder, file))
    elif args.vcd_file:
        vcd_files.append(args.vcd_file)

    # Process each VCD file
    for vcd_file in vcd_files:

        print("=====================================")
        if not args.clock:
            print("Reading Scopes and Signals definitions of VCD file...")
        else:
            print("Reading VCD files, monitoring signals and generating output files...")

        start_time_definition = time_module.time()
        vcd = VCDPARSE(vcd_path=vcd_file)
        vcd.read_definitions()
        end_time_definition = time_module.time()
        if not args.clock:
            print(f"Read successfully in {end_time_definition - start_time_definition:.2f} seconds.")
            print(f"Total number of signals: {len(vcd.get_signals())}")

            print("=====================================")
        # Check if instances are provided, if not, select all
        if not args.instances:
            if not args.clock:
                print("No instances specified. Monitoring all instances.")
            instances = "All"
        else:
            # Validate the provided instances
            instances = validate_instances(args.instances, vcd.get_signals())

        def filter_signals_by_instance(signals, instances):
            return [signal for signal in signals if any(instance in signal for instance in instances)]

        # Filter signals to include only those that belong to the specified instances
        signals = filter_signals_by_instance(vcd.get_signals(), instances) if instances!="All" else vcd.get_signals()

        # Find enable signals (if any)
        selected_enable = []
        if args.enable:
            selected_enable = find_enable_signals()
        if not selected_enable:
            if not args.clock:
                print("No enable signals provided, monitoring all times...")
        
        signals = selected_enable + signals

        if not args.clock:
            print("=====================================")
            print("Removing unwanted signals...")
            
        # Remove unwanted signals from the vcd object
        unwanted_signals = set(vcd.get_signals()) - set(signals)
        for signal in unwanted_signals:
            vcd.get_data().pop(signal, None)
            vcd.get_signals().remove(signal)
        
        if not args.clock:
            print(f"Total number of signals to monitor: {len(vcd.get_signals())}")
        
        if not args.clock:
            print("=====================================")
            print("Reading value changes...")
        start_time_read_changes = time_module.time()
        start_time, end_time = args.time if args.time else None, None
        vcd.read_value_changes(start_time, end_time)
        end_time_read_changes = time_module.time()
        if not args.clock:
            print(f"Read value changes successfully in {end_time_read_changes - start_time_read_changes:.2f} seconds.")
            print(f"Total time duration of VCD file: {vcd.get_begintime()} to {vcd.get_endtime()}.")

            print("=====================================")

        if not args.hamming_distance:  
            print("Monitoring signals...")
            start_time_monitor = time_module.time() 
            monitored_data_groups = monitor_signals(vcd, vcd.get_signals(), selected_enable)
            end_time_monitor = time_module.time()
            print(f"Monitoring data collected successfully in {end_time_monitor - start_time_monitor:.2f} seconds.")

            print("=====================================")
            print("Generating output files...")
            start_time_generate = time_module.time()
            output_folder = os.path.join(args.output_folder if args.output_folder else "output", os.path.splitext(os.path.basename(vcd_file))[0])
            clock_period = args.clock if args.clock else 2
            start_time, end_time = args.time if args.time else (vcd.get_begintime(), vcd.get_endtime())
            num_cycles = math.ceil((end_time - start_time) / clock_period)
            if args.clock:
                generate_vcd_files_with_groups(start_time, num_cycles, monitored_data_groups, output_folder)
            else:
                generate_one_vcd_file_monitored_data(monitored_data_groups, output_folder)
            end_time_generate = time_module.time()
            if not args.clock:
                print(f"Output files generated successfully in {end_time_generate - start_time_generate:.2f} seconds.")
            else:
                print(f"Output files generated successfully in {end_time_generate - start_time_definition:.2f} seconds.")
            print("=====================================")
        else:
            print("Calculating Hamming distance...")
            start_time_hamming = time_module.time()
            hamming_distances = {}
            for signal in vcd.get_signals():
                signal_data = vcd[signal].hamming_distance
                hamming_distances[signal] = signal_data

            output_folder = args.output_folder if args.output_folder else "output"
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            output_file = os.path.join(output_folder, f"hamming_distances_{os.path.basename(vcd_file)}.json")
            with open(output_file, 'w') as f:
                json.dump(hamming_distances, f, indent=4)

            end_time_hamming = time_module.time()
            print(f"Hamming distance calculated and written to {output_file} successfully in {end_time_hamming - start_time_hamming:.2f} seconds.")
            print("=====================================")