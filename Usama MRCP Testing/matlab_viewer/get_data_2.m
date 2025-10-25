p = BrainFlowInputParams();
p.serial_port = 'COM3';

% Use the DEFAULT_PRESET
preset = int32(BrainFlowPresets.DEFAULT_PRESET);

% Create the BoardShim object
b = BoardShim(int32(BoardIds.NEUROPAWN_KNIGHT_BOARD), p);

% --- FIX --- 
% Use a single, reliable onCleanup function.
% This ensures cleanup always runs, even if the script is terminated early.
c = onCleanup(@() cleanupBoard(b));

% Prepare the session
b.prepare_session();

% Optional: Set up a file streamer
% b.add_streamer('file://data.csv:w', preset);

% Start the stream
b.start_stream(450000, '');
pause(3.0);

% --- FIX ---
% Handle board configuration in a single try/catch block for robustness.
cmds = { ...
    'chon_1_12', 'rldadd_1', 'chon_2_12', 'rldadd_2', ...
    'chon_3_12', 'rldadd_3', 'chon_4_12', 'rldadd_4', ...
    'chon_5_12', 'rldadd_5', 'chon_6_12', 'rldadd_6', ...
    'chon_7_12', 'rldadd_7', 'chon_8_12', 'rldadd_8' ...
};

for i=1:numel(cmds)
    try
        b.config_board(cmds{i});
        pause(1);
    catch ME
        fprintf('Warning: Could not configure board with command %s. Error: %s\n', cmds{i}, ME.message);
    end
end
pause(3.0);
% Drain any data that arrived during configuration
count = b.get_board_data_count(preset);
b.get_board_data(count,preset);
pause(2.0);
disp(b.get_board_descr(57,preset))
eeg_channels = b.get_eeg_channels(57,preset);
disp(eeg_channels)
timestamps_channel= b.get_timestamp_channel(57,preset);
disp(timestamps_channel)
% Get data
data = b.get_current_board_data(500, preset);


% --- Nested cleanup function ---
function cleanupBoard(board_shim)
    % This function will be called automatically on exit, ensuring a clean shutdown.
    try
        disp('Stopping board stream...');
        board_shim.stop_stream();
    catch ME
        fprintf('Warning: Could not stop stream during cleanup: %s\n', ME.message);
    end
    
    try
        disp('Releasing board session...');
        board_shim.release_session();
    catch ME
        fprintf('Warning: Could not release session during cleanup: %s\n', ME.message);
    end
    disp('Board cleanup complete.');
end
