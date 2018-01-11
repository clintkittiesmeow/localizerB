function [averageLat,averageLon,averageAlt,averageLatErr,averageLonErr,averageAltErr] = get_average_location(working_directory, plot_points)
%GET_AVERAGE_LOCATION Summary of this function goes here
%   Give a directory that contains directories of passes (each pass
%   directory contains a *-test.csv, and this function will average the gps
%   coordinates of each of them. 

    files = dir(working_directory);
    issub = [files(:).isdir];
    passes = {files(issub).name};
    passes(ismember(passes,{'.','..'})) = [];

    lats = zeros(length(passes),1);
    lons = zeros(length(passes),1);
    alts = zeros(length(passes),1);
    err_lat = zeros(length(passes),1);
    err_lon = zeros(length(passes),1);
    err_alt = zeros(length(passes),1);
    
    % Get the latitude and longitude of each test
    for pass = 1:length(passes)
        dirstring = fullfile(working_directory, passes(pass), '*-test.csv');
        % Build list of results.csv files to import
        test = rdir(char(dirstring));

        % Read the test data
        csv = importtest(test.name);
        lats(pass) = csv.pos_lat;
        lons(pass) = csv.pos_lon;
        alts(pass) = csv.pos_alt;
        err_lat(pass) = csv.pos_lat_err;
        err_lon(pass) = csv.pos_lon_err;
        err_alt(pass) = csv.pos_alt_err;
    end
    
    averageLat = mean(lats);
    averageLon = mean(lons);
    averageAlt = mean(alts);
    averageLatErr = mean(err_lat);
    averageLonErr = mean(err_lon);
    averageAltErr = mean(err_alt);
    
    if exist('plot_points','var') && plot_points == true
        scatter(lats, lons);
        hold on
        plot(averageLat, averageLon, 'b--x', 'MarkerSize', 20);
        plot(median(lats), median(lons),'b--d', 'MarkerSize', 20);
        plot(get(gca,'xlim'), [averageLon, averageLon]);
        plot([averageLat, averageLat], get(gca,'ylim'));
        hold off
    end
    
end

