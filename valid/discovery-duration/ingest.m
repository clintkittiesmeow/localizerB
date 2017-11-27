
% Get list of directories to gather data from
files = dir(pwd);
issub = [files(:).isdir];
tests = {files(issub).name};
tests(ismember(tests,{'.','..'})) = [];

% Prepare cell array of tables
data = cell(length(tests),1);

% Import each test into a table
for test = 1:length(tests)
    dirstring = fullfile(pwd, tests(test), '**', '*-results.csv');
    % Build list of results.csv files to import
    passes = rdir(char(dirstring));
    data{test} = table();
    
    % Import each results.csv file
    for pass = passes'
        data{test} = [data{test}; importfile(pass.name, 2)];
    end
end

% List of mac addresses
macs = splitlines(strtrim(fileread('../../macs')));

% Run through each test and generate metrics
% Metrics:
%   Rate = beacons/second
%   Coverage = % of bssids detected <- large penalty per bssid
results = cell(length(tests),1);
for test = 1:length(tests)
    
    % Discover how many passes were done for this test
    passes = unique(data{test}.pass);
    % Generate an array to store our results in
    results{test} = zeros(length(passes),2);
    % Step through each pass of each test
    for pass = passes'
        pass_data = data{test}(data{test}.pass == pass,:);
        results{test}(pass+1,1) = height(pass_data) / data{test}.duration(1);
        coverage = 0;
        
        pass_macs = unique(data{test}.bssid);
        for mac = macs'
            if any(pass_macs == mac)
                coverage = coverage + 1;
            end
        end
        
        % Convert results to a percentage
        results{test}(pass+1,2) = coverage / length(macs);
    end
end