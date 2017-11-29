function [coprimes] = generate_hop_int(start_num, end_num)
%GENERATE_HOP_INT Summary of this function goes here
%   Detailed explanation goes here

    TU = 1024/1000000;  % 1 TU = 1024 usec https://en.wikipedia.org/wiki/TU_(Time_Unit)
    STD_BEACON_SCALE = 100;
    DEFAULT_START = STD_BEACON_SCALE/10;
    DEFAULT_END = STD_BEACON_SCALE*2;

    switch nargin
        case 0
            start_num = DEFAULT_START;
            end_num = DEFAULT_END;
        case 1
            end_num = DEFAULT_END;
    end
    
    coprimes = containers.Map('KeyType','uint32','ValueType','single');
    for i = floor(start_num):ceil(end_num)
        if gcd(i,STD_BEACON_SCALE) == 1
            coprimes(i) = round(i*TU, 5);
        end
    end
    
    bar(cell2mat(keys(coprimes)), ones(1,length(coprimes)));
    set(gca, 'XTickLabel', keys(coprimes));
    set(gca, 'XTickLabelRotation', 45)
    xticks(cell2mat(keys(coprimes)))
    text(double(cell2mat(keys(coprimes))), double(ones(1,length(coprimes))+.1), string(cell2mat(values(coprimes))))
    ylim([0 2]);
end

