# tempcalib.py

Universal temperature calibration script for Bruker TopSpin, supporting 1D, 2D, and 3D datasets, including CON spectra. 

## Overview
`tempcalib.py` is a Python/Jython automation script designed to accurately reference NMR chemical shifts based on sample temperature. It calculates the correct water shift using the formula `-(temp / 96.9) + 7.83` and applies the necessary adjustments to Spectrometer Frequencies (SF) and Spectral References (SR). To ensure maximum precision, the script utilizes direct disk read access to `acqus` and `procs` files to extract fundamental parameters like SFO, BF1, and TE. 

## Features
* **Universal Dimensionality:** Automatically detects and processes 1D, 2D, and 3D parameter modes.
* **Intelligent Nuclei Assignment:** Identifies 1H, 15N, and 13C nuclei up to 64-bit precision and maps them correctly to processing dimensions F1, F2, and F3.
* **Automatic TROSY Correction:** Detects TROSY pulse programs (via the `PULPROG` parameter) and dynamically applies a $\pm$ 46 Hz offset to 1H and 15N dimensions.
* **Smart Off-Resonance Detection:** Checks if the 1H transmitter (O1P/O2P) deviates by more than 0.5 ppm from 4.700 ppm. If off-resonance is detected, it triggers a warning dialog requesting the nominal water shift to accurately back-calculate the calibration.
* **Automated Data Processing:** After saving the calibrated parameters, the script automatically executes the relevant processing commands (e.g., `efp` for 1D, `xfb` for 2D, and prompts for `ftnd` for 3D datasets).
* **Custom Parameter Storage:** Saves the final temperature and calculated water shift to TopSpin's `USERP1` and `USERP2` parameters for future reference.

## Prerequisites
* Bruker TopSpin (supports standard Python/Jython macro execution).
* An acquired 1D, 2D, or 3D dataset loaded in the active TopSpin window.

## Installation
You can easily create the script directly from within TopSpin:

1. In the TopSpin command line, type:
   ```text
   edpy tempcalib
   ```
2. A built-in editor window will open. Copy the entire content of the `tempcalib.py` script from this repository and paste it into the editor.
3. Save the file and close the editor window. The script is now ready to use.

## Usage
1. Open your target dataset in Bruker TopSpin.
2. In the TopSpin command line, execute the script by typing:
   ```text
   xpy tempcalib
   ```
3. A "Temperature Calibration" dialog box will appear, displaying the detected dimensionality, active nuclei, and whether TROSY is active.
4. The script will attempt to read the true temperature from the `TE` parameter. If it is outside physical liquid NMR limits (below 250.0 K or above 400.0 K), it defaults to 298.0 K. Confirm or adjust this value.
5. **Off-Resonance Warning:** If the 1H channel is detected to be off-resonance, the dialog will expand to include a field for "Nominal water shift [ppm]". Input the intended water shift (defaulting to 4.700).
6. Click **OK**. 
7. The script will calculate the shifts, write the parameters to disk, print a summary of the calibration (SF in MHz and SR in Hz) to a message window, and execute standard TopSpin Fourier transform commands to update the spectrum visually.