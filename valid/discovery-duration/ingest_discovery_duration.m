
% Get list of directories to gather data from
files = dir(pwd);
issub = [files(:).isdir];
tests = {files(issub).name};
tests(ismember(tests,{'.','..'})) = [];

% Prepare cell array of tables
data = cell(length(tests),1);

% Import each test into a table
addpath ../scripts/
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
rmpath ../scripts/

% List of mac addresses
macs = splitlines(strtrim(fileread('../../macs')));

% Get durations from tests
durations = zeros(length(tests),1);
for test = 1:length(tests)
    durations(test) = mean(data{test}.duration);
end

% Run through each test and generate metrics
% Metrics:
%   Rate = beacons/second
%   BSSI Rate = beacons/second for each bssi
result_rate = zeros(length(tests),30);
result_bssi = zeros(length(tests),length(macs),30);
for test = 1:length(tests)
    
    % Discover how many passes were done for this test
    passes = unique(data{test}.pass);

    % Step through each pass of each test
    for pass = passes'
        pass_data = data{test}(data{test}.pass == pass,:);
        result_rate(test,pass+1) = height(pass_data) / durations(test);
        
        result_bssi(test,:,pass+1) = countcats(data{test}(data{test}.pass == pass,:).bssid);
    end
    
    % Calculate
end

figure

% Display rate data
subplot(2,1,1);
boxplot(result_rate', 'Labels', durations);
xlabel('Duration');
ylabel('Beacons per second');

% Display bssi rate
means = mean(result_bssi, 3);
subplot(2,1,2);
%s = summary(data{test});
% labels = char(s.bssid.Categories);
bar(bsxfun(@rdivide, means', durations'));
xlabel('BSSI');
ylabel('Beacons per second');

