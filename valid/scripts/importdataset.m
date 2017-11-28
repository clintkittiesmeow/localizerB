function [ data, tests, macs, durations, hop_rates ] = importdataset( working_directory )
%IMPORTDATASET Summary of this function goes here
%   Detailed explanation goes here

    % Get list of directories to gather data from
    files = dir(working_directory);
    issub = [files(:).isdir];
    tests = {files(issub).name};
    tests(ismember(tests,{'.','..'})) = [];

    % Prepare cell array of tables
    data = cell(length(tests),1);

    % Import each test into a table
    macs = loadmacs;
    for test = 1:length(tests)
        dirstring = fullfile(pwd, tests(test), '**', '*-results.csv');
        % Build list of results.csv files to import
        passes = rdir(char(dirstring));
        data{test} = table();

        % Import each results.csv file
        for pass = passes'
            data{test} = [data{test}; importfile(pass.name, 2, inf, cellstr(macs.BSSID))];
        end
    end

    % Get durations from tests
    durations = zeros(length(tests),1);
    for test = 1:length(tests)
        durations(test) = mean(data{test}.duration);
    end
    
    % Get hop rate from tests
    hop_rates = zeros(length(tests),1);
    for test = 1:length(tests)
        hop_rates(test) = mean(data{test}.hoprate);
    end

end

