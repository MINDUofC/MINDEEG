p = BrainFlowInputParams();
p.serial_port = 'COM3';

preset = int32(BrainFlowPresets.DEFAULT_PRESET);
b = BoardShim(int32(BoardIds.NEUROPAWN_KNIGHT_BOARD), p);

% cleanup always runs (even if you Ctrl+C)
c = onCleanup(@() cleanupBoard(b));

b.prepare_session();

% Stream to UDP for Simulink (localhost:25000)
b.add_streamer('streaming_board://127.0.0.1:25000', preset);
b.start_stream(450000, '');
pause(2.0);   % settle

% ---- one-time configuration ----
cmds = { ...
    'chon_1_12','rldadd_1','chon_2_12','rldadd_2', ...
    'chon_3_12','rldadd_3','chon_4_12','rldadd_4', ...
    'chon_5_12','rldadd_5','chon_6_12','rldadd_6', ...
    'chon_7_12','rldadd_7','chon_8_12','rldadd_8'  ...
};
for i = 1:numel(cmds)
    try
        b.config_board(cmds{i});
        pause(0.1);
    catch ME
        fprintf("Warning: config '%s' failed: %s\n", cmds{i}, ME.message);
    end
end

% drain any residuals after config
try, b.get_board_data(preset); end
pause(0.5);

% ---- run forever (until Ctrl+C) ----
fprintf('\nStreaming… Press Ctrl+C to stop. (buffer, ~rate)\n');
lastCnt = 0; lastT = tic;
while true
    pause(0.5);                           % keeps CPU low; tune if you want
    % quick health read: how many samples are buffered and est. incoming rate
    cnt = b.get_board_data_count(preset);
    dt  = toc(lastT);  if dt <= 0, dt = 0.5; end
    rate_est = (cnt - lastCnt) / dt;
    fprintf('\rbuffer=%6d   ~%6.1f samp/s', cnt, rate_est);
    lastCnt = cnt; lastT = tic;

    drawnow limitrate;                    % lets Ctrl+C break promptly
end

% -------- helper --------
function cleanupBoard(board_shim)
    try, disp('Stopping board stream…');  board_shim.stop_stream();   catch, end
    try, disp('Releasing board session…');board_shim.release_session();catch, end
    disp('Board cleanup complete.');
end
