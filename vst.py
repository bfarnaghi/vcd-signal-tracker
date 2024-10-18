import  argparse
from    collections.abc import MutableMapping
import  bisect
import  io
import  math
import  re
from    decimal import Decimal
from    pprint import PrettyPrinter
import  os
import  time
import  random
import  string
import  difflib

##### Parse Command Line Arguments

def parse_args():
    parser = argparse.ArgumentParser(description="Parse and analyze VCD files.")
    parser.add_argument("vcd_file", help="Path to the VCD file.")
    parser.add_argument("-i","--instances", type=str, nargs='+', help="List of instance names to track")
    parser.add_argument("-t", "--time", nargs=2, type=int, help="Start time and end time of monitoring.")
    parser.add_argument("-c", "--clock", type=int, help="Clock period for each cycle.")
    parser.add_argument("-saif", "--generate_saif_files", action="store_true", help="Generate SAIF files for each cycle.")
    parser.add_argument("-rmvcd", "--remove_vcd_files", action="store_true", help="Remove VCD files after generating SAIF files.")
    parser.add_argument("-o", "--output_folder", help="Output folder for generated VCD and SAIF files.")
    return parser.parse_args()

##### Enhance VCD Parsing Logic

pp = PrettyPrinter()
_RE_TYPE = type(re.compile(''))

class VCDPARSE(object):
    _VALUE = set(('0', '1', 'x', 'X', 'z', 'Z'))
    _VECTOR_VALUE_CHANGE = set(('b', 'B', 'r', 'R'))

    def __init__(self, vcd_path=None, only_sigs=False, signals=None, store_tvs=True, store_scopes=False, vcd_string=None):
        self.hierarchy = {}
        self.scopes = {}
        scopes_stack = [self.hierarchy]
        self.data = {}
        self.endtime = 0
        self.begintime = 0
        self.references_to_ids = {}
        self.signals = []
        self.timescale = {}
        self.signal_changed = False

        self._store_tvs = store_tvs

        if signals is None:
            signals = []
        all_sigs = not signals
        cur_sig_vals = {}
        hier = []
        num_sigs = 0
        time = 0
        first_time = True

        def handle_value_change(line):
            value = line[0]
            identifier_code = line[1:]
            self._add_value_identifier_code(time, value, identifier_code, cur_sig_vals)

        def handle_vector_value_change(line):
            value, identifier_code = line[1:].split()
            self._add_value_identifier_code(time, value, identifier_code, cur_sig_vals)

        if vcd_string is not None:
            vcd_file = io.StringIO(vcd_string)
        else:
            vcd_file = open(vcd_path, 'r')
        while True:
            line = vcd_file.readline()
            if line == '':
                break
            line0 = line[0]
            line = line.strip()
            if line == '':
                continue
            if line0 == '#':
                time = int(line.split()[0][1:])
                if first_time:
                    self.begintime = time
                    first_time = False
                self.endtime = time
                self.signal_changed = False
                changes = list(filter(None, line.split()[1:]))
                if len(changes) > 0:
                    for change in changes:
                        if change[0] in self._VALUE:
                            handle_value_change(change)
                        elif change[0] in self._VECTOR_VALUE_CHANGE:
                            raise Exception("Vector value changes have to be on a separate line!")
            elif line0 in self._VECTOR_VALUE_CHANGE:
                handle_vector_value_change(line)
            elif line0 in self._VALUE:
                handle_value_change(line)
            elif '$enddefinitions' in line:
                if only_sigs:
                    break
            elif '$scope' in line:
                scope_name = line.split()[2]
                hier.append(scope_name)
                if store_scopes:
                    full_scope_name = '.'.join(hier)
                    new_scope = Scope(full_scope_name, self)
                    scopes_stack[-1][scope_name] = new_scope
                    self.scopes[full_scope_name] = new_scope
                    scopes_stack.append(new_scope)
            elif '$upscope' in line:
                hier.pop()
                if store_scopes:
                    scopes_stack.pop()
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
                if store_scopes:
                    scopes_stack[-1][name] = reference
                if (reference in signals) or all_sigs:
                    self.signals.append(reference)
                    if identifier_code not in self.data:
                        self.data[identifier_code] = Signal(size, type)
                    self.data[identifier_code].references.append(reference)
                    self.references_to_ids[reference] = identifier_code
                    cur_sig_vals[identifier_code] = 'x'
            elif '$timescale' in line:
                if not '$end' in line:
                    while True:
                        line += " " + vcd_file.readline().strip().rstrip()
                        if '$end' in line:
                            break
                timescale = ' '.join(line.split()[1:-1])
                magnitude = Decimal(re.findall(r"\d+|$", timescale)[0])
                unit = re.findall(r"s|ms|us|ns|ps|fs|$", timescale)[0]
                factor = {
                    "s": '1e0',
                    "ms": '1e-3',
                    "us": '1e-6',
                    "ns": '1e-9',
                    "ps": '1e-12',
                    "fs": '1e-15',
                }[unit]
                self.timescale["timescale"] = magnitude * Decimal(factor)
                self.timescale["magnitude"] = magnitude
                self.timescale["unit"] = unit
                self.timescale["factor"] = Decimal(factor)
        vcd_file.close()

    def _add_value_identifier_code(self, time, value, identifier_code, cur_sig_vals):
        if identifier_code in self.data:
            entry = self.data[identifier_code]
            self.signal_changed = True
            if self._store_tvs:
                entry.tv.append((time, value))
            cur_sig_vals[identifier_code] = value

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

    def get_data(self):
        return self.data

    def get_begintime(self):
        return self.begintime
    
    def get_endtime(self):
        return self.endtime

    def get_signals(self):
        return self.signals

    def get_timescale(self):
        return self.timescale

class Signal(object):
    def __init__(self, size, var_type):
        self.size = size
        self.var_type = var_type
        self.references = []
        self.tv = []
        self.endtime = None

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

    def __repr__(self):
        return pp.pformat(self.__dict__)

class Scope(MutableMapping):
    def __init__(self, name, vcd):
        self.vcd = vcd
        self.name = name
        self.subElements = {}

    def __len__(self):
        return len(self.subElements)

    def __iter__(self):
        return iter(self.subElements)

    def __setitem__(self, key, value):
        self.subElements[key] = value

    def __delitem__(self, key):
        del self.subElements[key]

    def __getitem__(self, key):
        return self.subElements[key]

    def __repr__(self):
        return pp.pformat(self.__dict__)

##### Monitor Signals

def monitor_signals(vcd, signals, instances, start_time, end_time):
    
    # Filter signals to include only those that belong to the specified instances
    def filter_signals_by_instance(signals, instances):
        filtered_signals = []
        for signal in signals:
            # Assuming signal scope is in signal.name (or another appropriate attribute)
            # Modify this depending on how the signal's full scope name is stored
            if any(instance in signal for instance in instances):
                filtered_signals.append(signal)
        return filtered_signals

    # First filter the signals based on user-specified instances
    filtered_signals = filter_signals_by_instance(signals, instances) if instances!="All" else signals

    monitored_data = {signal: [] for signal in filtered_signals}
    for signal in filtered_signals:
        sig_data = vcd[signal].tv  # Time-value pairs for the signal
        for time, value in sig_data:
            if start_time <= time <= end_time:
                monitored_data[signal].append((time, value))
    
    return monitored_data

##### Write Output

def build_scope_hierarchy(monitored_data):
    all_scopes = {}
    for signal in monitored_data.keys():
        parts = signal.split('.')
        current_scope = all_scopes
        for part in parts[:-1]:  # Exclude the signal name itself
            if part not in current_scope:
                current_scope[part] = {}
            current_scope = current_scope[part]
        current_scope[parts[-1]] = signal  # Final part is the signal itself
    return all_scopes

def generate_identifier():
    # Ensure the first character is a letter (to avoid starting with a number)
    first_char = random.choice(string.ascii_uppercase)
    # Generate the remaining 5 characters from uppercase letters and digits
    remaining_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return first_char + remaining_chars

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

def generate_vcd_header(monitored_data):
    header = []
    
    # Add version and timescale
    header.append("$version Generated by VCDSignalTracker $end\n")
    header.append(f"$timescale 1{vcd.timescale.get('unit')} $end\n")  # Adjust timescale unit as needed

    # Build the scope hierarchy from monitored data
    all_scopes = build_scope_hierarchy(monitored_data)
    
    # Capture scopes in the header
    scopes_output = []
    write_scopes(scopes_output, all_scopes)  # Modified write_scopes to take a list
    
    # Add scope outputs to the header
    header.extend(scopes_output)
    
    # End of definitions section
    header.append("$enddefinitions $end\n")

    # Convert list to a string for easy printing
    return ''.join(header)

def generate_vcd_files_with_monitored_data(start_time,end_time,num_cycles, monitored_data, output_folder):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Step 1: Create identical header for all VCD files
    vcd_header = generate_vcd_header(monitored_data)

    # Step 2: Append specific monitored data for each cycle
    start_cycle_time = time.time()
    for cycle in range(num_cycles):
        cycle_time = start_time + cycle * clock_period
        vcd_file_path = os.path.join(output_folder, f"cycle_{cycle_time}.vcd")
        with open(vcd_file_path, 'w') as f:

            f.write(vcd_header)

            # Write signal value changes for the given cycle
            f.write(f"#{cycle_time}\n")  # Mark the current cycle
            for idx, (signal, data) in enumerate(monitored_data.items(), start=1):
                identifier = identifiers[signal]
                last_value = 'x'  # Default initial value
                for t, value in data:
                    if t == cycle_time:
                        if 'x' in value:
                            value = last_value
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{value}{identifier}\n")
                        else:
                            f.write(f"b{value} {identifier}\n")
                    last_value = value
                # If no value change at cycle_time, use the last known value
                if cycle_time not in [t for t, _ in data]:
                    if last_value != 'x':  # Only write if last_value is not the default 'x'
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{last_value}{identifier}\n")
                        else:
                            f.write(f"b{last_value} {identifier}\n")

            f.write(f"#{cycle_time+1}\n")  # Mark the current cycle
            for idx, (signal, data) in enumerate(monitored_data.items(), start=1):
                identifier = identifiers[signal]
                last_value = 'x'  # Default initial value
                for t, value in data:
                    if t == (cycle_time+1):
                        if 'x' in value:
                            value = last_value
                        #size = len(value) if isinstance(value, str) else 1
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{value}{identifier}\n")
                        else:
                            f.write(f"b{value} {identifier}\n")
                    last_value = value
                # If no value change at cycle_time+1, use the last known value
                if (cycle_time+1) not in [t for t, _ in data]:
                    if last_value != 'x':  # Only write if last_value is not the default 'x'
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{last_value}{identifier}\n")
                        else:
                            f.write(f"b{last_value} {identifier}\n")
            
            f.write(f"#{cycle_time+2}\n")  # Mark the current cycle
            for idx, (signal, data) in enumerate(monitored_data.items(), start=1):
                identifier = identifiers[signal]
                last_value = 'x'  # Default initial value
                for t, value in data:
                    if t == (cycle_time+2):
                        if 'x' in value:
                            value = last_value
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{value}{identifier}\n")
                        else:
                            f.write(f"b{value} {identifier}\n")
                    last_value = value
                # If no value change at cycle_time+2, use the last known value
                if (cycle_time+2) not in [t for t, _ in data]:
                    if last_value != 'x':  # Only write if last_value is not the default 'x'
                        size = sizes[signal]
                        if size == 1:
                            f.write(f"{last_value}{identifier}\n")
                        else:
                            f.write(f"b{last_value} {identifier}\n")

            f.write("$end\n")

        if args.generate_saif_files:
            # Step 3: Generate SAIF files for each cycle using vcd2saif command
            saif_file_path = os.path.join(output_folder, f"cycle_{cycle}.saif")
            os.system(f"vcd2saif -input {vcd_file_path} -output {saif_file_path} >> saif.log")

            # Wait for the conversion to complete before removing the VCD file
            if args.remove_vcd_files:
                while not os.path.exists(saif_file_path):
                    time.sleep(1)  # Wait for 1 second before checking again
                os.remove(vcd_file_path)
    
    print(f"Monitored data written to VCD files for each cycle in {time.time() - start_cycle_time:.2f} seconds.")

def validate_instances(input_instances, signals):
    #available_instances = list(set(signal.split('.')[-2] for signal in signals))
    available_instances = list(set('.'.join(signal.split('.')[:-1]) for signal in signals))

    valid_instances = []
    for instance in input_instances:
        # Exact match check
        if instance in available_instances:
            valid_instances.append(instance)
        else:
            # Check if the instance name is a part of any available instance
            close_matches = [avail_instance for avail_instance in available_instances if instance in avail_instance]
            if close_matches:
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

if __name__ == "__main__":

    args = parse_args()
    print("=====================================")
    print("Parsing VCD file...")
    start_parse_time = time.time()
    vcd = VCDPARSE(vcd_path=args.vcd_file)
    end_parse_time = time.time()
    print(f"VCD file parsed successfully in {end_parse_time - start_parse_time:.2f} seconds.")
    
    start_time, end_time = args.time if args.time else (vcd.get_begintime(), vcd.get_endtime())
    print(f"Total time duration of vcd file: {vcd.get_begintime()} to {vcd.get_endtime()}.")
    print(f"Monitoring signals from time {start_time} to {end_time}.")
    print(f"Total time duration: {end_time - start_time} ps.")
    print(f"Total number of signals: {len(vcd.get_signals())}")

    clock_period = args.clock if args.clock else 2
    output_folder = args.output_folder if args.output_folder else "output"

    num_cycles = math.ceil((end_time - start_time) / clock_period)
    print(f"Total number of cycles: {num_cycles}")
    print("=====================================")

    #Check if instances are provided, if not, select all
    if not args.instances:
        print("No instances specified. Monitoring all instances.")
        instances = "All"
    else:
        # Validate the provided instances
        instances = validate_instances(args.instances, vcd.get_signals())

    print("Monitoring signals...")
    monitored_data = monitor_signals(vcd, vcd.get_signals(),instances, start_time, end_time)
    end_monitor_time = time.time()
    print(f"Monitoring data collected successfully in {end_monitor_time - end_parse_time:.2f} seconds.")
    print("=====================================")

    print("Generating output files...")
    generate_vcd_files_with_monitored_data(start_time,end_time,num_cycles, monitored_data, output_folder)

    print("=====================================")
    print(f"Output files generated successfully in {time.time() - start_parse_time:.2f} seconds.")
