# -*- coding: utf-8 -*-
import mne
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import os
import numpy as np

# this file makes a topographical map of the scalp with elctrodes signal strenghths displayed 

# Load EDF files and concatenate
folder_path = r'C:\Users\rashe\OneDrive - University of Calgary\Desktop\edf\S01' # change this to the file location of the subject you want 
edf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.edf')] # gets the all the edf file into edf_files
raw_list = [mne.io.read_raw_edf(file, preload=True, verbose="error") for file in edf_files] # reads the files 
raw = mne.concatenate_raws(raw_list) # puts all the the raw signal toghther 

# Apply Notch plus Harmonics 
raw.notch_filter(freqs=60, picks='eeg', verbose=True)

# Apply bandpass filter (8–13 Hz)
raw.filter(l_freq=8, h_freq=13, picks='eeg', verbose=True)

# Apply CAR 
#raw.set_eeg_reference('average', projection=False)


# Define the list of channels you want to keep
channels_to_keep = ['Fc3.', 'C3..', 'C1..', 'Fcz.', 'Cz..', 'C2..', 'C4..', 'Fc4.']  # Replace with your desired channel names

# Select only the specified channels
raw. pick_channels(channels_to_keep)

# The raw object now contains only the selected channels
print(f"Selected channels: {raw.info['ch_names']}")



# Define the positions of electrodes using the 10-10 system
eeg_positions_10_10 = {
    "Fp1.": (-0.5, 1.0), "Fp2.": (0.5, 1.0), "Fpz.": (0.0, 1.0),
    "Af7.": (-0.75, 0.75), "Af3.": (-0.25, 0.75), "Afz.": (0.0, 0.75), "Af4.": (0.25, 0.75), "Af8.": (0.75, 0.75),
    "F7..": (-1.0, 0.5), "F5..": (-0.75, 0.5), "F3..": (-0.5, 0.5), "F1..": (-0.25, 0.5),
    "Fz..": (0.0, 0.5), "F2..": (0.25, 0.5), "F4..": (0.5, 0.5), "F6..": (0.75, 0.5), "F8..": (1.0, 0.5), 
    "Ft7.": (-1.0, 0.3), "Fc5.": (-0.75, 0.3), "Fc3.": (-0.5, 0.3), "Fc1.": (-0.25, 0.3),
    "Fcz.": (0.0, 0.3), "Fc2.": (0.25, 0.3), "Fc4.": (0.5, 0.3), "Fc6.": (0.75, 0.3), "Ft8.": (1.0, 0.3),
    "T9..": (-1.2, 0.0), "T7..": (-1.0, 0.0), "C5..": (-0.75, 0.0), "C3..": (-0.5, 0.0), "C1..": (-0.25, 0.0),
    "Cz..": (0.0, 0.0), "C2..": (0.25, 0.0), "C4..": (0.5, 0.0), "C6..": (0.75, 0.0), "T8..": (1.0, 0.0), "T10.": (1.2, 0.0),
    "Tp7.": (-1.0, -0.3), "Cp5.": (-0.75, -0.3), "Cp3.": (-0.5, -0.3), "Cp1.": (-0.25, -0.3),
    "Cpz.": (0.0, -0.3), "Cp2.": (0.25, -0.3), "Cp4.": (0.5, -0.3), "Cp6.": (0.75, -0.3), "Tp8.": (1.0, -0.3),
    "P7..": (-1.0, -0.5), "P5..": (-0.75, -0.5), "P3..": (-0.5, -0.5), "P1..": (-0.25, -0.5),
    "Pz..": (0.0, -0.5), "P2..": (0.25, -0.5), "P4..": (0.5, -0.5), "P6..": (0.75, -0.5), "P8..": (1.0, -0.5),
    "Po7.": (-0.75, -0.75), "Po3.": (-0.25, -0.75), "Poz.": (0.0, -0.75), "Po4.": (0.25, -0.75), "Po8.": (0.75, -0.75),
    "O1..": (-0.5, -1.0), "Oz..": (0.0, -1.0), "O2..": (0.5, -1.0), "Iz..": (0.0, -1.2)
}

# Create a dictionary of positions
ch_pos = {ch: (x, y, 0.0) for ch, (x, y) in eeg_positions_10_10.items()}

# Create the custom montage
custom_montage = mne.channels.make_dig_montage(ch_pos=ch_pos, coord_frame='head')

# Apply montage
raw.set_montage(custom_montage, on_missing='ignore')

times = raw.times
sampling_interval = 1 / 160  # Step size for slider based on sampling rate

# Interactive plot with slider
fig, topo_ax = plt.subplots(figsize=(10, 8))  # Adjust figure size for larger topomap
cbar_ax = fig.add_axes([0.92, 0.15, 0.03, 0.7])  # Separate axis for colorbar
plt.subplots_adjust(bottom=0.3)

# Initial plot at time 0
time_idx = 0
data = raw.get_data()[:, time_idx]  # Extract data for the first time point
im, cm = mne.viz.plot_topomap(
    data,
    raw.info,
    axes=topo_ax,
    show=False,
    sensors=True,
    sphere=(0, 0, 0, 1.2),  # Adjust the sphere radius to make the head larger
    extrapolate="head",
    contours=24,  # Add more contour levels for better detail
    cmap='rainbow'  # Apply the rainbow colormap
)

# Add the colorbar manually
plt.colorbar(im, cax=cbar_ax)

# Add slider for time selection
ax_slider = plt.axes([0.1, 0.1, 0.8, 0.03], facecolor="lightgrey")  # Make slider longer
slider = Slider(
    ax_slider, "Time (s)", times[0], times[-1], valinit=times[0], valstep=sampling_interval
)

# Update function for the slider
def update(val):
    time = slider.val
    time_idx = (np.abs(times - time)).argmin()  # Find the nearest time index
    topo_ax.clear()
    data = raw.get_data()[:, time_idx]  # Extract data at the selected time
    im, cm = mne.viz.plot_topomap(
        data,
        raw.info,
        axes=topo_ax,
        show=False,
        sensors=True,
        sphere=(0, 0, 0, 1.2),  # Adjust sphere radius
        extrapolate="head",
        contours=4,  # Add more contour levels
        cmap='rainbow'  # Apply the rainbow colormap
    )
    fig.canvas.draw_idle()

# Add precise formatting to the slider value
def format_slider(val):
    return f"{val:.3f}"  # Show time values with 3 decimal places

slider.valtext.set_text(format_slider(slider.val))  # Set initial slider value format
slider.on_changed(update)
slider.on_changed(lambda val: slider.valtext.set_text(format_slider(val)))  # Update display format

# Function to handle arrow key presses
def on_key(event):
    current_val = slider.val
    if event.key == "right":
        new_val = min(current_val + sampling_interval, times[-1])
    elif event.key == "left":
        new_val = max(current_val - sampling_interval, times[0])
    else:
        return
    slider.set_val(new_val)  # Update the slider value

fig.canvas.mpl_connect("key_press_event", on_key)  # Connect the key press event

plt.show()





