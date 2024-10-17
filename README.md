# VCD Signal Tracker

**Version**: 1.0

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
- `--time`: Specify the start and end times for signal monitoring (in clock cycles).
- `--clock`: Specify the clock period to divide the signals into separate cycles.
- `--generate_saif_files`: If specified, generates SAIF files for each clock cycle.
- `--remove_vcd_files`: If specified, removes the VCD files after SAIF file generation.
- `--output_folder`: Specify a folder to store the generated SAIF or VCD files.

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
