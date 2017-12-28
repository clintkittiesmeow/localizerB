% Get list of directories to gather data from
files = dir(pwd);
issub = [files(:).isdir];
positions = {files(issub).name};
positions(ismember(positions,{'.','..'})) = [];

coords = zeros(length(positions), 6);

addpath ../scripts/
% Import each test into a table
for position = 1:length(positions)
    gps = [1,6];
    gps = get_average_location(positions{position});
    %coords(position, :) = 
end
rmpath ../scripts/
