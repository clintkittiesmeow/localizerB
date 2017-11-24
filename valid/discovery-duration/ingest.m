results = rdir([pwd, '\**\*-results.csv']);
contents = table();
for result = results'
    contents = [contents; importfile(result.name, 2)];
end

macs = splitlines(strtrim(fileread('../../macs')));