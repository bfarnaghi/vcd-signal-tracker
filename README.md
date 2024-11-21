# VCD Signal Tracker

## Version 1.0 

VCD Signal Tracker is a tool designed for parsing Value Change Dump (VCD) files and generating Switching Activity Interchange Format (SAIF) files for each clock cycle. These files are crucial for power estimation in digital circuit design. The tool also provides features like time-interval-based filtering, clock cycle analysis, and management of output files.

## Features

- **Parse VCD Files**: Extract and track signal information and changes in values.
- **Time-Interval Monitoring**: Allows monitoring signal changes between specific time ranges.
- **SAIF Generation**: Generates SAIF files for each clock cycle based on signal activity.
- **Clock-Cycle Based Analysis**: Supports custom clock periods for cycle-level analysis.
- **Output Management**: Option to store generated SAIF files in a specific folder or remove original VCD files after processing.

## Usage

To use VCD Signal Tracker, run the script with the following arguments:

### Command Line Arguments

- `vcd_file`: Path to the input VCD file to parse.
- `-t` or `--time`: Specify the start and end times for signal monitoring (in clock cycles).
- `-c` or `--clock`: Specify the clock period to divide the signals into separate cycles.
- `-saif` or `--generate_saif_files`: If specified, generates SAIF files for each clock cycle. (Using vcd2saif tool provided by Synopsys)
- `-rmvcd` or `--remove_vcd_files`: If specified, removes the VCD files after SAIF file generation.
- `-o` or `--output_folder`: Specify a folder to store the generated SAIF or VCD files.

### Example Command

```bash
python vst.py input.vcd --time 100 200 --clock 10 --generate_saif_files --output_folder output/
```

This command will:
- Parse the VCD file `input.vcd`.
- Monitor signal changes between clock cycles 100 and 200.
- Divide the signals into cycles with a clock period of 10 units.
- Generate SAIF files for each clock cycle.
- Store the generated files in the `output/` folder.

### Optional Arguments

- `-saif`: Generates SAIF files for each clock cycle.
- `-rmvcd`: Removes VCD files after generating SAIF files.
- `-o`: Specifies the output directory for generated files.




## Version 2.0 Updates

In Version 2.0, you can specify instances to monitor within the VCD file, allowing you to focus only on signals belonging to specific instances rather than processing all signals. Additionally, you can designate an enable signal to monitor output only when it is set to 1. 
For larger programs, outputs can also be grouped based on the gap between monitored signals, enhancing manageability. These features can be configured using the following command-line arguments.

### Command-Line Arguments

- `-f` or `--folder`: Path to the folder containing VCD files.
- `-i` or `--instances`: Specify list of instance names to track.
- `-e` or `--enable`: Enable signal to monitor selected signals.
- `-g` or `--enable_gap_threshold`: Specify the maximum allowed gap between enable signals to group output.
 
#### Example Usage
**Monitor signals only from the instance named `DUT`:**
```bash
python vst.py input.vcd --instances DUT --time 0 10000
```

- If you do not provide any instances, the script will monitor **all available instances**.
- You can define instances by providing part of the instance name (e.g., `DUT`). The script will then track all signals that include the specified instance at any level in the hierarchy.
- If the provided instance is not found, the script will suggest similar available instances for selection or allow you to choose to track all similar instances.

For instance, when analyzing a hardware module, you can specify the required instance to monitor. If using the gap feature, the extracted VCD files will generate VCD data for each clock cycle across all VCD files from the previous run. This enables detailed access to switching activity per clock cycle.



## Version 3.0 Updates

In Version 3.0, the VCD file reading process has been optimized by removing unnecessary parts. Initially, scopes and signals are read and displayed, allowing users to select the required instances or enable signals. Unwanted signals are then removed from tracking, reducing memory usage.

In this version:
- The `--gap` argument has been removed. Data is now automatically grouped based on the start and end times of each enable signal window.
- The Hamming distance for each signal is calculated during the VCD file reading process and can be saved to a JSON file using a new argument.

### Command-Line Argument

- `-hd` or `--hamming_distance`: Calculate Hamming distance for each signal.
 
#### Example Usage
**Monitor signals only from the instance named `DUT`, use the enable signal `trigger`, convert the output to an SAIF file, and remove the VCD file after conversion:**
```bash
python vst.py input.vcd --instances DUT -e trigger -saif -rmvcd
```
**Monitor signals only from the instance named `DUT`, calculate the Hamming distances for each signal in this instance, and save the output in the `json` folder:**
```bash
python vst.py input.vcd --instances DUT -hd -o json
```
