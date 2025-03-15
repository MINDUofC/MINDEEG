import serial.tools.list_ports as device_ports
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QLineEdit, QComboBox, QDial, QCheckBox, QLabel
import logging
import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


# GET PORTS FROM COMBOBOX

def get_available_ports():
    """Returns a list of available serial ports."""
    ports = list(device_ports.comports())
    return [port.device for port in ports]

def refresh_ports_on_click(combo_box):
    """Refreshes the QComboBox with available ports when clicked."""
    combo_box.clear()  # Clear previous entries
    available_ports = get_available_ports()

    if available_ports:
        combo_box.addItems(available_ports)
    else:
        combo_box.addItem("No ports found")



# This will take in board_config data, validate it, and then
def turn_on_board(board_id_input: QLineEdit, port_input: QComboBox, channel_dial: QDial,
                     common_ref_checkbox: QCheckBox, status_bar: QLabel, isBoardOn: bool):
    """
    Initializes the EEG board based on GUI inputs.

    :param isBoardOn: bool Is the board currently on?
    :param board_id_input: QLineEdit for Board ID
    :param port_input: QComboBox for available ports
    :param channel_dial: QDial for number of channels (0 = off, 1-8 = active)
    :param common_ref_checkbox: QCheckBox for enabling common reference (RLD)
    :param status_bar: QLabel to display status updates
    """

    # Retrieve values from GUI
    board_id = board_id_input.text().strip()
    port = port_input.currentText().strip()
    num_channels = channel_dial.value()
    common_ref = common_ref_checkbox.isChecked()

    # Validate Inputs
    if not board_id or not board_id.isdigit():
        set_status(status_bar, "Error: Invalid Board ID", error=True)
        isBoardOn = False
        return
    if not port or port == "No ports found":
        set_status(status_bar, "Error: No valid port selected", error=True)
        isBoardOn = False
        return
    if num_channels == 0:
        set_status(status_bar, "Error: Channel Dial must be greater than 0", error=True)
        isBoardOn = False
        return

    board_id = int(board_id)

    # Set up BrainFlow Parameters**
    params = BrainFlowInputParams()
    params.serial_port = port
    params.timeout = 15  # Default timeout

    # Enable board logging**
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    # Display starting message
    set_status(status_bar, "Turning on...", error=False)

    try:
        board_shim = BoardShim(board_id, params)
        board_shim.prepare_session()

        logging.info(f"Board ID: {board_id} | Port: {port} | Channels: {num_channels} | RLD: {common_ref}")

        # **Generate configuration commands**
        neuro_pawn_commands = []
        for ch in range(1, num_channels + 1):
            neuro_pawn_commands.append(f"chon_{ch}_12")  # Enable channel with gain 12
            if common_ref:
                neuro_pawn_commands.append(f"rldadd_{ch}")  # Add common reference

        board_shim.start_stream(450000)
        time.sleep(2)  # Allow board time to initialize

        # **Send configuration commands**
        for command in neuro_pawn_commands:
            board_shim.config_board(command)
            logging.info(f"Sent command: {command}")
            time.sleep(0.25)

        # **Disable UI elements while the board is running**
        board_id_input.setDisabled(True)
        port_input.setDisabled(True)
        channel_dial.setDisabled(True)
        common_ref_checkbox.setDisabled(True)

        # **Display success message**
        set_status(status_bar, "Successful On", error=False)
        isBoardOn = True
        return board_shim  # Return board object for future control (turn off function)

    except Exception as e:
        logging.error("Exception occurred", exc_info=True)
        isBoardOn = False
        set_status(status_bar, f"Error: {str(e)}", error=True)



def turn_off_board(board_shim, board_id_input: QLineEdit, port_input: QComboBox, channel_dial: QDial, common_ref_checkbox: QCheckBox, status_bar: QLabel, isBoardOn: bool):
    """
    Turns off the EEG board, stops streaming, and re-enables GUI elements.

    :param isBoardOn: Is the board currently on?
    :param board_shim: The active BoardShim instance.
    :param board_id_input: QLineEdit for Board ID.
    :param port_input: QComboBox for available ports.
    :param channel_dial: QDial for number of channels.
    :param common_ref_checkbox: QCheckBox for enabling common reference (RLD).
    :param status_bar: QLabel to display status updates.
    """
    if not board_shim:
        set_status(status_bar, "Error: No active board to turn off", error=True)
        isBoardOn = False
        return

    try:
        if board_shim.is_prepared():
            board_shim.release_session()
            logging.info("Board session released.")

        # **Re-enable UI elements**
        board_id_input.setDisabled(False)
        port_input.setDisabled(False)
        channel_dial.setDisabled(False)
        common_ref_checkbox.setDisabled(False)

        # **Update status bar**
        set_status(status_bar, "Board Off", error=False)
        isBoardOn = False

    except Exception as e:
        logging.error("Exception while turning off the board", exc_info=True)
        isBoardOn = isBoardOn #Remains at its current state
        set_status(status_bar, f"Error: {str(e)}", error=True)



def set_status(status_bar: QLabel, message: str, error: bool = False):
    """
    Updates the status bar message while keeping the existing style and changing only the text color.

    :param status_bar: QLabel to update.
    :param message: The message to display.
    :param error: Whether the message indicates an error (red text for errors, black for normal).
    """
    status_bar.setText(message)
    text_color = "red" if error else "black"

    existing_style = """
        QLabel {
            background-color: white; /* White background */
            border: 2px solid black; /* Black outline */
            border-radius: 10px; /* Rounded corners */
            padding: 5px; /* Padding inside the label */
            font-family: "Montserrat ExtraBold", sans-serif; /* Use Montserrat ExtraBold */
            font-size: 14px; /* Adjust size as needed */
        
    """
    status_bar.setStyleSheet(existing_style + " color: "+str(text_color)+";}")