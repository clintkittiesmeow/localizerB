function [ result_rate, result_bssi ] = results( tests, data, macs, durations )
%RESULTS Summary of this function goes here
%   Detailed explanation goes here

    % Run through each test and generate metrics
    % Metrics:
    %   Rate = beacons/second
    %   BSSI Rate = beacons/second for each bssi
    result_rate = zeros(length(tests),30);
    result_bssi = zeros(length(tests),size(macs.BSSID, 1),30);
    for test = 1:length(tests)

        % Discover how many passes were done for this test
        passes = unique(data{test}.pass);

        % Step through each pass of each test
        for pass = passes'
            pass_data = data{test}(data{test}.pass == pass,:);
            result_rate(test,pass+1) = height(pass_data) / durations(test);

            result_bssi(test,:,pass+1) = countcats(data{test}(data{test}.pass == pass,:).bssid);
        end
    end

end

